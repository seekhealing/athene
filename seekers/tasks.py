from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail

from .models import Human
from .constants import EMAIL, SMS
from . import twilio


logger = get_task_logger(__name__)


@shared_task
def send_message(human_id, contact_method, message, subject=None):
    human_obj = Human.objects.get(id=human_id)
    if contact_method == EMAIL:
        if not human_obj.email:
            logger.warning(f'Tried sending message to {human_obj} via email but has no email address')
            return
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [human_obj.email])
    elif contact_method == SMS:
        if not human_obj.phone_number:
            logger.warning(f'Tried sending message to {human_obj} via SMS but has no phone number')
            return
        twilio.sms.send_text(str(human_obj.phone_number), message)
