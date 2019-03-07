from django.db import models
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from multiselectfield import MultiSelectField

from . import google

DAYS_OF_WEEK = [
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday')
]

class Calendar(models.Model):
    calendar_id = models.CharField(max_length=250, primary_key=True)
    name = models.CharField(max_length=120, editable=False)
    inactive_date = models.DateField(blank=True, null=True)
    track_attendance = models.BooleanField(default=False)
    send_autotext_days = MultiSelectField(choices=DAYS_OF_WEEK, blank=True)
    send_autotext_time = models.TimeField(blank=True, null=True)

    def __str__(self):
        return self.name
    
    def clean(self):
        try:
            calendar_obj = google.client.get_calendar(self.calendar_id)
        except ValueError as e:
            raise ValidationError({'calendar_id', e.args[0]})
        else:
            self.name = calendar_obj['summary']
    

class HumanAttendance(models.Model):
    human = models.ForeignKey('seekers.Human', verbose_name='Attendee', on_delete=models.CASCADE)
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    event_id = models.CharField(max_length=120, db_index=True)
    recurring_event_id = models.CharField(max_length=120, blank=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True)

    @cached_property
    def event(self):
        if not self.event_id:
            return None
        event_obj = google.client.get_event(self.calendar.calendar_id, self.event_id)
        return event_obj
    
    def __str__(self):
        return f'{self.human} went to {self.event["summary"]}'
    
    class Meta:
        verbose_name = 'Event attendance'
        verbose_name_plural = 'Event attendance'
        unique_together = [('human', 'calendar', 'event_id')]

CONTACT_PREFERENCES = [
    (1, 'Email'),
    (2, 'SMS'),
    # (3, 'Facebook')
]

class SeekerCalendarSubscription(models.Model):
    seeker = models.ForeignKey('seekers.Seeker', on_delete=models.CASCADE)
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    contact_method = models.IntegerField(choices=CONTACT_PREFERENCES)

    def __str__(self):
        return f'{self.seeker} subscribed to {self.calendar}'
    
    class Meta:
        unique_together = [('seeker', 'calendar')]