from django import forms
from .models import WorkoutRequest

# Workout Request Template here
class WorkoutRequestForm(forms.ModelForm):
    max_participants = forms.IntegerField(
        initial=2,
        min_value=2,
        widget=forms.NumberInput(attrs={'min': 2}),
        help_text="Minimum 2 participants (including yourself)",
        label="Maximum Participants"
    )
    
    class Meta:
        model = WorkoutRequest
        fields = ['date', 'time', 'body_part', 'experience_level', 'max_participants']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
        }