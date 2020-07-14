import hashlib
import hmac
import logging
import os
import re

from django.http import HttpResponse
from django.conf import settings
from django.views.decorators import csrf, http
import phonenumbers
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator

from .models import Human
from . import slack

logger = logging.getLogger(__name__)
MAILGUN_SIGNING_KEY = os.environ.get("MAILGUN_WEBHOOK_SIGNING_KEY")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")


@http.require_POST
@csrf.csrf_exempt
def mailgun_webhook(request):
    if not (MAILGUN_SIGNING_KEY or settings.MAILGUN_BYPASS_SIGNATURE):
        return HttpResponse(status=501, content="Webhook signing key not set.")

    # Verify signature
    try:
        hmac_digest = hmac.new(
            key=MAILGUN_SIGNING_KEY.encode(),
            msg=f'{request.POST["timestamp"]}{request.POST["token"]}'.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        assert hmac.compare_digest(str(request.POST["signature"]), str(hmac_digest))
    except (KeyError, AssertionError):
        if (not settings.MAILGUN_BYPASS_SIGNATURE) or (not settings.DEBUG):
            return HttpResponse(status=400, content="Signature verification failed.")

    sender = request.POST["from"]
    if "<" in sender:
        match_obj = re.search(r".*<([^>]+)>", sender)
        sender_email = match_obj.group(1)
    else:
        sender_email = sender
    try:
        human_obj = Human.objects.get(email__iexact=sender_email)
    except Human.DoesNotExist:
        slack.forward_unknown_message(sender, request.POST["stripped-text"])
    else:
        slack.forward_mass_text_reply(human_obj, request.POST["stripped-text"])
        human_obj.send_replies_to_channel = ""
        human_obj.save()

    return HttpResponse(status=200, content="Message accepted.")


@http.require_POST
@csrf.csrf_exempt
def twilio_webhook(request):
    if not TWILIO_AUTH_TOKEN:
        return HttpResponse(status=501, content="Webhook auth token not set.")

    validator = RequestValidator(TWILIO_AUTH_TOKEN)

    # Validate the request using its URL, POST data,
    # and X-TWILIO-SIGNATURE header
    request_valid = validator.validate(
        request.build_absolute_uri(), request.POST, request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
    )

    # Continue processing the request if it's valid, return a 403 error if
    # it's not
    if not request_valid:
        logger.error(
            f'Twilio signature failed: {request.build_absolute_uri()} + {request.POST} vs {request.META.get("HTTP_X_TWILIO_SIGNATURE")}'
        )
        if not (settings.DEBUG or settings.TWILIO_BYPASS_SIGNATURE):
            return HttpResponse(status=403, content="Signature verification failed")

    resp = MessagingResponse()

    sender = request.POST["From"]
    phone_obj = phonenumbers.parse(sender, "US")
    localized_phone_number = phonenumbers.format_number(phone_obj, phonenumbers.PhoneNumberFormat.NATIONAL)
    try:
        human_obj = Human.objects.get(phone_number=localized_phone_number)
    except Human.DoesNotExist:
        slack.forward_unknown_message(localized_phone_number, request.POST["Body"])
    else:
        slack.forward_mass_text_reply(human_obj, request.POST["Body"])
        human_obj.send_replies_to_channel = ""
        human_obj.save()

    resp.message("Thank you for your reply! We have forwarded it on to our staff.")

    # Return the TwiML
    return HttpResponse(resp)
