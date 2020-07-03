import datetime

from dateutil import parser
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.widgets import AdminDateWidget
from django.utils.timezone import localdate
from django.template.response import TemplateResponse
from django import forms
from pytz import timezone

from . import models
from .google import calendar as client
from seekers.forms import MassTextForm
from seekers import tasks, constants


class HumanCalendarSubscriptionAdmin(admin.TabularInline):
    model = models.HumanCalendarSubscription
    extra = 1
    classes = ["collapse"]


def mass_text(modeladmin, request, queryset):
    if request.POST.get("submitted"):
        form_obj = MassTextForm(request.POST)
        if form_obj.is_valid():
            recipients = (
                models.HumanCalendarSubscription.objects.filter(calendar__in=queryset.values_list("pk", flat=True))
                .values_list("human", "contact_method")
                .distinct()
            )
            for human_id, contact_method in recipients:
                tasks.send_message.delay(
                    human_id,
                    contact_method,
                    form_obj.cleaned_data.get("sms_body" if contact_method == constants.SMS else "email_body"),
                    form_obj.cleaned_data.get("email_subject"),
                )
            modeladmin.message_user(request, f"Sending email/SMS to {len(recipients)} human(s).", messages.SUCCESS)
            return None
    else:
        form_obj = MassTextForm()
    context = dict(
        form=form_obj,
        queryset=queryset,
        title=f"Send mass communication to {modeladmin.model._meta.verbose_name_plural}",
        opts=modeladmin.model._meta,
        media=modeladmin.media,
    )
    return TemplateResponse(request, "admin/seekers/mass_text.html", context)


mass_text.short_description = "Send mass communication"


class CalendarAdmin(admin.ModelAdmin):
    model = models.Calendar
    actions = [mass_text]


class CheckinModelForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        try:
            event = client.get_event(cleaned_data["calendar_id"], cleaned_data["event_id"])
            if event.get("recurringEventId"):
                assert event.get("recurringEventid") == cleaned_data["recurring_event_id"]
        except (AssertionError, ValueError):
            raise forms.ValidationError("The event identifier given is invalid.")

    class Meta:
        model = models.HumanAttendance
        fields = ["human", "calendar", "event_id", "recurring_event_id"]


class DatePickerForm(forms.Form):
    event_date = forms.DateField(widget=AdminDateWidget())


class HumanAttendanceAdmin(admin.ModelAdmin):
    model = models.HumanAttendance
    autocomplete_fields = ["human"]
    hidden_fields = ["calendar", "event_id", "recurring_event_id"]

    def has_change_permission(self, request, obj=None):
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.hidden_fields:
            return db_field.formfield(widget=forms.HiddenInput(), **kwargs)
        else:
            return super().formfield_for_dbfield(db_field, request, **kwargs)

    def process_event(self, calendar_obj, event):
        local_tz = timezone(settings.TIME_ZONE)
        if "dateTime" in event["start"]:
            start_dt = parser.parse(event["start"]["dateTime"]).astimezone(local_tz)
            end_dt = parser.parse(event["end"]["dateTime"]).astimezone(local_tz)
        else:
            start_dt = parser.parse(event["start"]["date"]).astimezone(local_tz)
            end_dt = parser.parse(event["end"]["date"]).astimezone(local_tz)
        return dict(
            calendar_id=calendar_obj.calendar_id,
            summary=event["summary"],
            event_id=event["id"],
            location=event.get("location", ""),
            recurring_event_id=event.get("recurringEventId"),
            start_dt=start_dt,
            end_dt=end_dt,
        )

    def response_add(self, request, obj, post_url_continue=None):
        return super().response_add(request, obj, post_url_continue=request.get_full_path())

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}

        if "calendar" in request.GET and "event_id" in request.GET:
            # We're doing check-ins for the event
            calendar_id, event_id = request.GET["calendar"], request.GET["event_id"]
            event = client.get_event(calendar_id, event_id)
            extra_context.update(
                dict(
                    already_checked_in=self.model.objects.filter(calendar_id=calendar_id, event_id=event_id).order_by(
                        "-created"
                    ),
                    event=self.process_event(models.Calendar.objects.get(calendar_id=calendar_id), event),
                    stage="checkin",
                    title=f'Check in for {event["summary"]}',
                )
            )
            form_url += "?" + request.GET.urlencode()
        elif "past_event" in request.GET:
            extra_context.update(
                dict(
                    choose_date=True,
                    date_form=DatePickerForm(),
                    stage="pick_date",
                    title="Select date for event search",
                )
            )
        else:
            if "event_date" in request.GET:
                date = datetime.date(*map(int, request.GET["event_date"].split("-")))
            else:
                date = localdate()

            calendar_objs = models.Calendar.objects.filter(inactive_date__isnull=True, track_attendance=True)
            events = []
            local_tz = timezone(settings.TIME_ZONE)
            start_dt = local_tz.localize(datetime.datetime.combine(date, datetime.time(0)))
            end_dt = start_dt + datetime.timedelta(days=1)
            for calendar_obj in calendar_objs:
                for event in client.get_upcoming_events(calendar_obj.calendar_id, start_dt=start_dt, end_dt=end_dt):
                    events.append(self.process_event(calendar_obj, event))
            events.sort(key=lambda event: event["start_dt"])
            extra_context.update(
                dict(
                    upcoming_events=events,
                    event_date=date,
                    stage="pick_event",
                    title=f'Events available for check in on {date.strftime("%b %d, %Y")}',
                )
            )
        return super().changeform_view(request, object_id, form_url, extra_context)


admin.site.register(models.HumanAttendance, HumanAttendanceAdmin)
admin.site.register(models.Calendar, CalendarAdmin)
