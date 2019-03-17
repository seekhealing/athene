import copy
import logging

logger = logging.getLogger(__name__)

from django.contrib import admin
from django.conf import settings
from django.apps import apps
from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from . import models, mailchimp
from events.admin import HumanCalendarSubscriptionAdmin

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
            if obj.email:
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

        for instance in instances:
            if isinstance(instance, models.HumanNote):
                if not instance.id:
                    instance.added_by = request.user
            instance.save()

class HumanAdmin(HumanAdminMixin, admin.ModelAdmin):
    inlines = [HumanNoteAdmin, HumanCalendarSubscriptionAdmin]
    model = models.Human

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
        seeker = human.upgrade_to_seeker()
        self.message_user(request, f'{human} has been enrolled as a Seeker.')
        return HttpResponseRedirect(reverse('admin:seekers_seeker_change', args=(object_id,)))

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.path.endswith('/autocomplete/'):
            return qs
        else:
            return qs.filter(seeker__isnull=True)

    fieldsets = (
        (None, {
            'fields': ['show_id', ('first_names', 'last_names'), 
                       ('city', 'state')],
        }),
        ('Contact information', {
            'fields': (('email', 'phone_number'), 'contact_preference')
        }), 
        ('Record history', {
            'fields': (('created', 'updated'),),
        }),
    )

    def _get_obj_does_not_exist_redirect(self, request, opts, object_id):
        try:
            seeker_obj = models.Seeker.objects.get(pk=object_id)
        except models.Seeker.DoesNotExist as e:
            return HttpResponseRedirect(
                reverse('admin:seekers_seeker_change', args=(object_id,))
            )
        else:
            return super()._get_obj_does_not_exist_redirect(request, opts, object_id)

    def get_fieldsets(self, request, obj=None):
        if obj is None and '_popup' in request.GET:
            shortened_fieldsets = copy.deepcopy(self.fieldsets[0:2])
            shortened_fieldsets[0][1]['fields'].remove('show_id')
            return shortened_fieldsets
        return super().get_fieldsets(request, obj)
    
    readonly_fields = ['show_id', 'created','updated']
    list_display = ['__str__', 'email', 'phone_number']
    search_fields = ['last_names', 'first_names', 'email', 'phone_number']

    def enroll_as_seeker(self, request, queryset):
        for obj in queryset:
            logger.info(f'Upgrading {obj} from prospect to Seeker.')
            obj.upgrade_to_seeker()
        self.message_user(request, f'{len(queryset)} prospect(s) enrolled as Seekers.')
    enroll_as_seeker.short_description = 'Enroll as Seeker'

    actions = ['enroll_as_seeker']

class IsActiveFilter(admin.SimpleListFilter):
    title = 'Active'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes'),
            ('0', 'No')
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'true':
            return queryset.filter(inactive_date__isnull=True)
        elif self.value() == 'false':
            return queryset.filter(inactive_date__isnull=False)
        else:
            return queryset        

class SeekerAdmin(HumanAdminMixin, admin.ModelAdmin):
    inlines = [HumanNoteAdmin, SeekerMilestoneAdmin, 
               HumanCalendarSubscriptionAdmin,]

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
            'fields': (('ride_share', 'space_holder', 'activity_buddy', 'outreach'),),
        }),
        ('Important dates', {
            'fields': (('birthdate', 'sober_anniversary'),),
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
    list_display = ['__str__', 'email', 'phone_number', 'listener_trained', 'extra_care', 'extra_care_graduate', 'is_active']
    list_filter = ['listener_trained', 'extra_care', 'extra_care_graduate', IsActiveFilter,
                   'ride_share', 'space_holder', 'activity_buddy', 'outreach']
    search_fields = ['last_names', 'first_names', 'email', 'phone_number']

    def seeker_pairs(self, instance):
        return ', '.join(map(str, instance.seeker_pairs))
    
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
    


class SeekerPairingAdmin(admin.ModelAdmin):
    model = models.SeekerPairing
    list_display = ('left', 'right', 'pair_date', 'unpair_date')


admin.site.register(models.Human, HumanAdmin)
admin.site.register(models.Seeker, SeekerAdmin)
admin.site.register(models.SeekerPairing, SeekerPairingAdmin)