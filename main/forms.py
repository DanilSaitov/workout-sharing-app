from django import forms
from .models import WorkoutRequest

# Workout Request Template here
class WorkoutRequestForm(forms.ModelForm):
    class Meta:
        model = WorkoutRequest
        fields = ['date', 'time', 'body_part', 'experience_level']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
        }