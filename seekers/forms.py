from django.conf import settings
from django import forms


class MassTextForm(forms.Form):
    email_subject = forms.CharField(label="Email subject", help_text=("For people who prefer email delivery."))

    email_body = forms.CharField(
        label="Email body",
        help_text="For people who prefer email delivery.",
        widget=forms.Textarea(attrs=dict(rows=10, cols=120)),
    )

    sms_body = forms.CharField(
        label="SMS body",
        help_text="For people who prefer SMS delivery.",
        widget=forms.Textarea(attrs=dict(rows=10, cols=120)),
    )

    reply_to_channel = forms.ChoiceField(
        choices=[(channel, channel) for channel in settings.SLACK_WEBHOOK_MAP],
        initial=settings.DEFAULT_SLACK_CHANNEL,
        label="Send replies to",
    )
