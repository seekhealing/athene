import logging
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

from . import constants
from . import mailchimp


logger = logging.getLogger(__name__)


def id_gen():
    digits = string.digits + string.ascii_lowercase
    id_int = random.randint(0, (36 ** 4) - 1)
    id_str = ""
    power = 3
    while power >= 0:
        placevalue = id_int // (36 ** power)
        id_str += digits[placevalue]
        id_int -= placevalue * (36 ** power)
        power -= 1
    return id_str


CONTACT_PREFERENCES = [
    (constants.EMAIL, "Email"),
    (constants.SMS, "SMS"),
]


class Human(models.Model):
    id = models.CharField(max_length=4, primary_key=True, default=id_gen, editable=False)
    human = property(lambda self: self)
    first_names = models.CharField(max_length=120)
    last_names = models.CharField(max_length=120)
    email = models.EmailField(
        blank=True, error_messages=dict(unique="A person with this email is already in the system.")
    )
    phone_number = PhoneNumberField(
        blank=True, error_messages=dict(unique="A person with this phone number is already in the system.")
    )
    facebook_username = models.CharField(max_length=30, blank=True)
    facebook_alias = models.CharField(max_length=120, blank=True)
    birthdate = models.DateField(blank=True, null=True)
    sober_anniversary = models.DateField(blank=True, null=True)
    street_address = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=30, blank=True)
    state = USStateField(default="NC")
    zip_code = USZipCodeField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    contact_preference = models.IntegerField(choices=CONTACT_PREFERENCES, blank=True, null=True)
    first_conversation = models.DateField(blank=True, null=True)

    send_replies_to_channel = models.CharField(max_length=120, editable=False, blank=True, default="")

    def __str__(self):
        return f"{self.first_names} {self.last_names}"

    def upgrade_to_seeker(self):
        seeker = Seeker.objects.create(human=self, enroll_date=timezone.now().date(),)
        if self.email:
            status = mailchimp.client.subscription_status(self.email)
            if status["status"] == "subscribed":
                logger.info("Adding default Seeker tags to mailing list subscription.")
                current_tags = [tag["name"] for tag in status["tags"]]
                mailchimp.client.update_user_tags(
                    self.email, list(set(current_tags).union(set(settings.MAILCHIMP_DEFAULT_SEEKER_TAGS)))
                )
        return seeker

    def mark_as_community_partner(self):
        community_partner = CommunityPartner.objects.create(human=self)
        return community_partner

    def _get_unique_checks(self, exclude=None):
        # We want email and phone_number to be unique but we don't want to do so at the DB level because
        # we still need blank values
        unique_checks, date_checks = super()._get_unique_checks(exclude=exclude)
        if self.email:
            unique_checks.append((self.__class__, ("email",)))
        if self.phone_number:
            unique_checks.append((self.__class__, ("phone_number",)))
        return unique_checks, date_checks

    def find_ride(self):
        if not settings.GOOGLEMAPS_API:
            return []
        client = googlemaps.Client(key=settings.GOOGLEMAPS_API)
        ride_volunteers = Seeker.objects.filter(
            Q(ride_share=True) | Q(transportation=1), inactive_date__isnull=True, human__street_address__gt=""
        ).exclude(pk=self.id)
        result_rows = []
        for chunk in [ride_volunteers[i : i + 25] for i in range(0, len(ride_volunteers), 25)]:  # noqa: E203
            result = client.distance_matrix(
                origins=f"{self.street_address}, {self.zip_code}",
                destinations=[f"{obj.human.street_address}, {obj.human.zip_code}" for obj in chunk],
                mode="driving",
                units="imperial",
            )
            result_rows += result["rows"][0]["elements"]
        result_map = zip(ride_volunteers, result_rows)
        result_map = list(filter(lambda result: result[1]["status"] == "OK", result_map))
        result_map.sort(key=lambda result: result[1]["duration"]["value"])
        return [(result[0], result[1]) for result in result_map[:10]]

    class Meta:
        verbose_name = "Human"
        ordering = ["first_names", "last_names"]
        index_together = [("last_names", "first_names")]
        permissions = [
            ("can_send_masstext_to_one", "Can send individualized text/emails"),
            ("can_send_masstext_to_several", "Can send text/emails to several humans at once"),
            ("can_send_masstext_to_many", "Can send text/emails to lots of humans at once"),
        ]


class HumanMixin:
    def first_names(self):
        return self.human.first_names

    first_names.short_description = "First names"
    first_names.admin_order_field = "human__first_names"

    def last_names(self):
        return self.human.last_names

    last_names.short_description = "Last names"
    last_names.admin_order_field = "human__last_names"

    def email(self):
        return self.human.email

    email.short_description = "Email address"
    email.admin_order_field = "human__email"

    def phone_number(self):
        return self.human.phone_number

    phone_number.short_description = "Phone number"
    phone_number.admin_order_field = "human__phone_number"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.human.save(update_fields=["updated"])

    def __str__(self):
        return str(self.human)


TRANSPORTATION_CHOICES = [
    (1, "Has a car"),
    (2, "Public transit/Lyft"),
    (3, "Homebound"),
]


class SeekerNeedType(models.Model):
    need = models.CharField(max_length=40, unique=True)

    def __str__(self):
        return self.need

    class Meta:
        ordering = ["need"]


class Seeker(HumanMixin, models.Model):

    human = models.OneToOneField(Human, primary_key=True, db_column="human_ptr_id", on_delete=models.CASCADE)

    enroll_date = models.DateField(blank=True, null=True)
    inactive_date = models.DateField(blank=True, null=True)
    needs = models.ManyToManyField(SeekerNeedType, blank=True, null=True)
    lt_complete = models.DateField("Completed Listening Training", blank=True, null=True)

    def is_active(self):
        return self.inactive_date is None

    is_active.boolean = True
    is_active.short_description = "Active"

    seeker_pairings = models.ManyToManyField("self", through="SeekerPairing", symmetrical=False)

    ride_share = models.BooleanField(default=False)
    space_holder = models.BooleanField(default=False, verbose_name="Space Owl")
    facilitator = models.BooleanField(default=False)
    one_on_one_facilitator = models.BooleanField(default=False)
    listening_line = models.BooleanField(default=False)
    event_helper = models.BooleanField(default=False)
    donations_getter = models.BooleanField(default=False)
    food_maker = models.BooleanField(default=False)
    street_team = models.BooleanField(default=False)
    donor_thankyou_writer = models.BooleanField(default=False, verbose_name='Donor "Thank You" writer')
    donor_thankyou_caller = models.BooleanField(default=False, verbose_name='Donor "Thank You" caller')
    mediator = models.BooleanField(default=False)
    activity_buddy = models.BooleanField(default=False, verbose_name="Connection Mission worthy")
    outreach = models.BooleanField(default=False, verbose_name="Listening Booth volunteer")
    ready_to_pair = models.BooleanField(default=False)
    admin_human = models.BooleanField(default=False)
    creative_human = models.BooleanField(default=False)
    herbal_first_aid = models.BooleanField(default=False)
    connection_agent_organization = models.CharField(max_length=120, blank=True)

    def is_connection_agent(self):
        return bool(self.connection_agent_organization)

    is_connection_agent.boolean = True
    is_connection_agent.short_description = "Connection agent"

    transportation = models.IntegerField(choices=TRANSPORTATION_CHOICES, blank=True, null=True)

    @property
    def active_seeker_pairings(self):
        return SeekerPairing.objects.filter(Q(left=self) | Q(right=self), unpair_date__isnull=True)

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

    class Meta:
        ordering = ["human__first_names", "human__last_names"]


def today():
    return timezone.now().date()


class SeekerPairing(models.Model):
    left = models.ForeignKey(Seeker, on_delete=models.CASCADE, related_name="left_pair")
    right = models.ForeignKey(Seeker, on_delete=models.CASCADE, related_name="right_pair")
    pair_date = models.DateField(default=today)
    unpair_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)

    def clean(self):
        if self.left_id == self.right_id:
            raise ValidationError({"right": "You may not pair a seeker to themselves."})

    def __str__(self):
        return f"{self.left} paired with {self.right}"

    class Meta:
        ordering = ["pair_date"]


class SeekerPairingMeeting(models.Model):
    seeker_pairing = models.ForeignKey(SeekerPairing, on_delete=models.CASCADE)
    meeting_date = models.DateField(default=today)
    comment = models.CharField(max_length=200)

    def __str__(self):
        return f"Meeting for {self.seeker_pairing} on {self.meeting_date}"

    class Meta:
        ordering = ["-meeting_date"]


class HumanNote(models.Model):
    human = models.ForeignKey(Human, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, editable=False, null=True)
    note = RichTextField()

    STR_TEMPLATE = template.Template('{{ timestamp|date:"DATETIME_FORMAT" }} by {{ added_by|default:"Athene" }}')

    def __str__(self):
        return self.STR_TEMPLATE.render(template.Context(dict(timestamp=self.created, added_by=self.added_by)))

    class Meta:
        ordering = ("-created",)
        verbose_name = "Note"


class CommunityPartnerService(models.Model):
    service_code = models.CharField(max_length=15, primary_key=True)
    service_name = models.CharField(max_length=40, unique=True)

    def __str__(self):
        return self.service_name


class CommunityPartner(HumanMixin, models.Model):
    human = models.OneToOneField(Human, primary_key=True, db_column="human_ptr_id", on_delete=models.CASCADE)

    organization = models.CharField(max_length=120, blank=True)

    services = models.ManyToManyField(CommunityPartnerService)

    def __str__(self):
        return str(self.human)

    class Meta:
        ordering = ["human__first_names", "human__last_names"]
