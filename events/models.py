import logging

from dateutil import parser as dt_parser
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template import Context, Template, loader
from django.utils.functional import cached_property
from django.utils.timezone import now
from multiselectfield import MultiSelectField
from pytz import timezone

from seekers import tasks, constants
from . import google

logger = logging.getLogger(__name__)

DAYS_OF_WEEK = [
    (0, "Sunday"),
    (1, "Monday"),
    (2, "Tuesday"),
    (3, "Wednesday"),
    (4, "Thursday"),
    (5, "Friday"),
    (6, "Saturday"),
]

CHANNEL_CHOICES = [(channel, channel) for channel in settings.SLACK_WEBHOOK_MAP.keys()]


class Calendar(models.Model):
    calendar_id = models.CharField(max_length=250, primary_key=True)
    name = models.CharField(max_length=120, editable=False)
    inactive_date = models.DateField(blank=True, null=True)
    track_attendance = models.BooleanField(default=False)
    send_autotext_days = MultiSelectField(choices=DAYS_OF_WEEK, blank=True)
    autotext_days_in_advance = models.PositiveIntegerField(null=True, blank=True)
    replies_go_to = models.CharField(max_length=40, choices=CHANNEL_CHOICES, default="#rides")
    default_email_opening = models.TextField(
        blank=True, default="", help_text="Prepended to autotext emails - break lines at 80 columns"
    )
    email_opening_override = models.TextField(
        blank=True,
        default="",
        help_text="One-time override to email opening - reset after next autotext - break lines at 80 columns",
    )
    default_sms_opening = models.TextField(
        blank=True,
        default="",
        help_text="Prepended to autotext SMS - be efficient with content - do not break lines unnecessarily",
    )
    sms_opening_override = models.TextField(
        blank=True,
        default="",
        help_text="One-time override to SMS opening - be efficient with content - do not break lines unnecessarily.",
    )
    default_email_closing = models.TextField(
        blank=True, default="", help_text="Appended after autotext emails - break lines at 80 columns"
    )
    email_closing_override = models.TextField(
        blank=True,
        default="",
        help_text="One-time override to email closing - reset after next autotext - break lines at 80 columns",
    )
    default_sms_closing = models.TextField(
        blank=True,
        default="",
        help_text="Appended after autotext SMS - be efficient with content - do not break lines unnecessarily",
    )
    sms_closing_override = models.TextField(
        blank=True,
        default="",
        help_text="One-time override to SMS closing - be efficient with content - do not break lines unnecessarily.",
    )

    def __str__(self):
        return self.name

    def clean(self):
        try:
            calendar_obj = google.calendar.get_calendar(self.calendar_id)
        except ValueError as e:
            raise ValidationError({"calendar_id", e.args[0]})
        else:
            self.name = calendar_obj["summary"]

    class Meta:
        permissions = [("can_send_to_subscribers", "Can send messages to calendar subscribers")]


class CalendarEvent(models.Model):
    id = models.CharField(max_length=120, primary_key=True)
    summary = models.CharField(max_length=200, blank=True, default="")
    start_time = models.DateTimeField(blank=True, null=True)
    recurring_event_id = models.CharField(max_length=120, null=True, db_index=True)
    last_updated = models.DateTimeField(blank=True, null=True)
    json = models.JSONField(default=dict)

    def __str__(self):
        return self.summary

    @classmethod
    def cache(cls, event):
        start_time = dt_parser.parse(event["start"].get("dateTime", event["start"].get("date")))
        if not start_time.tzinfo:
            start_time = start_time.astimezone(timezone(settings.TIME_ZONE))
        with transaction.atomic():
            event_obj, created = cls.objects.get_or_create(
                id=event["id"],
                defaults=dict(
                    summary=event["summary"],
                    start_time=start_time,
                    recurring_event_id=event.get("recurringEventId"),
                    last_updated=dt_parser.parse(event["updated"]),
                    json=event,
                ),
            )
            if not created and event_obj.last_updated < dt_parser.parse(event["updated"]):
                event_obj.summary = event["summary"]
                event_obj.start_time = start_time
                event_obj.last_updated = dt_parser.parse(event["updated"])
                event_obj.json = event
                event_obj.save(force_update=True)
        return event_obj, created


class HumanAttendance(models.Model):
    human = models.ForeignKey("seekers.Human", verbose_name="Attendee", on_delete=models.CASCADE)
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    event_id = models.CharField(max_length=120, db_index=True)
    start_time = models.DateTimeField(editable=False, blank=True, null=True)
    legacy_recurring_event_id = models.CharField(
        max_length=120, db_column="recurring_event_id", blank=True, db_index=True
    )
    created = models.DateTimeField(auto_now_add=True)

    @cached_property
    def event(self):
        if not self.event_id:
            return {}
        try:
            event_obj = google.calendar.get_event(self.calendar.calendar_id, self.event_id)
        except ValueError:
            return {}
        return event_obj

    def __str__(self):
        try:
            related_event = CalendarEvent.objects.get(id=self.event_id)
        except CalendarEvent.DoesNotExist:
            related_event, _ = CalendarEvent.cache(self.event)
        return f'{self.human} went to {related_event.summary or "Unknown event"}'

    def save(self, *args, **kwargs):
        if self.start_time is None and self.event_id:
            try:
                event = CalendarEvent.objects.get(id=self.event_id)
            except CalendarEvent.DoesNotExist:
                pass
            else:
                self.start_time = event.start_time
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Event attendance"
        verbose_name_plural = "Event attendance"
        unique_together = [("human", "calendar", "event_id")]


CONTACT_PREFERENCES = [
    (constants.EMAIL, "Email"),
    (constants.SMS, "SMS"),
]


class HumanCalendarSubscription(models.Model):
    human = models.ForeignKey("seekers.Human", on_delete=models.CASCADE)
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    contact_method = models.IntegerField(choices=CONTACT_PREFERENCES)

    def __str__(self):
        return f"{self.human} subscribed to {self.calendar}"

    def send_events_summary(self, events, extra_context=None):
        logger.debug(f"Sending to event summary to {self.human} via {self.get_contact_method_display()}")
        extra_context = extra_context or dict()
        context = dict(human=self.human, events=events, calendar=self.calendar, **extra_context)
        template_path = f"events/autotext/{self.get_contact_method_display().lower()}.txt"
        template_obj = loader.get_template(template_path)
        content = template_obj.render(context)
        today = Template('{{ timestamp|date:"DATE_FORMAT" }}').render(Context(dict(timestamp=now())))
        email_subject = f"Upcoming {self.calendar.name} - {today}"
        tasks.send_message.delay(
            None, self.human.id, self.contact_method, content, email_subject, self.calendar.replies_go_to
        )

    class Meta:
        unique_together = [("human", "calendar")]
        verbose_name = "Calendar subscription"
