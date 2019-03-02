import copy

from django.contrib import admin
from django.apps import apps
from django import forms

from .models import Seeker, SeekerPairing, SeekerMilestone, SeekerNote
from events.admin import SeekerCalendarSubscriptionAdmin

class SeekerMilestoneAdmin(admin.TabularInline):
    model = SeekerMilestone
    extra = 1
    classes = ["collapse"]
    

class SeekerNoteAdmin(admin.StackedInline):
    model = SeekerNote
    extra = 1
    template = 'admin/edit_inline/stacked_safe_display.html'
    readonly_fields = ['added_by', 'created']

    def has_change_permission(self, request, obj=None):
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'added_by':
            return db_field.formfield(widget=forms.HiddenInput(),
                                      initial=request.user)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

class IsActiveFilter(admin.SimpleListFilter):
    title = 'Active?'
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


class SeekerAdmin(admin.ModelAdmin):
    inlines = [SeekerNoteAdmin, SeekerMilestoneAdmin, 
               SeekerCalendarSubscriptionAdmin,]

    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        if not obj and '_popup' in request.GET: # this is an add
            return []
        return inline_instances

    model = Seeker
    fieldsets = (
        (None, {
            'fields': ['show_id', ('first_names', 'last_names'), 
                       ('city', 'state'), 'seeker_pair',
                       'listener_trained', 'extra_care', 'extra_care_graduate'],
        }),
        ('Contact information', {
            'fields': (('email', 'phone_number'), ('facebook_username',
                       'facebook_alias'), 'contact_preference')
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

    readonly_fields = ['show_id', 'seeker_pair', 'listener_trained', 
                       'extra_care', 'extra_care_graduate', 
                       'created', 'updated']
    list_display = ['__str__', 'listener_trained', 'extra_care', 'extra_care_graduate', 'is_active']
    list_filter = ['listener_trained', 'extra_care', 'extra_care_graduate', IsActiveFilter]
    search_fields = ['last_names', 'first_names', 'email', 'phone_number']

    def show_id(self, instance):
        return instance.id
    show_id.short_description = 'Identifier'

    def seeker_pair(self, instance):
        return instance.seeker_pair

class SeekerPairingAdmin(admin.ModelAdmin):
    model = SeekerPairing
    list_display = ('left', 'right', 'pair_date', 'unpair_date')


admin.site.register(Seeker, SeekerAdmin)
admin.site.register(SeekerPairing, SeekerPairingAdmin)