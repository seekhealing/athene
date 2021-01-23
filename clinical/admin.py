from decimal import Decimal
from functools import update_wrapper

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum, Avg, Q
from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from . import models, flow


csrf_protect_m = method_decorator(csrf_protect)


class ExtraCareNoteAdmin(admin.StackedInline):
    model = models.ExtraCareNote
    extra = 1
    template = "admin/edit_inline/stacked_safe_display.html"
    fieldsets = ((None, {"fields": ("note",)}),)

    def has_change_permission(self, request, obj=None):
        return False


class HiddenInputWithDisplay(forms.TextInput):
    template_name = "widgets/hidden_with_display.html"


class ProgressEventForm(forms.ModelForm):
    class Meta:
        model = models.ProgressEvent
        widgets = {
            "event_type": HiddenInputWithDisplay,
            "phase": forms.HiddenInput,
            "program_flow": forms.HiddenInput,
            "note": forms.TextInput(attrs=dict(size=80)),
        }
        fields = forms.ALL_FIELDS


class ProgressFormSet(forms.BaseInlineFormSet):
    def __init__(self, data=None, files=None, instance=None, save_as_new=False, prefix=None, queryset=None, **kwargs):
        # I've simply copied BaseInlineFormSet's __init__ method here, but added the additional
        # queryset constraint to limit things to the current flow
        if instance is None:
            self.instance = self.fk.remote_field.model()
        else:
            self.instance = instance
        self.save_as_new = save_as_new
        if queryset is None:
            queryset = self.model._default_manager
        if self.instance.pk is not None:
            qs = queryset.filter(
                **{self.fk.name: self.instance, "program_flow": instance.current_program_flow, "complete": False}
            )
        else:
            qs = queryset.none()
        self.unique_fields = {self.fk.name}
        super(forms.BaseInlineFormSet, self).__init__(data, files, prefix=prefix, queryset=qs, **kwargs)

        # Add the generated field to form._meta.fields if it's defined to make
        # sure validation isn't skipped on that field.
        if self.form._meta.fields and self.fk.name not in self.form._meta.fields:
            if isinstance(self.form._meta.fields, tuple):
                self.form._meta.fields = list(self.form._meta.fields)
            self.form._meta.fields.append(self.fk.name)
        # End of the copying from BaseInlineFormSet

        if self.instance.pk is not None:
            event_types, phase, _ = flow.extra_care_flow(self.instance)
            self.min_num = self.max_num = len(event_types)
            for event in qs:
                event_types.remove(event.event_type)
            self.initial_extra = [
                dict(event_type=event_type, phase=phase, program_flow=self.instance.current_program_flow)
                for event_type in event_types
            ]
            self.extra = len(self.initial_extra)

    def clean(self):
        if any(self.errors):
            return
        errors = flow.validate_extra_care_flow(
            self.instance, [form.cleaned_data for form in self.forms if form.has_changed()]
        )
        if errors:
            raise ValidationError(errors)


class ProgressEventInlineAdmin(admin.StackedInline):
    fieldsets = (
        (None, {"fields": (("event_type", "phase", "program_flow"), ("scheduled", "occurred", "excused"), ("note",))}),
    )
    model = models.ProgressEvent
    can_delete = False
    formset = ProgressFormSet
    form = ProgressEventForm
    template = "admin/clinical/progressevent/progressevent_inline.html"


class ExtraCareAdmin(admin.ModelAdmin):
    model = models.ExtraCare
    fieldsets = ((None, {"fields": ("status",)}),)
    readonly_fields = ["status"]
    list_display = ["first_names", "last_names", "email", "phone_number", "status"]
    list_filter = ["status"]
    inlines = [ProgressEventInlineAdmin, ExtraCareNoteAdmin]

    def get_object(self, request, object_id, from_field=None):
        to_return = super().get_object(request, object_id, from_field)
        if to_return:
            models.AuditLog.objects.create(
                extracare=to_return,
                ip_address=request.META.get("REMOTE_ADDR"),
                user=request.user,
                operation=models.AuditLog.Operation.READ,
            )
        return to_return

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if obj:
            event_count, since_date = obj.recent_events_attended
            if event_count == 0 and obj.status == "active":
                self.message_user(
                    request,
                    f"Seeker {obj.human.first_names} {obj.human.last_names} has attended zero events "
                    "since last Monday.",
                    messages.WARNING,
                )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_change(self, request, new_object):
        # Save the new object one more time to kick off the signals updating status
        instance = models.ExtraCare.objects.get(pk=new_object.pk)
        instance._no_log = True
        instance.save()
        return super().response_change(request, new_object)

    def get_urls(self):
        from django.urls import path

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            wrapper.model_admin = self
            return update_wrapper(wrapper, view)

        return [
            path("<path:object_id>/exit_early/", wrap(self.exit_flow_early), name="clinical_extracare_exitearly"),
        ] + super().get_urls()

    @csrf_protect_m
    def exit_flow_early(self, request, object_id):
        if request.method == "POST":
            extracare = get_object_or_404(models.ExtraCare, human_id=object_id)
            if extracare.status == "active":
                extracare.exit_early()
                self.message_user(request, f"Exited program flow for {extracare}", messages.SUCCESS)
            else:
                self.message_user(
                    request, f"Seeker {extracare} has no active program flow, so cannot exit early.", messages.ERROR,
                )
        return HttpResponseRedirect(reverse("admin:clinical_extracare_change", args=(object_id,)))

    def has_add_permission(self, request):
        return False


class ExtraCareBenefitAdmin(admin.TabularInline):
    model = models.ExtraCareBenefit
    extra = 1
    fields = ["benefit_type", "cost", "scheduled", "date", "cancelled"]
    autocomplete_fields = ["benefit_type"]


class ExtraCareBenefitProxyAdmin(admin.ModelAdmin):
    model = models.ExtraCareBenefitProxy
    inlines = [ExtraCareBenefitAdmin]
    fieldsets = ((None, {"fields": tuple()}),)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["benefit_types"] = dict(
            models.ExtraCareBenefitType.objects.all().values_list("id", "default_cost")
        )
        return super().changeform_view(request, object_id, form_url, extra_context)

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        today = timezone.now().date()

        benefit_types = models.ExtraCareBenefitType.objects.all().order_by("connectionagent", "name")
        this_month_filter = Q(extracarebenefit__date__month=today.month, extracarebenefit__date__year=today.year) | Q(
            extracarebenefit__cancelled__month=today.month, extracarebenefit__cancelled__year=today.year
        )
        this_year_filter = Q(extracarebenefit__date__year=today.year) | Q(extracarebenefit__cancelled__year=today.year)
        used_benefit_filter = Q(extracarebenefit__date__isnull=False) | Q(extracarebenefit__cancelled__isnull=False)

        def _annotated(qs, filter_q):
            to_return = qs.annotate(used=Count("extracarebenefit", filter=filter_q & used_benefit_filter))
            to_return = to_return.annotate(total=Sum("extracarebenefit__cost", filter=filter_q & used_benefit_filter))
            to_return = to_return.annotate(
                average_cost=Avg("extracarebenefit__cost", filter=filter_q & used_benefit_filter)
            )
            return to_return

        this_month = _annotated(benefit_types, this_month_filter)
        this_year = _annotated(benefit_types, this_year_filter)
        all_time = _annotated(benefit_types, Q())

        seekers_this_month = models.ExtraCareBenefit.objects.filter(
            Q(date__month=today.month, date__year=today.year)
            | Q(cancelled__month=today.month, cancelled__year=today.year)
        ).aggregate(count=Count("extracare"))["count"]
        total_spent_this_month = models.ExtraCareBenefit.objects.filter(
            Q(date__month=today.month, date__year=today.year)
            | Q(cancelled__month=today.month, cancelled__year=today.year)
        ).aggregate(total=Sum("cost"))["total"] or Decimal("0")
        if seekers_this_month:
            avg_per_seeker = total_spent_this_month / seekers_this_month
        else:
            avg_per_seeker = Decimal("0")

        cost_per_seeker = _annotated(models.ExtraCare.objects.all(), this_month_filter)
        cost_per_seeker = cost_per_seeker.filter(used__gt=0).order_by("-used", "-total")

        return TemplateResponse(
            request,
            "admin/clinical/extracarebenefitproxy/change_list.html",
            context=dict(
                today=today,
                by_benefit_type=zip(this_month, this_year, all_time),
                seekers_this_month=seekers_this_month,
                total_spent_this_month=total_spent_this_month,
                avg_per_seeker=avg_per_seeker,
                cost_per_seeker=cost_per_seeker,
                cl=self.get_changelist_instance(request),
            ),
        )


class ConnectionAgentAdmin(admin.ModelAdmin):
    search_fields = ["name", "point_of_contact"]


class ExtraCareBenefitTypeAdmin(admin.ModelAdmin):
    search_fields = ["name"]


admin.site.register(models.ExtraCare, ExtraCareAdmin)
admin.site.register(models.ExtraCareBenefitProxy, ExtraCareBenefitProxyAdmin)
admin.site.register(models.ConnectionAgent, ConnectionAgentAdmin)
admin.site.register(models.ExtraCareBenefitType, ExtraCareBenefitTypeAdmin)