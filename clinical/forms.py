from django import forms

from seekers import models as seekers
from clinical import models as clinical

class StepOne(forms.ModelForm):
    model = seekers.Seeker
    fields = ('first_names', 'last_names', 'pronouns')

class StepTwo(forms.ModelForm):
    model = seekers.Seeker
    fields = ('phone_number', 'email', 'street_address', 'city', 'state', 'zip_code')

class StepThree(forms.ModelForm):
    model = seekers.Seeker
    fields = ('birthdate',)

class StepFour(forms.ModelForm):
    model = clinical.SeekerIntakeData
    fields = ('why_are_you_here', 'are_you_a_seeker')

class StepFive(forms.ModelForm):
    model = clinical.SeekerIntakeData
    fields = ('substance_use_history', 'substance_bonds', 'non_substance_bonds')

class StepSix(forms.ModelForm):
    model = clinical.SeekerIntakeData
    fields = ('current_intentions', 'other_intentions')

class StepSeven(forms.ModelForm):
    model = clinical.SeekerIntakeData
    fields = ('connection_capacity', 'connection_count')

class StepEight(forms.ModelForm):
    model = clinical.SeekerIntakeData
    fields = ('life_confidence', 'thriving_confidence')

class StepNine(forms.ModelForm):
    model = clinical.SeekerIntakeData
    fields = ('connection_booster',)


