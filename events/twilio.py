import logging
logger = logging.getLogger(__name__)

import os

import requests

class SMS(object):
    def __init__(self):
        self.username = os.environ.get('TWILIO_API_USERNAME')
        self.auth = requests.auth.HTTPBasicAuth(
            username=self.username,
            password=os.environ.get('TWILIO_API_PASSWORD'))
        self.my_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')

    def send_text(self, recipient, content, test=False):
        try:
            logger.info(f'Sending SMS to {recipient}')
            if test:
                logger.debug('Test SMS content:')
                logger.debug(f'{content}')
            else:
                response = requests.post(
                    f'https://api.twilio.com/2010-04-01/Accounts/{self.username}/Messages.json',
                    data={'To': recipient,
                         'From': self.my_phone_number,
                         'Body': content},
                    auth=self.auth)
                response.raise_for_status()
        except requests.RequestException as e:
            logger.exception('Error communicating with Twilio!')
            if e.response.text:
                logger.error(f'Twilio error: {e.response.text}')

sms = SMS()