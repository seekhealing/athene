from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail
import requests
import requests.exceptions

from .models import Human, HumanNote
from .constants import EMAIL, SMS
from . import twilio


logger = get_task_logger(__name__)


@shared_task
def send_message(
    sender_id, human_id, contact_method, message, subject=None, reply_to_channel=settings.DEFAULT_SLACK_CHANNEL
):
    human_obj = Human.objects.get(id=human_id)
    if contact_method == EMAIL:
        if not human_obj.email:
            logger.warning(f"Tried sending message to {human_obj} via email but has no email address")
            return
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [human_obj.email])
    elif contact_method == SMS:
        if not human_obj.phone_number:
            logger.warning(f"Tried sending message to {human_obj} via SMS but has no phone number")
            return
        twilio.sms.send_text(str(human_obj.phone_number), message)
    human_obj.send_replies_to_channel = reply_to_channel
    human_obj.save(force_update=True)
    if sender_id:
        HumanNote.objects.create(
            human=human_obj, added_by_id=sender_id, note=f"<p>Sent a message through Athene:<p><pre>{message}</pre>"
        )


@shared_task
def async_request(method, *args, retry_count=3, **kwargs):
    if "timeout" not in kwargs:
        kwargs["timeout"] = 3.0
    try:
        response = requests.request(method, *args, **kwargs)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        if retry_count:
            logger.warning(f"Timeout during {method.upper()} to {args[0]}. Queueing for retry.")
            retry_count -= 1
            async_request.s(method, *args, retry_count=retry_count, **kwargs).apply_async(countdown=60 * 5)
        else:
            logger.error(f"Timeout during {method.upper()} to {args[0]}. No more retries. Giving up.")
    except requests.exceptions.HTTPError:
        if response.status_code // 100 == 5:
            if retry_count:
                logger.warning(
                    f"HTTP error during {method.upper()} to {args[0]}: ({response.status_code}) {response.text} - Queueing for retry."
                )
                retry_count -= 1
                async_request.s(method, *args, retry_count=retry_count, **kwargs).apply_async(countdown=60 * 5)
            else:
                logger.error(
                    f"HTTP error during {method.upper()} to {args[0]}: ({response.status_code}) {response.text} - No more retries. Giving up."
                )
        else:
            logger.error(f"HTTP error during {method.upper()} to {args[0]}: ({response.status_code}) {response.text}")
