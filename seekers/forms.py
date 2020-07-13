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
