import copy
from decimal import Decimal
import logging

from django.contrib import admin
from django.conf import settings
from django.db.models import Count, Sum, Avg, Q
from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from . import models, mailchimp
from events.admin import HumanCalendarSubscriptionAdmin


logger = logging.getLogger(__name__)
csrf_protect_m = method_decorator(csrf_protect)


class SeekerMilestoneAdmin(admin.TabularInline):
    model = models.SeekerMilestone
    extra = 1
    classes = ["collapse"]


class HumanNoteAdmin(admin.StackedInline):
    model = models.HumanNote
    extra = 1
    template = 'admin/edit_inline/stacked_safe_display.html'
    fieldsets = (
        (None, {
            'fields': ('note',)
        }),)

    def has_change_permission(self, request, obj=None):
        return False


class MailchimpForm(forms.Form):
    tags = forms.MultipleChoiceField(choices=[(t,t) for t in settings.MAILCHIMP_TAGS],
                                     widget=forms.widgets.CheckboxSelectMultiple,
                                     required=False)


class HumanAdminMixin(object):
    def save_model(self, request, obj, form, change):
        to_return = super().save_model(request, obj, form, change)
        if not change and obj.email:
            status = mailchimp.client.subscription_status(obj.email)
            if status['status'] != 'subscribed':
                tags = getattr(settings, f'MAILCHIMP_DEFAULT_{self.model._meta.model_name.upper()}_TAGS')
                logger.info(f'Subscribing new {obj} to mailing list with tags {tags}')
                mailchimp.client.subscribe_user(obj.first_names, obj.last_names,
                                                obj.email, tags)
        return to_return

    def save_related(self, request, form, formsets, change):
        to_return = super().save_related(request, form, formsets, change)
        if change and form.instance.email:
            status = mailchimp.client.subscription_status(form.instance.email)
            if status['status'] == 'subscribed':
                mc_form = MailchimpForm(request.POST)
                if mc_form.is_valid():
                    logger.info(f'Updating subscription tags for {form.instance}')
                    mailchimp.client.update_user_tags(form.instance.email,
                                                      mc_form.cleaned_data['tags'])
                else:
                    logger.warning(f'Tags form was invalid. {form.errors}')
        return to_return

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or dict()
        initial_tags = []
        if object_id:
            obj = self.get_object(request, object_id)
            if obj and obj.email:
                status = mailchimp.client.subscription_status(obj.email)
                logger.debug(f'Current subscription status: {status}')
                initial_tags = [tag['name'] for tag in status.get('tags', [])]
                extra_context['mailchimp_status'] = status
        extra_context['mailchimp_form'] = MailchimpForm(initial=dict(tags=initial_tags))
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        if not obj and '_popup' in request.GET: # this is an add
            return []
        return inline_instances

    def show_id(self, instance):
        return instance.id
    show_id.short_description = 'Identifier'
 
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        formset.save_existing_objects()

        for instance in instances:
            if not instance.id:
                if isinstance(instance, models.HumanNote):
                    instance.added_by = request.user
            instance.save()


class FirstConversationFilter(admin.SimpleListFilter):
    title = 'First conversation scheduled'
    parameter_name = 'first_conv'

    def lookups(self, request, model_admin):
        return (
            ('future', 'Scheduled'),
            ('past', 'Already occurred'),
            ('null', 'Needs scheduling')
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'future':
            return queryset.filter(first_conversation__isnull=False,
                                   first_conversation__gte=timezone.now().date())
        if self.value() == 'past':
            return queryset.filter(first_conversation__isnull=False,
                                   first_conversation__lte=timezone.now().date())
        if self.value() == 'null':
            return queryset.filter(first_conversation__isnull=True)
        return queryset


class HumanAdmin(HumanAdminMixin, admin.ModelAdmin):
    inlines = [HumanNoteAdmin, HumanCalendarSubscriptionAdmin]
    model = models.Human
    list_filter = [FirstConversationFilter]

    def get_urls(self):
        from django.urls import path
        urlpatterns = super().get_urls()
        urlpatterns = [
            path('<path:object_id>/enroll/', 
                 self.admin_site.admin_view(self.enroll_seeker), 
                 name='seekers_human_enroll')
        ] + urlpatterns
        return urlpatterns

    def enroll_seeker(self, request, object_id):
        human = self.get_object(request, object_id)
        _ = human.upgrade_to_seeker()
        self.message_user(request, f'{human} has been enrolled as a Seeker.')
        return HttpResponseRedirect(reverse('admin:seekers_seeker_change', args=(object_id,)))

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.path.endswith('/autocomplete/'):
            return qs
        else:
            return qs.filter(seeker__isnull=True, communitypartner__isnull=True)

    fieldsets = [
        (None, {
            'fields': ['show_id', ('first_names', 'last_names'), 
                       'street_address', ('city', 'state', 'zip_code')],
        }),
        ('Contact information', {
            'fields': (('email', 'phone_number'), 'contact_preference')
        }),
        ('Important dates', {
            'fields': (('birthdate', 'sober_anniversary'), 'first_conversation'),
        }),
        ('Record history', {
            'fields': (('created', 'updated'),),
        }),
    ]

    def _get_obj_does_not_exist_redirect(self, request, opts, object_id):
        try:
            _ = models.Seeker.objects.get(pk=object_id)
        except models.Seeker.DoesNotExist:
            return HttpResponseRedirect(
                reverse('admin:seekers_seeker_change', args=(object_id,))
            )
        else:
            return super()._get_obj_does_not_exist_redirect(request, opts, object_id)

    def get_fieldsets(self, request, obj=None):
        if obj is None and '_popup' in request.GET:
            shortened_fieldsets = copy.deepcopy(self.fieldsets[0:2])
            shortened_fieldsets[0][1]['fields'] = [('first_names', 'last_names'), 
                                                   ('city', 'state')]
            return shortened_fieldsets
        return super().get_fieldsets(request, obj)
    
    readonly_fields = ['show_id', 'created', 'updated']
    list_display = ['first_names', 'last_names', 'email', 'phone_number', 'first_conversation', 'created']
    search_fields = ['last_names', 'first_names', 'email', 'phone_number']

    def enroll_as_seeker(self, request, queryset):
        for obj in queryset:
            logger.info(f'Upgrading {obj} from prospect to Seeker.')
            obj.upgrade_to_seeker()
        self.message_user(request, f'{len(queryset)} prospect(s) enrolled as Seekers.')
    enroll_as_seeker.short_description = 'Enroll as Seeker'

    def mark_as_community_partner(self, request, queryset):
        for obj in queryset:
            logger.info(f'Migrating {obj} from prospect to Community Partner.')
            obj.mark_as_community_partner()
        self.message_user(request, f'{len(queryset)} prospect(s) marked as Community Partners.')
    mark_as_community_partner.short_description = 'Mark as Community Partner'

    actions = ['enroll_as_seeker', 'mark_as_community_partner']


class IsActiveFilter(admin.SimpleListFilter):
    title = 'Active'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes'),
            ('0', 'No')
        )
    
    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(inactive_date__isnull=True)
        elif self.value() == '0':
            return queryset.filter(inactive_date__isnull=False)
        else:
            return queryset        


class ServiceFilter(admin.SimpleListFilter):
    title = 'Service offer'
    parameter_name = 'service_offer'
    service_fields = ['ride_share', 'space_holder', 'facilitator',
                      'activity_buddy', 'outreach']

    def lookups(self, request, model_admin):
        return [
            (f, f.replace('_', ' ').capitalize()) for f in self.service_fields
        ]
    
    def queryset(self, request, queryset):
        if self.value() in self.service_fields:
            return queryset.filter(**{self.value(): True})
        return queryset


class IsConnectionAgentFilter(admin.SimpleListFilter):
    title = 'Connection agent'
    parameter_name = 'connection_agent'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes'),
            ('0', 'No')
        )
    
    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.exclude(connection_agent_organization='')
        elif self.value() == '0':
            return queryset.filter(connection_agent_organization='')
        else:
            return queryset        


class PairingStatusFilter(admin.SimpleListFilter):
    title = 'Pairing status'
    parameter_name = 'pairing_status'

    def lookups(self, request, model_admin):
        return (
            ('p', 'Paired'),
            ('u_r', 'Unpaired and ready'),
            ('u_u', 'Unpaired but unready')
        )
    
    def queryset(self, request, queryset):
        paired_filter = Q(left_pair__unpair_date__isnull=True, left_pair__id__isnull=False) | \
                        Q(right_pair__unpair_date__isnull=True, right_pair__id__isnull=False)
        if self.value() == 'p':
            return queryset.filter(paired_filter).distinct()
        paired_seekers = models.Seeker.objects.filter(paired_filter).values_list('id', flat=True)
        if self.value() == 'u_r':
            return queryset.filter(ready_to_pair=True).exclude(id__in=paired_seekers).distinct()
        if self.value() == 'u_u':
            return queryset.filter(ready_to_pair=False).exclude(id__in=paired_seekers).distinct()
        return queryset
            

class SeekerAdmin(HumanAdminMixin, admin.ModelAdmin):
    inlines = [HumanNoteAdmin, SeekerMilestoneAdmin,
               HumanCalendarSubscriptionAdmin]

    model = models.Seeker
    fieldsets = (
        (None, {
            'fields': ['show_id', ('first_names', 'last_names'), 
                       'street_address', ('city', 'state', 'zip_code'), 'seeker_pairs',
                       'transportation',
                       'listener_trained', 'extra_care', 'extra_care_graduate'],
        }),
        ('Contact information', {
            'fields': (('email', 'phone_number'), ('facebook_username',
                       'facebook_alias'), 'contact_preference')
        }),
        ('Service Opportunities', {
            'fields': (('ready_to_pair', 'ride_share', 'space_holder', 'activity_buddy', 'outreach'),
                       'connection_agent_organization'),
        }),
        ('Important dates', {
            'fields': (('birthdate', 'sober_anniversary'), ('first_conversation', 'enroll_date')),
        }),
        ('Record history', {
            'fields': (('created', 'updated'), 'inactive_date'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None and '_popup' in request.GET:
            shortened_fieldsets = copy.deepcopy(self.fieldsets[0:2])
            shortened_fieldsets[0][1]['fields'].remove('show_id')
            shortened_fieldsets[0][1]['fields'].remove('seeker_pair')
            return shortened_fieldsets
        return super().get_fieldsets(request, obj)

    readonly_fields = ['show_id', 'seeker_pairs', 'listener_trained', 
                       'extra_care', 'extra_care_graduate', 
                       'created', 'updated']
    list_display = ['first_names', 'last_names', 'email', 'phone_number', 'enroll_date', 'listener_trained', 
                    'extra_care', 'extra_care_graduate', 'is_active', 'is_connection_agent']
    list_display_links = ['first_names', 'last_names']
    list_filter = ['listener_trained', 'extra_care', 'extra_care_graduate', IsActiveFilter, IsConnectionAgentFilter,
                   PairingStatusFilter, ServiceFilter]
    search_fields = ['last_names', 'first_names', 'email', 'phone_number']

    def seeker_pairs(self, instance):
        return mark_safe(
            ', '.join(map(lambda sp: f'<a href="../../../seekerpairing/{sp[0]}/">{sp[1]}</a>', instance.seeker_pairs))
        )
        
    def get_urls(self):
        from django.urls import path
        urlpatterns = super().get_urls()
        urlpatterns = [
            path('<path:object_id>/ride/', 
                 self.admin_site.admin_view(self.find_a_ride), 
                 name='seekers_seeker_ride')
        ] + urlpatterns
        return urlpatterns

    def find_a_ride(self, request, object_id):
        seeker = self.get_object(request, object_id)
        context = dict(
            seeker=seeker,
            rides=seeker.find_ride(),
            is_popup=True
        )
        return render(request, 'admin/seekers/seeker/ride.html',
                      context=context)
    
    def downgrade_to_prospect(self, request, queryset):
        for seeker in queryset:
            seeker.delete(keep_parents=True)
        self.message_user(request, f'{len(queryset)} seeker(s) downgraded to Prospects.')
    downgrade_to_prospect.short_description = 'Downgrade to Prospect'

    actions = ['downgrade_to_prospect']


class IsActivePairingFilter(admin.SimpleListFilter):
    title = 'Active/Inactive Pairs'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Active'),
            ('0', 'Inactive')
        )
    
    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(unpair_date__isnull=True)
        elif self.value() == '0':
            return queryset.filter(unpair_date__isnull=False)
        else:
            return queryset        


class SeekerPairingMeetingAdmin(admin.TabularInline):
    model = models.SeekerPairingMeeting
    extra = 1


class SeekerPairingAdmin(admin.ModelAdmin):
    model = models.SeekerPairing
    list_display = ('left', 'right', 'pair_date', 'unpair_date')
    list_filter = [IsActivePairingFilter]
    inlines = [SeekerPairingMeetingAdmin]


class SeekerBenefitAdmin(admin.TabularInline):
    model = models.SeekerBenefit
    extra = 1
    autocomplete_fields = ['benefit_type']


class SeekerBenefitProxyAdmin(admin.ModelAdmin):
    model = models.SeekerBenefitProxy
    inlines = [SeekerBenefitAdmin]
    fieldsets = ((None, {'fields': tuple()}),)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['benefit_types'] = dict(models.SeekerBenefitType.objects.all().values_list('id', 'default_cost'))
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    @csrf_protect_m
    def changelist_view(self, request, extra_context=None):
        today = timezone.now().date()
        
        benefit_types = models.SeekerBenefitType.objects.all()
        this_month_filter = Q(seekerbenefit__date__month=today.month)
        this_year_filter = Q(seekerbenefit__date__year=today.year)

        def _annotated(qs, filter_q):
            to_return = qs.annotate(
                used=Count('seekerbenefit', filter=filter_q))
            to_return = to_return.annotate(
                total=Sum('seekerbenefit__cost', filter=filter_q))
            to_return = to_return.annotate(
                average_cost=Avg('seekerbenefit__cost', filter=filter_q))
            return to_return
        
        this_month = _annotated(benefit_types, this_month_filter)
        this_year = _annotated(benefit_types, this_year_filter)
        all_time = _annotated(benefit_types, None)

        seekers_this_month = models.SeekerBenefit.objects.filter(date__month=today.month)\
            .aggregate(count=Count('seeker'))['count']
        total_spent_this_month = models.SeekerBenefit.objects.filter(date__month=today.month)\
            .aggregate(total=Sum('cost'))['total'] or Decimal("0")
        if seekers_this_month:
            avg_per_seeker = total_spent_this_month / seekers_this_month
        else:
            avg_per_seeker = Decimal("0")

        cost_per_seeker = _annotated(models.Seeker.objects.all(), this_month_filter)
        cost_per_seeker = cost_per_seeker.filter(used__gt=0).order_by('-used', '-total')

        return TemplateResponse(
            request, 'admin/seekers/seekerbenefitproxy/change_list.html',
            context=dict(
                today=today,
                by_benefit_type=zip(this_month, this_year, all_time),
                seekers_this_month=seekers_this_month,
                total_spent_this_month=total_spent_this_month,
                avg_per_seeker=avg_per_seeker,
                cost_per_seeker=cost_per_seeker,
                cl=self.get_changelist_instance(request),

            )
        )


class SeekerBenefitTypeAdmin(admin.ModelAdmin):
    search_fields = ['name']


class CommunityPartnerAdmin(HumanAdminMixin, admin.ModelAdmin):
    model = models.CommunityPartner
    inlines = [HumanNoteAdmin, HumanCalendarSubscriptionAdmin]

    fieldsets = (
        (None, {
            'fields': ['show_id', ('first_names', 'last_names'), 
                       ('city', 'state'), 'organization'],
        }),
        ('Contact information', {
            'fields': (('email', 'phone_number'), 'contact_preference')
        }), 
        ('Record history', {
            'fields': (('created', 'updated'),),
        }),
    )
    readonly_fields = ['show_id', 'created', 'updated']
    list_display = ['first_names', 'last_names', 'email', 'phone_number']

admin.site.register(models.Human, HumanAdmin)
admin.site.register(models.Seeker, SeekerAdmin)
admin.site.register(models.CommunityPartner, CommunityPartnerAdmin)
admin.site.register(models.SeekerPairing, SeekerPairingAdmin)
admin.site.register(models.SeekerBenefitProxy, SeekerBenefitProxyAdmin)
admin.site.register(models.SeekerBenefitType, SeekerBenefitTypeAdmin)
