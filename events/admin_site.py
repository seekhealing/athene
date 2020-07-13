class EventsAdminSiteMixin(object):
    pass


"""
import datetime

from dateutil import parser
from django.conf import settings
from django.contrib.admin.widgets import AutocompleteSelect
from django.contrib import messages
from django import forms
from django.forms.models import modelform_factory
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path
from pytz import utc, timezone

from .forms import SeekerAttendanceModelForm
from .models import Calendar, SeekerAttendance
from .google import client


class EventsAdminSiteMixin(object):
    def get_urls(self):
        base_urls = super().get_urls()
        urls = [
            path('events/checkin/', self.admin_view(self.checkin_list)),
            path('events/checkin/<calendar_id>/<event_id>/', self.checkin_event),
        ]
        return urls + base_urls

    def checkin_list(self, request):
        calendar_objs = Calendar.objects.filter(inactive_date__isnull=True,
                                                track_attendance=True)
        upcoming_events = []
        now = utc.localize(datetime.datetime.utcnow())
        tomorrow = now + datetime.timedelta(days=1)
        local_tz = timezone(settings.TIME_ZONE)
        for calendar_obj in calendar_objs:
            for event in client.get_upcoming_events(calendar_obj.calendar_id,
                                                    start_dt=now,
                                                    end_dt=tomorrow):
                upcoming_events.append(
                    dict(
                        calendar_id=calendar_obj.calendar_id,
                        summary=event['summary'],
                        event_id=event['id'],
                        recurring_event_id=event.get('recurringEventId'),
                        start_dt=parser.parse(event['start']['dateTime']).astimezone(local_tz),
                        end_dt=parser.parse(event['end']['dateTime']).astimezone(local_tz)
                    )
                )
        upcoming_events.sort(key=lambda event: event['start_dt'])
        context = dict(
            self.each_context(request),
            upcoming_events=upcoming_events
        )
        return TemplateResponse(request, "events/checkin_list.html", context)

    def get_checkin_form(self):
        def callback(db_field, **kwargs):
            new_kwargs = kwargs.copy()
            if db_field.name == 'seeker':
                new_kwargs['widget'] = AutocompleteSelect(db_field.remote_field, self)
            return db_field.formfield(**new_kwargs)
        return modelform_factory(
            SeekerAttendance,
            form=SeekerAttendanceModelForm,
            fields=forms.ALL_FIELDS,
            exclude=None,
            formfield_callback=callback
        )

    def checkin_event(self, request, calendar_id, event_id):
        try:
            event = client.get_event(calendar_id, event_id)
        except ValueError:
            raise Http404('Unknown event')
        if datetime.datetime.utcnow().astimezone(utc) - parser.parse(event['end']['dateTime']) > datetime.timedelta(seconds=60*60):
            messages.add_message(request, messages.ERROR, "Event has already ended.")
            return HttpResponseRedirect('../..')
        if request.method == 'POST':
            form_obj = SeekerAttendanceModelForm(request.POST)
            if form_obj.is_valid():
                form_obj.save()
        form_obj = self.get_checkin_form()(
            initial=dict(calendar=calendar_id,
                         event_id=event_id,
                         recurring_event_id=event.get('recurringEventId')))
        already_checked_in = SeekerAttendance.objects.filter(calendar_id=calendar_id,
                                                             event_id=event_id).order_by('-created')
        context = dict(
            self.each_context(request),
            already_checked_in=already_checked_in,
            event=event,
            form_obj=form_obj,
            opts=SeekerAttendance._meta,
            app_label=SeekerAttendance._meta.app_label,
        )
        return TemplateResponse(request, "events/checkin_form.html", context)
"""
