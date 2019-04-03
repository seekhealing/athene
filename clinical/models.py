from django.db import models
from django.contrib.postgres.fields import ArrayField

from ckeditor.fields import RichTextField

SUBSTANCE_BOND_CHOICES = [
    (0, 'Alcohol'),
    (1, 'IV drug user'),
    (2, 'Heroin (nasal, smoking, or IV)'),
    (3, 'Fentanyl'),
    (4, 'Pharmaceutical opioids (i.e. "pain pills")'),
    (5, 'MAT opioids (e.g. methadone, buprenorphine/suboxone)'),
    (6, 'Powder cocaine'),
    (7, 'Crack cocaine'),
    (8, 'Methamphetamine'),
    (9, 'Pharmaceutical amphetamines (e.g. Adderall, Ritalin)'),
    (10, 'Cannabis/marijuana'),
    (11, 'Kratom'),
    (12, 'Caffeine'),
    (13, 'Sugar'),
    (14, 'Other')
]

NON_SUBSTANCE_BOND_CHOICES = [
    (0, 'Social media'),
    (1, 'Gambling'),
    (2, 'Work'),
    (3, 'Video games'),
    (4, 'Eating disorder(s)'),
    (5, 'Netflix binging'),
    (6, 'Sex'),
    (7, 'Porn'),
    (8, 'Self-harm'),
    (9, 'Other')
]

HEALING_INTENTIONS = [
    (0, '100% abstinence free from all mind-altering substances'),
    (1, 'Abstinence from one or more substances, moderation with others'),
    (2, 'Use methadone, buprenorphine/suboxone, or kratom to taper down to abstinence from opioids'),
    (3, 'Use methadone, buprenorphine/suboxone, or kratom to maintain a safer opioid bond'),
    (4, 'Other')
]

CONNECTION_CAPACITY_CHOICES = [
    (1, "1 - There is no one in my life that I could talk with about things "
        "I'm ashamed of. my social anxiety makes it almost impossible to "
        "connect with new people"),
] + \
[(i, str(i)) for i in range(2, 10)] + \
[
    (10, "10 - I have multiple people I can share anything with and feel "
         "capable of creating new authentic connections with strangers.")
]

class SeekerIntakeData(models.Model):
    seeker = models.OneToOneField('seekers.Seeker', unique=True, on_delete=models.CASCADE)
    why_are_you_here = RichTextField(
        blank=True,
        verbose_name='What attracts you to SeekHealing?',
        help_text=('Why are you here, and what do you want to get 
                   'out of being involved in this program & community?')
    )
    are_you_a_seeker = RichTextField(
        blank=True,
        verbose_name='Do you consider yourself a seeker?',
        help_text=("A seeker is simply someone who has made a commitment "
                   "to healing: to constantly re-evaluating your relationship "
                   "with behavior(s) that don't serve you. That may involve "
                   "overcoming a chemical addiction, or it may not.")
    )
    substance_use_history = models.TypedChoiceField(
        coerce=lambda x: x =='True', 
        choices=((False, 'No'), (True, 'Yes')), 
        widget=forms.RadioSelect,
        verbose_name='Do you have a substance use history?',
        help_text=(
            'Note: it is not required that you answer "yes" in order to join '
            'the program. If you have dealt with other addictions not related '
            "to substance use, answer no here (we'll get that info from ya in "
            "a couple questions)")
    )

    substance_bonds = ArrayField(
        models.IntegerField,
        blank=True
    )

    non_substance_bonds = ArrayField(
        models.IntegerField,
        blank=True
    )

    current_intentions = ArrayField(
        models=IntegerField,
        blank=True
    )

    other_intentions = RichTextField(
        verbose_name='What are your other intentions for healing & personal growth?',
        blank=True
    )

    connection_capacity = models.IntegerField(
        verbose_name="On a scale of 1 to 10, how would you rate your capacity "
                     "for connection in your life?",
        choices=CONNECTION_CAPACITY_CHOICES,
        null=True, blank=True
    )

    connection_count = models.PositiveIntegerField(
        verbose_name="How many people in your life do you trust enough to "
                     "share absolutely anything with?",
        null=True, blank=True
    )