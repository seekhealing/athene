from datetime import timedelta
import logging

from ckeditor.fields import RichTextField
from django import template
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.utils import timezone
from localflavor.us.models import USStateField, USZipCodeField
from phonenumber_field.modelfields import PhoneNumberField

from events.models import HumanAttendance
from seekers.models import Human, HumanMixin
from .constants import INTAKE_EVENTS, RELEASE_EVENTS


logger = logging.getLogger(__name__)
EXTRACARE_STATUS = [("active", "Active"), ("inactive", "Inactive"), ("complete", "Complete")]


class ExtraCare(HumanMixin, models.Model):
    human = models.OneToOneField(Human, primary_key=True, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=EXTRACARE_STATUS, default="inactive")
    current_program_flow = models.PositiveIntegerField(default=1)

    _recent_events_attended = None
    _threshold_date = None

    @property
    def recent_events_attended(self):
        if not self._recent_events_attended:
            now = timezone.localtime()
            this_morning = now.replace(hour=0, minute=0, second=0, microsecond=0)
            # The Monday before last
            self._threshold_date = this_morning - timedelta(days=this_morning.weekday() + 7)
            self._recent_events_attended = HumanAttendance.objects.filter(
                start_time__gt=self._threshold_date, human_id=self.human_id
            ).count()
        return self._recent_events_attended, self._threshold_date

    def completed_events(self):
        return self.progressevent_set.filter(complete=True).order_by("id")

    def exit_early(self):
        ProgressEvent.objects.create(
            extracare=self,
            program_flow=self.current_program_flow,
            event_type="Exited program early",
            phase="exited",
            occurred=timezone.now().date(),
            complete=True,
        )
        self.current_program_flow += 1
        # A signal will inactivate this person
        self.save()

    class Meta:
        verbose_name = "Extra Care participant"


class ExtraCareNote(models.Model):
    extracare = models.ForeignKey(ExtraCare, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, editable=False, null=True)
    note = RichTextField()

    STR_TEMPLATE = template.Template('{{ timestamp|date:"DATETIME_FORMAT" }} by {{ added_by|default:"Athene" }}')

    def __str__(self):
        return self.STR_TEMPLATE.render(template.Context(dict(timestamp=self.created, added_by=self.added_by)))

    class Meta:
        ordering = ("-created",)
        verbose_name = "Note"


class ConnectionAgent(models.Model):
    name = models.CharField(max_length=80, unique=True)
    point_of_contact = models.CharField(max_length=120, blank=True)
    street_address = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=30, blank=True)
    state = USStateField(default="NC")
    zip_code = USZipCodeField(blank=True)
    email = models.EmailField(
        blank=True, error_messages=dict(unique="A person with this email is already in the system.")
    )
    phone_number = PhoneNumberField(
        blank=True, error_messages=dict(unique="A person with this phone number is already in the system.")
    )

    def __str__(self):
        return self.name


class ExtraCareBenefitType(models.Model):
    name = models.CharField(max_length=120)
    connectionagent = models.ForeignKey(ConnectionAgent, null=True, blank=True, on_delete=models.SET_NULL)
    default_cost = models.DecimalField(decimal_places=2, max_digits=5, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = (
            "connectionagent",
            "name",
        )
        verbose_name = "Extra Care benefit type"


class ExtraCareBenefit(models.Model):
    extracare = models.ForeignKey(ExtraCare, on_delete=models.CASCADE)
    benefit_type = models.ForeignKey(ExtraCareBenefitType, on_delete=models.CASCADE)
    cost = models.DecimalField(decimal_places=2, max_digits=5)
    scheduled = models.DateField()
    rescheduled_count = models.PositiveIntegerField(default=0, editable=False)
    date = models.DateField(blank=True, null=True)
    cancelled = models.DateField(blank=True, null=True)

    @classmethod
    def from_db(cls, db, field_names, values):
        # Default implementation of from_db() (subject to change and could
        # be replaced with super()).
        if len(values) != len(cls._meta.concrete_fields):
            values = list(values)
            values.reverse()
            values = [values.pop() if f.attname in field_names else models.DEFERRED for f in cls._meta.concrete_fields]
        instance = cls(*values)
        instance._state.adding = False
        instance._state.db = db
        # customization to store the original field values on the instance
        instance._loaded_values = dict(zip(field_names, values))
        return instance

    def clean(self):
        if self.date and self.cancelled:
            raise ValidationError("A benefit cannot both have occurred and be cancelled.")
        tomorrow = timezone.now().date() + timedelta(days=1)
        if (self.date and self.date > tomorrow) or (self.cancelled and self.cancelled > tomorrow):
            raise ValidationError("You cannot use a future date for when a benefit was given.")
        if not self._state.adding:
            if (
                self._loaded_values["scheduled"]
                and self.scheduled
                and self.scheduled != self._loaded_values["scheduled"]
            ):
                self.rescheduled_count += 1

    def __str__(self):
        return f"{self.extracare} @ {self.benefit_type} on {self.scheduled or self.date}"

    class Meta:
        ordering = ("-date",)


# A proxy model to register a special admin class just for managing ECP benefits
class ExtraCareBenefitProxy(ExtraCare):
    def this_month(self):
        qs = self.extracarebenefit_set.filter(
            Q(date__isnull=False) | Q(cancelled__isnull=False), date__month=timezone.now().month
        ).select_related()
        result = qs.aggregate(total_cost=models.Sum("cost"))
        return result["total_cost"]

    def all_time(self):
        qs = self.extracarebenefit_set.filter(Q(date__isnull=False) | Q(cancelled__isnull=False)).select_related()
        result = qs.aggregate(total_cost=models.Sum("cost"))
        return result["total_cost"]

    class Meta:
        proxy = True
        verbose_name = "Extra Care benefit report"


class ProgressEvent(models.Model):
    extracare = models.ForeignKey(ExtraCare, on_delete=models.CASCADE)
    program_flow = models.PositiveIntegerField()
    event_type = models.CharField(max_length=40)
    phase = models.CharField(max_length=20)
    scheduled = models.DateField(blank=True, null=True)
    rescheduled_count = models.PositiveIntegerField(editable=False, default=0)
    occurred = models.DateField(blank=True, null=True)
    excused = models.DateField(blank=True, null=True)
    note = models.TextField(blank=True)
    complete = models.BooleanField(editable=False, default=False)

    @classmethod
    def from_db(cls, db, field_names, values):
        # Default implementation of from_db() (subject to change and could
        # be replaced with super()).
        if len(values) != len(cls._meta.concrete_fields):
            values = list(values)
            values.reverse()
            values = [values.pop() if f.attname in field_names else models.DEFERRED for f in cls._meta.concrete_fields]
        instance = cls(*values)
        instance._state.adding = False
        instance._state.db = db
        # customization to store the original field values on the instance
        instance._loaded_values = dict(zip(field_names, values))
        return instance

    def clean(self):
        if self.occurred and self.excused:
            raise ValidationError("The event either occurred or was excused, but not both.")
        for field in ["occurred", "excused"]:
            if getattr(self, field) and getattr(self, field) > timezone.now().date() + timedelta(days=1):
                if not settings.DEBUG:
                    raise ValidationError("Events cannot be marked complete with a future date.")
                else:
                    logger.warning("Event allowed to be marked complete in the future because DEBUG is on.")
        if not self._state.adding:
            if (
                self._loaded_values["scheduled"]
                and self.scheduled
                and (self.scheduled != self._loaded_values["scheduled"])
            ):
                self.rescheduled_count += 1

    def __str__(self):
        return f"{self.event_type} - {self.extracare}"

    class Meta:
        ordering = ["id"]


def update_extracare_status(sender=None, instance=None, **kwargs):
    if instance.status != "complete":
        # If there are no events in flight, we're inactive
        # If there are some events in flight, but not a full set of release events, we're active
        # If there are events in flight and it's complete, so are we
        events = instance.progressevent_set.filter(program_flow=instance.current_program_flow)
        if events:
            for event_type, _ in RELEASE_EVENTS:
                if not any([e for e in events if e.event_type == event_type and e.complete]):
                    instance.status = "active"
                    return
            ProgressEvent.objects.create(
                extracare=instance,
                program_flow=instance.current_program_flow,
                event_type="Completed",
                phase="completed",
                occurred=max([e.occurred or e.excused for e in events]),
                complete=True,
            )
            instance.status = "complete"
        else:
            instance.status = "inactive"


def update_progressevents(sender=None, instance=None, **kwargs):
    if instance.occurred or instance.excused:
        instance.complete = True
    if instance.event_type == INTAKE_EVENTS[-1][0] and instance.complete:
        # Get rid of any optional events. Trust formset validation to handle the rest.
        sender.objects.filter(
            extracare=instance.extracare,
            program_flow=instance.program_flow,
            complete=False,
            event_type__in=[p[0] for p in INTAKE_EVENTS],
        ).delete()


signals.pre_save.connect(update_extracare_status, sender=ExtraCare)
signals.pre_save.connect(update_progressevents, sender=ProgressEvent)
