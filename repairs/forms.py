from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import ItemCategory, PartDonation, PartUsage, RepairAssignment, RepairFeedback, RepairRequest, RepairSession, SparePart, User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.REQUESTER
        if commit:
            user.save()
        return user


class RequestForm(forms.ModelForm):
    class Meta:
        model = RepairRequest
        fields = ('category', 'item_name', 'description')
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = RepairAssignment
        fields = ('volunteer', 'notes')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['volunteer'].queryset = User.objects.filter(role=User.Role.VOLUNTEER, is_active=True)


class SessionForm(forms.ModelForm):
    class Meta:
        model = RepairSession
        fields = ('started_at', 'ended_at', 'findings', 'outcome')
        widgets = {
            'started_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'ended_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'findings': forms.Textarea(attrs={'rows': 3}),
            'outcome': forms.Textarea(attrs={'rows': 3}),
        }
    def clean(self):
        data = super().clean()
        if data.get('started_at') and data['started_at'] > timezone.now():
            self.add_error('started_at', 'Start time cannot be in the future.')
        if data.get('ended_at') and data.get('started_at') and data['ended_at'] < data['started_at']:
            self.add_error('ended_at', 'End time must follow start time.')
        return data


class PartForm(forms.ModelForm):
    class Meta:
        model = SparePart
        fields = ('name', 'unit', 'reorder_level')


class DonationForm(forms.ModelForm):
    class Meta:
        model = PartDonation
        fields = ('part', 'donor', 'quantity', 'notes')


class UsageForm(forms.ModelForm):
    class Meta:
        model = PartUsage
        fields = ('part', 'quantity')


class CategoryForm(forms.ModelForm):
    class Meta:
        model = ItemCategory
        fields = ('name', 'description')


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = RepairFeedback
        fields = ('rating', 'comment')
        widgets = {'rating': forms.Select(choices=[(i, str(i)) for i in range(1, 6)]),
                   'comment': forms.Textarea(attrs={'rows': 3})}
