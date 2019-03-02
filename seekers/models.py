import random
import string
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from ckeditor.fields import RichTextField
from localflavor.us.models import USStateField
from phonenumber_field.modelfields import PhoneNumberField


def seeker_id_gen():
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

class Seeker(models.Model):
    id = models.CharField(max_length=4, primary_key=True, default=seeker_id_gen, editable=False)
    first_names = models.CharField(max_length=120)
    last_names = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone_number = PhoneNumberField(blank=True)
    city = models.CharField(max_length=30, blank=True)
    state = USStateField(default='NC')
    birthdate = models.DateField(blank=True, null=True)
    sober_anniversary = models.DateField(blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    inactive_date = models.DateField(blank=True, null=True)

    def is_active(self):
        return self.inactive_date is None
    is_active.boolean = True
    
    seeker_pairings = models.ManyToManyField('self', through='SeekerPairing',
                                             symmetrical=False)

    facebook_username = models.CharField(max_length=30, blank=True)
    facebook_alias = models.CharField(max_length=120, blank=True)

    contact_preference = models.IntegerField(choices=CONTACT_PREFERENCES, blank=True, null=True)

    listener_trained = models.BooleanField('Listener trained?', editable=False, default=False)
    extra_care = models.BooleanField('Extra care program?', editable=False, default=False)
    extra_care_graduate = models.BooleanField('Extra care graduate?', editable=False, default=False)

    def __str__(self):
        return f'{self.first_names} {self.last_names}'

    @property
    def seeker_pairing(self):
        try:
            pairing = SeekerPairing.objects.filter(
                Q(left=self)|Q(right=self),
                unpair_date__isnull=True
            )[0]
        except IndexError:
            return None
        else:
            return pairing
    
    @property
    def seeker_pair(self):
        pairing = self.seeker_pairing
        if not pairing:
            return None
        if pairing.left_id == self.id:
            return pairing.right
        else:
            return pairing.left

    class Meta:
        ordering = ['last_names', 'first_names']
        unique_together = [('last_names', 'first_names', 'birthdate')]

class SeekerPairing(models.Model):
    left = models.ForeignKey(Seeker, on_delete=models.CASCADE, related_name='left_pair')
    right = models.ForeignKey(Seeker, on_delete=models.CASCADE, related_name='right_pair')
    pair_date = models.DateField(auto_now=True)
    unpair_date = models.DateField(blank=True, null=True)

    def clean(self):
        if self.left_id == self.right_id:
            raise ValidationError({'right': 'You may not pair a seeker to themselves.'})
        if not self.id and not self.unpair_date:
            if self.left.seeker_pairing:
                raise ValidationError({'left': 'This seeker already has an active pairing.'})
            if self.right.seeker_pairing:
                raise ValidationError({'right': 'This seeker already has an active pairing'})

    def __str__(self):
        return f'{self.left} paired with {self.right}'

    class Meta:
        ordering = ['pair_date']

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

class SeekerNote(models.Model):
    seeker = models.ForeignKey(Seeker, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                 editable=False, null=True)
    note = RichTextField()

    def __str__(self):
        timestamp = self.created.strftime("%Y-%m-%d %H:%M:%S")
        words = self.note.split(' ')[:10]
        lead_in = ' '.join(words[:10])
        if len(words) > 10:
            lead_in += '...'
        return f'{timestamp} by {self.added_by}: {lead_in}'
    

