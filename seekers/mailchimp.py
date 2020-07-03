import logging
import hashlib

from django.conf import settings
import mailchimp3
from mailchimp3.mailchimpclient import MailChimpError


logger = logging.getLogger(__name__)


class MailChimp(object):
    def __init__(self):
        if settings.MAILCHIMP_API_KEY is not None:
            self.client = mailchimp3.MailChimp(mc_api=settings.MAILCHIMP_API_KEY, mc_user=settings.MAILCHIMP_USERNAME)
        else:
            self.client = None
        self.list_id = settings.MAILCHIMP_LIST_ID

    def subscription_status(self, email):
        if not self.client:
            return {"status": "mailchip-unconfigured"}
        subscriber_hash = hashlib.md5(email.lower().encode("utf8")).hexdigest()
        try:
            status = self.client.lists.members.get(
                list_id=self.list_id,
                subscriber_hash=subscriber_hash,
                fields="id,email_address,status,unsubscribe_reason,merge_fields,tags",
            )
        except MailChimpError:
            return {"status": "never-subscribed"}
        else:
            return status

    def subscribe_user(self, first_names, last_names, email, tags):
        if not self.client:
            logger.warning("Mailchimp is not properly configured.")
        else:
            try:
                self.client.lists.members.create(
                    list_id=self.list_id,
                    data=dict(
                        email_address=email,
                        status="subscribed",
                        merge_fields=dict(FNAME=first_names, LNAME=last_names),
                        tags=tags,
                    ),
                )
            except MailChimpError:
                logger.exception(f"Error subscribing user {email} to list.")
        return self.subscription_status(email)

    def update_user_tags(self, email, tags):
        if not self.client:
            logger.warning("Mailchimp is not properly configured.")
        else:
            subscriber_hash = hashlib.md5(email.lower().encode("utf8")).hexdigest()
            tag_map = [
                {"name": tag, "status": "active" if tag in tags else "inactive"} for tag in settings.MAILCHIMP_TAGS
            ]
            try:
                self.client.lists.members.tags.update(
                    list_id=self.list_id, subscriber_hash=subscriber_hash, data=dict(tags=tag_map)
                )
            except MailChimpError:
                logger.exception(f"Error updating user tags for {email}.")
        return self.subscription_status(email)


client = MailChimp()
