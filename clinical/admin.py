from decimal import Decimal

from django.contrib import admin
from django.db.models import Count, Sum, Avg, Q
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from . import models


csrf_protect_m = method_decorator(csrf_protect)


class ExtraCareNoteAdmin(admin.StackedInline):
    model = models.ExtraCareNote
    extra = 1
    template = "admin/edit_inline/stacked_safe_display.html"
    fieldsets = ((None, {"fields": ("note",)}),)

    def has_change_permission(self, request, obj=None):
        return False


class ExtraCareAdmin(admin.ModelAdmin):
    model = models.ExtraCare
    fieldsets = ((None, {"fields": ("status",)}),)
    readonly_fields = ["status"]
    list_display = ["first_names", "last_names", "email", "phone_number"]
    inlines = [ExtraCareNoteAdmin]

    def has_add_permission(self, request):
        return False


class ExtraCareBenefitAdmin(admin.TabularInline):
    model = models.ExtraCareBenefit
    extra = 1
    autocomplete_fields = ["benefit_type"]


class ExtraCareBenefitProxyAdmin(admin.ModelAdmin):
    model = models.ExtraCareBenefitProxy
    inlines = [ExtraCareBenefitAdmin]
    fieldsets = ((None, {"fields": tuple()}),)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["benefit_types"] = dict(
            models.ExtraCareBenefitType.objects.all().values_list("id", "default_cost")
        )
        return super().changeform_view(request, object_id, form_url, extra_context)

    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        today = timezone.now().date()

        benefit_types = models.ExtraCareBenefitType.objects.all()
        this_month_filter = Q(extracarebenefit__date__month=today.month, extracarebenefit__date__year=today.year)
        this_year_filter = Q(extracarebenefit__date__year=today.year)

        def _annotated(qs, filter_q):
            to_return = qs.annotate(used=Count("extracarebenefit", filter=filter_q))
            to_return = to_return.annotate(total=Sum("extracarebenefit__cost", filter=filter_q))
            to_return = to_return.annotate(average_cost=Avg("extracarebenefit__cost", filter=filter_q))
            return to_return

        this_month = _annotated(benefit_types, this_month_filter)
        this_year = _annotated(benefit_types, this_year_filter)
        all_time = _annotated(benefit_types, None)

        seekers_this_month = models.ExtraCareBenefit.objects.filter(date__month=today.month).aggregate(
            count=Count("extracare")
        )["count"]
        total_spent_this_month = models.ExtraCareBenefit.objects.filter(date__month=today.month).aggregate(
            total=Sum("cost")
        )["total"] or Decimal("0")
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


class ExtraCareBenefitTypeAdmin(admin.ModelAdmin):
    search_fields = ["name"]


admin.site.register(models.ExtraCare, ExtraCareAdmin)
admin.site.register(models.ExtraCareBenefitProxy, ExtraCareBenefitProxyAdmin)
admin.site.register(models.ExtraCareBenefitType, ExtraCareBenefitTypeAdmin)
