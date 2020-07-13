import datetime
import logging
import re

from django.contrib.auth.models import User
from django.core.management import BaseCommand
from django.utils.timezone import now
from dateutil.parser import parse
import pytz

from events import models, google
from seekers.models import Human

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send the calendar autotext for the day"

    def add_arguments(self, parser):
        parser.add_argument(
            "--test-human", action="store", dest="test_human", help="Username of a user to send a test message to."
        )
        parser.add_argument("--sms-opening", action="store")
        parser.add_argument("--email-opening", action="store")
        parser.add_argument("--sms-only", action="store_true")
        parser.add_argument("--email-only", action="store_true")

    def normalize_event(self, event):
        begin = parse(event["start"]["dateTime"]).astimezone(pytz.timezone("US/Eastern"))
        end = parse(event["end"]["dateTime"]).astimezone(pytz.timezone("US/Eastern"))
        description = re.sub(r"\n+", "\n", event["description"].replace("<br>", "\n").replace("&nbsp;", " "))
        zoom_link = re.search(r"https://zoom\.us/j/[0-9]{10}", description)
        if zoom_link:
            hangout_link = zoom_link.group(0)
        else:
            hangout_link = event.get("hangoutLink", "")
        return dict(
            name=event["summary"],
            begin=begin,
            end=end,
            description=description,
            location=event.get("location"),
            hangoutLink=hangout_link,
        )

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
                subscriber.send_events_summary(
                    normalized_events,
                    extra_context=dict(
                        sms_opening=options.get("sms_opening"), email_opening=options.get("email_opening")
                    ),
                )
