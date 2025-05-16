from django import forms
from django.utils import timezone
from .models import XRayImage, PredictionHistory, UserProfile
from django.contrib.auth.models import User

class XRayUploadForm(forms.ModelForm):
    class Meta:
        model = XRayImage
        fields = ['image', 'first_name', 'last_name', 'patient_id', 'gender', 
                 'date_of_birth', 'date_of_xray', 'additional_info']
        widgets = {
            'date_of_birth': forms.TextInput(attrs={'placeholder': 'YYYY-MM-DD'}),
            'date_of_xray': forms.TextInput(attrs={'placeholder': 'YYYY-MM-DD', 'value': timezone.now().strftime('%Y-%m-%d')}),
            'gender': forms.Select(choices=[('', '--Select--'), ('male', 'Male'), ('female', 'Female'), ('other', 'Other')]),
            'additional_info': forms.Textarea(attrs={'rows': 3}),
        }

class PredictionHistoryFilterForm(forms.Form):
    gender = forms.ChoiceField(
        choices=[('', 'All'), ('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        required=False
    )
    age_min = forms.IntegerField(required=False, min_value=0, max_value=120, 
                                label="Minimum Age",
                                widget=forms.NumberInput(attrs={'placeholder': 'Min Age'}))
    age_max = forms.IntegerField(required=False, min_value=0, max_value=120, 
                                label="Maximum Age",
                                widget=forms.NumberInput(attrs={'placeholder': 'Max Age'}))
    date_min = forms.DateField(required=False, 
                              label="From Date",
                              widget=forms.TextInput(attrs={'placeholder': 'YYYY-MM-DD'}))
    date_max = forms.DateField(required=False, 
                              label="To Date",
                              widget=forms.TextInput(attrs={'placeholder': 'YYYY-MM-DD'}))
    pathology = forms.ChoiceField(
        choices=[], 
        required=False,
        label="Pathology"
    )
    pathology_threshold = forms.FloatField(
        required=False, 
        min_value=0.0, 
        max_value=1.0,
        label="Minimum Probability",
        initial=0.5,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate pathology choices dynamically
        pathology_choices = [
            ('', 'All'),
            ('atelectasis', 'Atelectasis'),
            ('cardiomegaly', 'Cardiomegaly'),
            ('consolidation', 'Consolidation'),
            ('edema', 'Edema'),
            ('effusion', 'Effusion'),
            ('emphysema', 'Emphysema'),
            ('fibrosis', 'Fibrosis'),
            ('hernia', 'Hernia'),
            ('infiltration', 'Infiltration'),
            ('mass', 'Mass'),
            ('nodule', 'Nodule'),
            ('pleural_thickening', 'Pleural Thickening'),
            ('pneumonia', 'Pneumonia'),
            ('pneumothorax', 'Pneumothorax'),
            ('fracture', 'Fracture'),
            ('lung_opacity', 'Lung Opacity'),
            ('enlarged_cardiomediastinum', 'Enlarged Cardiomediastinum'),
            ('lung_lesion', 'Lung Lesion')
        ]
        self.fields['pathology'].choices = pathology_choices 

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'preferred_theme', 
            'preferred_language', 
            'dashboard_view', 
            'email_notifications',
            'processing_complete_notification',
            'two_factor_auth_enabled'
        ]
        widgets = {
            'preferred_theme': forms.Select(attrs={'class': 'form-select'}),
            'preferred_language': forms.Select(attrs={'class': 'form-select'}),
            'dashboard_view': forms.Select(attrs={'class': 'form-select'}),
        }

class UserInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Current Password"
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="New Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirm New Password"
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if not self.user.check_password(current_password):
            raise forms.ValidationError("Incorrect current password")
        return current_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', "Passwords don't match")
        
        return cleaned_data 