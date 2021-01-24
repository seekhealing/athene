import datetime
import logging
import re

from django.contrib.auth.models import User
from django.core.management import BaseCommand
from django.utils.timezone import now
from dateutil.parser import parse
import pytz
import usaddress

from events import models, google
from seekers.models import Human

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send the calendar autotext for the day"

    def add_arguments(self, parser):
        parser.add_argument(
            "--test-human", action="store", dest="test_human", help="Username of a user to send a test message to."
        )
        parser.add_argument("--sms-only", action="store_true")
        parser.add_argument("--email-only", action="store_true")

    tag_mapping = {
        "Recipient": "recipient",
        "AddressNumber": "address",
        "AddressNumberPrefix": "address",
        "AddressNumberSuffix": "address",
        "StreetName": "address",
        "StreetNamePreDirectional": "address",
        "StreetNamePreModifier": "address",
        "StreetNamePreType": "address",
        "StreetNamePostDirectional": "address",
        "StreetNamePostModifier": "address",
        "StreetNamePostType": "address",
        "CornerOf": "address",
        "IntersectionSeparator": "address",
        "LandmarkName": "recipient",
        "USPSBoxGroupID": "address",
        "USPSBoxGroupType": "address",
        "USPSBoxID": "address",
        "USPSBoxType": "address",
        "BuildingName": "recipient",
        "OccupancyType": "address",
        "OccupancyIdentifier": "address",
        "SubaddressIdentifier": "address",
        "SubaddressType": "address",
        "PlaceName": "city",
        "StateName": "state",
        "ZipCode": "zip_code",
    }

    def normalize_event(self, event):
        start_dt = parse(event["start"]["dateTime"]).astimezone(pytz.timezone("US/Eastern"))
        try:
            end_dt = parse(event["end"]["dateTime"]).astimezone(pytz.timezone("US/Eastern"))
        except KeyError:
            end_dt = None
        description = re.sub(r"\n+", "\n", event.get("description", "").replace("<br>", "\n").replace("&nbsp;", " "))
        # Location could be an place+address or a URL
        location = event.get("location", "").strip()
        if location and not location.startswith(("https://", "http://")):
            location_parts, _ = usaddress.tag(event.get("location"), tag_mapping=self.tag_mapping)
            location_name = location_parts.get("recipient", "")
            location_place = location_parts.get("address", "")
        else:
            location_name = location_place = ""
        to_return = event.copy()
        to_return.update(
            dict(
                start_dt=start_dt,
                end_dt=end_dt,
                description=description,
                location_name=location_name,
                location_place=location_place,
            )
        )
        return to_return

    def handle(self, *args, **options):
        client = google.Calendar()
        for calendar_obj in models.Calendar.objects.filter(inactive_date__isnull=True):
            if not (calendar_obj.send_autotext_days and calendar_obj.autotext_days_in_advance):
                logger.info(f"Skipping calendar {calendar_obj} - autotext disabled.")
                continue
            if now().strftime("%w") not in calendar_obj.send_autotext_days:
                if options["test_human"]:
                    logger.info(f"Ordinarily {calendar_obj} would not send a text today, but this is a test.")
                else:
                    logger.info(f'Skipping calendar {calendar_obj} - autotext does not run on {now().strftime("%A")}')
                    continue
            event_horizon = now() + datetime.timedelta(days=calendar_obj.autotext_days_in_advance)
            events = client.get_upcoming_events(calendar_obj.calendar_id, end_dt=event_horizon)
            if not events:
                logger.warning(
                    f"No events in the next {calendar_obj.autotext_days_in_advance} days for {calendar_obj}"
                )
                continue
            normalized_events = [self.normalize_event(event) for event in events if "dateTime" in event["start"]]
            if options["sms_only"]:
                allowed_contact_methods = [2]
            elif options["email_only"]:
                allowed_contact_methods = [1]
            else:
                allowed_contact_methods = [1, 2]
            if options["test_human"]:
                test_user = User.objects.get(username=options["test_human"])
                test_human = Human.objects.get(email=test_user.email)
                logger.info(f"Sending test messages to {test_human}")
                subscribers = [
                    models.HumanCalendarSubscription(
                        calendar=calendar_obj, human=test_human, contact_method=contact_method
                    )
                    for contact_method in allowed_contact_methods
                ]
            else:
                subscribers = calendar_obj.humancalendarsubscription_set.filter(
                    contact_method__in=allowed_contact_methods
                )
            for subscriber in subscribers:
                subscriber.send_events_summary(normalized_events)
            calendar_obj.email_opening_override = ""
            calendar_obj.email_closing_override = ""
            calendar_obj.sms_opening_override = ""
            calendar_obj.sms_closing_override = ""
            calendar_obj.save()
