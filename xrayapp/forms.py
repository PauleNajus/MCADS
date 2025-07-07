from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
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
            'additional_info': forms.Textarea(attrs={'rows': 3, 'maxlength': 1000}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add file validation
        self.fields['image'].validators.append(
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'bmp', 'tiff'])
        )
        # Add input length limits for security
        self.fields['first_name'].widget.attrs.update({'maxlength': 100})
        self.fields['last_name'].widget.attrs.update({'maxlength': 100})
        self.fields['patient_id'].widget.attrs.update({'maxlength': 100})
    
    def clean_image(self):
        """Validate uploaded image file"""
        image = self.cleaned_data.get('image')
        if not image:
            return image
            
        # Check file size (max 10MB)
        if image.size > 10 * 1024 * 1024:
            raise ValidationError('Image file too large. Maximum size is 10MB.')
        
        # Check MIME type for security if magic is available
        if MAGIC_AVAILABLE:
            try:
                file_mime = magic.from_buffer(image.read(), mime=True)
                image.seek(0)  # Reset file pointer
                
                allowed_mimes = [
                    'image/jpeg', 'image/jpg', 'image/png', 
                    'image/bmp', 'image/tiff', 'image/x-ms-bmp'
                ]
                
                if file_mime not in allowed_mimes:
                    raise ValidationError('Invalid file type. Only image files are allowed.')
            except Exception:
                # If magic fails, rely on Django's validation
                pass
            
        return image
    
    def clean_first_name(self):
        """Sanitize first name input"""
        first_name = self.cleaned_data.get('first_name', '').strip()
        if first_name and not first_name.replace(' ', '').replace('-', '').replace("'", '').isalpha():
            raise ValidationError('First name should only contain letters, spaces, hyphens, and apostrophes.')
        return first_name
    
    def clean_last_name(self):
        """Sanitize last name input"""
        last_name = self.cleaned_data.get('last_name', '').strip()
        if last_name and not last_name.replace(' ', '').replace('-', '').replace("'", '').isalpha():
            raise ValidationError('Last name should only contain letters, spaces, hyphens, and apostrophes.')
        return last_name
    
    def clean_patient_id(self):
        """Validate patient ID format"""
        patient_id = self.cleaned_data.get('patient_id', '').strip()
        if patient_id and not patient_id.replace('-', '').replace('_', '').isalnum():
            raise ValidationError('Patient ID should only contain letters, numbers, hyphens, and underscores.')
        return patient_id
    
    def clean_date_of_birth(self):
        """Validate date of birth"""
        dob = self.cleaned_data.get('date_of_birth')
        if dob and dob > timezone.now().date():
            raise ValidationError('Date of birth cannot be in the future.')
        if dob and (timezone.now().date() - dob).days > 365 * 150:  # 150 years max
            raise ValidationError('Date of birth seems too old.')
        return dob
    
    def clean_date_of_xray(self):
        """Validate X-ray date"""
        xray_date = self.cleaned_data.get('date_of_xray')
        if xray_date and xray_date > timezone.now().date():
            raise ValidationError('X-ray date cannot be in the future.')
        return xray_date


class PredictionHistoryFilterForm(forms.Form):
    gender = forms.ChoiceField(
        choices=[('', 'All'), ('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        required=False
    )
    age_min = forms.IntegerField(required=False, min_value=0, max_value=150, 
                                label="Minimum Age",
                                widget=forms.NumberInput(attrs={'placeholder': 'Min Age'}))
    age_max = forms.IntegerField(required=False, min_value=0, max_value=150, 
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
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        age_min = cleaned_data.get('age_min')
        age_max = cleaned_data.get('age_max')
        date_min = cleaned_data.get('date_min')
        date_max = cleaned_data.get('date_max')
        
        if age_min is not None and age_max is not None and age_min > age_max:
            raise ValidationError('Minimum age cannot be greater than maximum age.')
        
        if date_min and date_max and date_min > date_max:
            raise ValidationError('Start date cannot be after end date.')
            
        return cleaned_data


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
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 30}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 30}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
    
    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if email:
            # Check if email is already taken by another user
            existing_user = User.objects.filter(email=email).exclude(id=self.instance.id).first()
            if existing_user:
                raise ValidationError('This email address is already in use.')
        return email


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Current Password"
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="New Password",
        min_length=8
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
            raise ValidationError("Incorrect current password")
        return current_password
    
    def clean_new_password(self):
        """Validate new password strength"""
        new_password = self.cleaned_data.get('new_password')
        if new_password:
            # Check for common patterns
            if new_password.lower() in ['password', '12345678', 'qwerty']:
                raise ValidationError("Password is too common.")
            
            # Check for at least one digit and one letter
            if not any(c.isdigit() for c in new_password):
                raise ValidationError("Password must contain at least one digit.")
            
            if not any(c.isalpha() for c in new_password):
                raise ValidationError("Password must contain at least one letter.")
                
        return new_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', "Passwords don't match")
        
        return cleaned_data 