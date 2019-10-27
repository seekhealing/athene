import logging
logger = logging.getLogger(__name__)

import decimal
import random
import string
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django import template
from django.utils import timezone

from ckeditor.fields import RichTextField
import googlemaps
from localflavor.us.models import USStateField, USZipCodeField
from phonenumber_field.modelfields import PhoneNumberField

from . import mailchimp


def id_gen():
    digits = string.digits + string.ascii_lowercase
    id_int = random.randint(0, (36 ** 4) - 1)
    id_str = ''
    power = 3
    while power >= 0:
        placevalue = id_int // (36 ** power)
        id_str += digits[placevalue]
        id_int -= (placevalue * (36 ** power))
        power -= 1
    return id_str

CONTACT_PREFERENCES = [
    (1, 'Email'),
    (2, 'SMS'),
    (3, 'Facebook')
]


class Human(models.Model):
    id = models.CharField(max_length=4, primary_key=True, default=id_gen, editable=False)
    first_names = models.CharField(max_length=120)
    last_names = models.CharField(max_length=120)
    email = models.EmailField(
        blank=True, error_messages=dict(unique='A person with this email is already in the system.'))
    phone_number = PhoneNumberField(
        blank=True, error_messages=dict(unique='A person with this phone number is already in the system.'))
    birthdate = models.DateField(blank=True, null=True)
    sober_anniversary = models.DateField(blank=True, null=True)
    street_address = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=30, blank=True)
    state = USStateField(default='NC')
    zip_code = USZipCodeField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    contact_preference = models.IntegerField(choices=CONTACT_PREFERENCES, blank=True, null=True)
    first_conversation = models.DateField(blank=True, null=True)
 
    def __str__(self):
        return f'{self.first_names} {self.last_names}'
    
    def upgrade_to_seeker(self):
        seeker = Seeker(human_ptr=self,
                        enroll_date=timezone.now().date(), 
                        **{field.name: getattr(self, field.name) for field in type(self)._meta.fields})
        seeker.save()
        if self.email:
            status = mailchimp.client.subscription_status(self.email)
            if status['status'] == 'subscribed':
                logger.info('Adding default Seeker tags to mailing list subscription.')
                current_tags = [tag['name'] for tag in status['tags']]
                mailchimp.client.update_user_tags(
                    self.email, list(set(current_tags).union(set(settings.MAILCHIMP_DEFAULT_SEEKER_TAGS))))
        return seeker
    
    def mark_as_community_partner(self):
        community_partner = CommunityPartner(
            human_ptr=self,
            **{field.name: getattr(self, field.name) for field in type(self)._meta.fields})
        community_partner.save()
        return community_partner
    
    def _get_unique_checks(self, exclude=None):
        # We want email and phone_number to be unique but we don't want to do so at the DB level because
        # we still need blank values
        unique_checks, date_checks = super()._get_unique_checks(exclude=exclude)
        if self.email:
            unique_checks.append((self.__class__, ('email',)))
        if self.phone_number:
            unique_checks.append((self.__class__, ('phone_number',)))
        return unique_checks, date_checks

    class Meta:
        verbose_name = 'Prospect'
        ordering = ['first_names', 'last_names']
        index_together = [('last_names', 'first_names')]

TRANSPORTATION_CHOICES = [
    (1, 'Has a car'),
    (2, 'Public transit/Lyft'),
    (3, 'Homebound'),
]


class Seeker(Human):

    enroll_date = models.DateField(blank=True, null=True)
    inactive_date = models.DateField(blank=True, null=True)

    def is_active(self):
        return self.inactive_date is None
    is_active.boolean = True
    is_active.short_description = 'Active'
    
    seeker_pairings = models.ManyToManyField('self', through='SeekerPairing',
                                             symmetrical=False)

    facebook_username = models.CharField(max_length=30, blank=True)
    facebook_alias = models.CharField(max_length=120, blank=True)

    listener_trained = models.BooleanField('Listener trained', editable=False, default=False)
    extra_care = models.BooleanField('Extra care program', editable=False, default=False)
    extra_care_graduate = models.BooleanField('Extra care graduate', editable=False, default=False)

    ride_share = models.BooleanField(default=False)
    space_holder = models.BooleanField(default=False)
    facilitator = models.BooleanField(default=False)
    activity_buddy = models.BooleanField(default=False)
    outreach = models.BooleanField(default=False)
    ready_to_pair = models.BooleanField(default=False)
    connection_agent_organization = models.CharField(max_length=120, blank=True)

    def is_connection_agent(self):
        return bool(self.connection_agent_organization)
    is_connection_agent.boolean = True
    is_connection_agent.short_description = 'Connection agent'

    transportation = models.IntegerField(choices=TRANSPORTATION_CHOICES,
                                         blank=True, null=True)

    @property
    def active_seeker_pairings(self):
        return SeekerPairing.objects.filter(
            Q(left=self)|Q(right=self),
            unpair_date__isnull=True
        )
    
    @property
    def seeker_pairs(self):
        pairings = self.active_seeker_pairings
        pairs = []
        for pairing in pairings:
            if pairing.left_id == self.id:
                pairs.append((pairing.id, pairing.right))
            else:
                pairs.append((pairing.id, pairing.left))
        return pairs
    
    def find_ride(self):
        if not settings.GOOGLEMAPS_API: return []
        client = googlemaps.Client(key=settings.GOOGLEMAPS_API)
        ride_volunteers = type(self).objects.filter(
            Q(ride_share=True) | Q(transportation=1),
            inactive_date__isnull=True,
            street_address__gt='').exclude(pk=self.id)
        result_rows = []
        for chunk in [ride_volunteers[i:i + 25] for i in range(0, len(ride_volunteers), 25)]:
            result = client.distance_matrix(
                origins=f'{self.street_address}, {self.zip_code}',
                destinations=[f'{obj.street_address}, {obj.zip_code}'
                              for obj in ride_volunteers],
                mode='driving', units='imperial'
            )
            result_rows += result['rows'][0]['elements']
        result_map = zip(ride_volunteers, result_rows)
        result_map = list(filter(lambda result: result[1]['status'] == 'OK', result_map))
        result_map.sort(key=lambda result: result[1]['duration']['value'])
        return [(result[0], result[1]) for result in result_map]


def today():
    return timezone.now().date()


class SeekerPairing(models.Model):
    left = models.ForeignKey(Seeker, on_delete=models.CASCADE, related_name='left_pair')
    right = models.ForeignKey(Seeker, on_delete=models.CASCADE, related_name='right_pair')
    pair_date = models.DateField(default=today)
    unpair_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)

    def clean(self):
        if self.left_id == self.right_id:
            raise ValidationError({'right': 'You may not pair a seeker to themselves.'})
        
    def __str__(self):
        return f'{self.left} paired with {self.right}'

    class Meta:
        ordering = ['pair_date']


class SeekerPairingMeeting(models.Model):
    seeker_pairing = models.ForeignKey(SeekerPairing, on_delete=models.CASCADE)
    meeting_date = models.DateField(default=today)
    comment = models.CharField(max_length=200)

    def __str__(self):
        return f'Meeting for {self.seeker_pairing} on {self.meeting_date}'
    
    class Meta:
        ordering = ['-meeting_date']


SEEKER_MILESTONES = [
    (1, 'Listening trained'),
    (2, 'Extra-care enrolled'),
    (3, 'Extra-care graduated')
]


class SeekerMilestone(models.Model):
    seeker = models.ForeignKey(Seeker, on_delete=models.CASCADE)
    date = models.DateField()
    milestone = models.IntegerField(choices=SEEKER_MILESTONES)

    def __str__(self):
        return f'{self.seeker} - {self.get_milestone_display()}'

    def save(self, *args, **kwargs):
        super(SeekerMilestone, self).save(*args, **kwargs)
        seeker_milestones = SeekerMilestone.objects.filter(
            seeker=self.seeker_id).values_list('milestone', flat=True)
        self.seeker.listener_trained = 1 in seeker_milestones
        self.seeker.extra_care = 2 in seeker_milestones and 3 not in seeker_milestones
        self.seeker.extra_care_graduate = 3 in seeker_milestones
        self.seeker.save()
    
    class Meta:
        ordering = ['date']
        verbose_name = 'Milestone'

class HumanNote(models.Model):
    human = models.ForeignKey(Human, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                 editable=False, null=True)
    note = RichTextField()

    STR_TEMPLATE = template.Template(
        '{{ timestamp|date:"DATETIME_FORMAT" }} by {{ added_by }}')
    def __str__(self):
        return self.STR_TEMPLATE.render(
            template.Context(
                dict(timestamp=self.created,
                      added_by=self.added_by)
            )
        )
    
    class Meta:
        ordering = ('-created',)
        verbose_name = 'Note'
    
class SeekerBenefitType(models.Model):
    name = models.CharField(max_length=120)
    default_cost = models.DecimalField(decimal_places=2, max_digits=5, blank=True, null=True)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ('name',)

class SeekerBenefit(models.Model):
    seeker = models.ForeignKey(Seeker, on_delete=models.CASCADE)
    benefit_type = models.ForeignKey(SeekerBenefitType, on_delete=models.CASCADE)
    cost = models.DecimalField(decimal_places=2, max_digits=5)
    date = models.DateField()

    def __str__(self):
        return f'{self.seeker} @ {self.benefit_type} on {self.date}'
    
    class Meta:
        ordering = ('-date',)

# A proxy model to register a special admin class just for managing seeker benefits
class SeekerBenefitProxy(Seeker):

    def this_month(self):
        qs = self.seekerbenefit_set.filter(date__month=timezone.now().month).select_related()
        result = qs.aggregate(total_cost=models.Sum('cost'))
        return result['total_cost']
    
    def all_time(self):
        qs = self.seekerbenefit_set.all().select_related()
        result = qs.aggregate(total_cost=models.Sum('cost'))
        return result['total_cost']

    class Meta:
        proxy = True
        verbose_name = 'Seeker benefit report'

class CommunityPartner(Human):
    organization = models.CharField(max_length=120, blank=True)
