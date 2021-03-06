import logging
import json
import os

from django.conf import settings

from . import tasks

logger = logging.getLogger(__name__)

WEBHOOK_MAP = json.loads(os.environ.get("SLACK_WEBHOOK_MAP", "{}"))


def send_message_to_channel(channel, basic_text, blocks, sync=False):
    logger.info(f"Sending message to {channel}: {basic_text}")
    if sync:
        tasks.async_request("POST", WEBHOOK_MAP[channel], json=dict(text=basic_text, blocks=blocks), retry_count=0)
    else:
        tasks.async_request.delay(
            "POST", WEBHOOK_MAP[channel], json=dict(text=basic_text, blocks=blocks), retry_count=0
        )


def forward_mass_text_reply(human_obj, reply_text):
    channel = human_obj.send_replies_to_channel or settings.DEFAULT_SLACK_CHANNEL
    basic_text = f"Reply received from {human_obj} to mass communications: {reply_text}"
    if human_obj.phone_number:
        formatted_phone_number = human_obj.phone_number.as_national
    else:
        formatted_phone_number = "Unknown"
    blocks = [
        dict(
            type="section",
            text=dict(
                type="mrkdwn",
                text=f"Hello, *{channel}*! We received a reply to a recent mass communications over email/SMS.",
            ),
        ),
        dict(type="divider"),
        dict(
            type="section",
            text=dict(
                type="mrkdwn",
                text=(
                    f"From: {human_obj.first_names} {human_obj.last_names}\n\n"
                    f"Phone number: {formatted_phone_number}\n\n"
                    f'Email address: {human_obj.email if human_obj.email else "Unknown"}\n\n'
                    f"Message:\n\n"
                    f"```{reply_text}```"
                ),
            ),
        ),
    ]
    send_message_to_channel(channel, basic_text, blocks)


def forward_unknown_message(sender_id, message_text):
    channel = settings.DEFAULT_SLACK_CHANNEL
    basic_text = f"Reply received from {sender_id} to mass communications: {message_text}"
    blocks = [
        dict(
            type="section",
            text=dict(
                type="mrkdwn",
                text=f"Hello, *{channel}*! We received a message from an unfamiliar sender over email/SMS.",
            ),
        ),
        dict(type="divider"),
        dict(
            type="section",
            text=dict(type="mrkdwn", text=(f"From: {sender_id}\n\n" f"Message:\n\n" f"```{message_text}```")),
        ),
    ]
    send_message_to_channel(channel, basic_text, blocks)
