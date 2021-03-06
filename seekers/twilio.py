import logging
import os

from django.conf import settings
import requests


logger = logging.getLogger(__name__)


class SMS(object):
    def __init__(self):
        self.username = os.environ.get("TWILIO_API_USERNAME")
        if self.username:
            self.auth = requests.auth.HTTPBasicAuth(
                username=self.username, password=os.environ.get("TWILIO_API_PASSWORD")
            )
            self.my_phone_number = os.environ.get("TWILIO_PHONE_NUMBER")
        else:
            self.auth = self.my_phone_number = None

    def send_text(self, recipient, content):
        try:
            logger.info(f"Sending SMS to {recipient}")
            if settings.DEBUG or not self.auth:
                logger.info(f"{content}")
            else:
                response = requests.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{self.username}/Messages.json",
                    data={"To": recipient, "From": self.my_phone_number, "Body": content},
                    auth=self.auth,
                )
                response.raise_for_status()
        except requests.RequestException as e:
            logger.exception("Error communicating with Twilio!")
            if e.response.text:
                logger.error(f"Twilio error: {e.response.text}")


sms = SMS()
