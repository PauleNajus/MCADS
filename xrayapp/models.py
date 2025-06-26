from django.db import models
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

# User Roles Choices
USER_ROLES = [
    ('Administrator', 'Administrator'),
    ('Radiographer', 'Radiographer'),
    ('Technologist', 'Technologist'),
    ('Radiologist', 'Radiologist'),
]

# Create your models here.

class XRayImage(models.Model):
    """Model to store X-ray images and analysis results"""
    # User who uploaded the image
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='xray_images', null=True, db_index=True)
    
    # Patient Information
    first_name = models.CharField(max_length=100, blank=True, db_index=True)
    last_name = models.CharField(max_length=100, blank=True, db_index=True)
    patient_id = models.CharField(max_length=100, blank=True, db_index=True)
    gender = models.CharField(max_length=10, blank=True, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True, db_index=True)
    date_of_xray = models.DateField(null=True, blank=True, db_index=True)
    additional_info = models.TextField(blank=True)
    
    # X-ray image and processing
    image = models.ImageField(upload_to='xrays/')
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processing_status = models.CharField(max_length=20, default='pending', db_index=True)
    progress = models.IntegerField(default=0)
    
    # Image metadata
    image_format = models.CharField(max_length=10, blank=True)  # e.g., 'JPEG', 'PNG'
    image_size = models.CharField(max_length=20, blank=True)    # e.g., '2.4 MB'
    image_resolution = models.CharField(max_length=20, blank=True)  # e.g., '1024x768'
    image_date_created = models.DateTimeField(null=True, blank=True)
    
    # Interpretability visualizations
    has_gradcam = models.BooleanField(default=False, db_index=True)
    gradcam_visualization = models.CharField(max_length=255, null=True, blank=True)
    gradcam_heatmap = models.CharField(max_length=255, null=True, blank=True)
    gradcam_overlay = models.CharField(max_length=255, null=True, blank=True)
    gradcam_target_class = models.CharField(max_length=50, null=True, blank=True)
    
    has_pli = models.BooleanField(default=False, db_index=True)
    pli_visualization = models.CharField(max_length=255, null=True, blank=True)
    pli_overlay_visualization = models.CharField(max_length=255, null=True, blank=True)
    pli_saliency_map = models.CharField(max_length=255, null=True, blank=True)
    pli_target_class = models.CharField(max_length=50, null=True, blank=True)
    
    # Predicted pathologies (values range from 0.0 to 1.0)
    atelectasis = models.FloatField(null=True, blank=True, db_index=True)
    cardiomegaly = models.FloatField(null=True, blank=True, db_index=True)
    consolidation = models.FloatField(null=True, blank=True, db_index=True)
    edema = models.FloatField(null=True, blank=True, db_index=True)
    effusion = models.FloatField(null=True, blank=True, db_index=True)
    emphysema = models.FloatField(null=True, blank=True, db_index=True)
    fibrosis = models.FloatField(null=True, blank=True, db_index=True)
    hernia = models.FloatField(null=True, blank=True, db_index=True)
    infiltration = models.FloatField(null=True, blank=True, db_index=True)
    mass = models.FloatField(null=True, blank=True, db_index=True)
    nodule = models.FloatField(null=True, blank=True, db_index=True)
    pleural_thickening = models.FloatField(null=True, blank=True, db_index=True)
    pneumonia = models.FloatField(null=True, blank=True, db_index=True)
    pneumothorax = models.FloatField(null=True, blank=True, db_index=True)
    fracture = models.FloatField(null=True, blank=True, db_index=True)
    lung_opacity = models.FloatField(null=True, blank=True, db_index=True)
    enlarged_cardiomediastinum = models.FloatField(null=True, blank=True, db_index=True)
    lung_lesion = models.FloatField(null=True, blank=True, db_index=True)
    support_devices = models.FloatField(null=True, blank=True, db_index=True)
    
    # Severity level
    severity_level = models.IntegerField(null=True, blank=True, db_index=True)
    
    class Meta:
        # Add composite indexes for commonly queried combinations
        indexes = [
            models.Index(fields=['user', 'uploaded_at']),
            models.Index(fields=['processing_status', 'uploaded_at']),
            models.Index(fields=['patient_id', 'date_of_xray']),
            models.Index(fields=['gender', 'date_of_birth']),
            models.Index(fields=['severity_level', 'uploaded_at']),
        ]
        # Optimize database table order
        ordering = ['-uploaded_at']
    
    @property
    def calculate_severity_level(self):
        """Calculate severity level based on average of pathology probabilities
        1: Insignificant findings (0-19%)
        2: Moderate findings (20-30%)
        3: Significant findings (31-100%)
        """
        pathology_fields = {
            'atelectasis': self.atelectasis,
            'cardiomegaly': self.cardiomegaly,
            'consolidation': self.consolidation,
            'edema': self.edema,
            'effusion': self.effusion,
            'emphysema': self.emphysema,
            'fibrosis': self.fibrosis,
            'hernia': self.hernia,
            'infiltration': self.infiltration,
            'mass': self.mass,
            'nodule': self.nodule,
            'pleural_thickening': self.pleural_thickening,
            'pneumonia': self.pneumonia,
            'pneumothorax': self.pneumothorax,
            'fracture': self.fracture,
            'lung_opacity': self.lung_opacity,
            'enlarged_cardiomediastinum': self.enlarged_cardiomediastinum,
            'lung_lesion': self.lung_lesion,
            'support_devices': self.support_devices,
        }
        
        # Filter out None values
        valid_values = [v for v in pathology_fields.values() if v is not None]
        
        if not valid_values:
            return None
        
        # Calculate average probability
        avg_probability = sum(valid_values) / len(valid_values)
        
        # Determine severity level
        if avg_probability <= 0.19:  # 0-19%
            return 1
        elif avg_probability <= 0.30:  # 20-30%
            return 2
        else:  # 31-100%
            return 3
    
    @property
    def severity_label(self):
        """Get severity level label"""
        severity_mapping = {
            1: "Insignificant findings",
            2: "Moderate findings",
            3: "Significant findings",
        }
        level = self.severity_level
        if level is None:
            level = self.calculate_severity_level
            
        return severity_mapping.get(level, "Unknown")
    
    def __str__(self):
        if self.patient_id and (self.first_name or self.last_name):
            return f"{self.first_name} {self.last_name} (ID: {self.patient_id}) - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"
        return f"X-ray #{self.id} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"
        
    def get_patient_display(self):
        """Return formatted patient information"""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return "Unknown patient"


class PredictionHistory(models.Model):
    """Model to store prediction history with filtering capabilities"""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='prediction_history', null=True, db_index=True)
    xray = models.ForeignKey(XRayImage, on_delete=models.CASCADE, related_name='prediction_history', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    model_used = models.CharField(max_length=50, db_index=True)  # densenet, resnet, etc.
    
    # Filters
    filter_by_gender = models.CharField(max_length=10, blank=True, db_index=True)
    filter_by_age_min = models.IntegerField(null=True, blank=True)
    filter_by_age_max = models.IntegerField(null=True, blank=True)
    filter_by_date_min = models.DateField(null=True, blank=True, db_index=True)
    filter_by_date_max = models.DateField(null=True, blank=True, db_index=True)
    filter_by_pathology = models.CharField(max_length=50, blank=True, db_index=True)
    filter_by_pathology_threshold = models.FloatField(null=True, blank=True)
    
    # Predicted pathologies - copied from XRayImage for historical record
    atelectasis = models.FloatField(null=True, blank=True)
    cardiomegaly = models.FloatField(null=True, blank=True)
    consolidation = models.FloatField(null=True, blank=True)
    edema = models.FloatField(null=True, blank=True)
    effusion = models.FloatField(null=True, blank=True)
    emphysema = models.FloatField(null=True, blank=True)
    fibrosis = models.FloatField(null=True, blank=True)
    hernia = models.FloatField(null=True, blank=True)
    infiltration = models.FloatField(null=True, blank=True)
    mass = models.FloatField(null=True, blank=True)
    nodule = models.FloatField(null=True, blank=True)
    pleural_thickening = models.FloatField(null=True, blank=True)
    pneumonia = models.FloatField(null=True, blank=True)
    pneumothorax = models.FloatField(null=True, blank=True)
    fracture = models.FloatField(null=True, blank=True)
    lung_opacity = models.FloatField(null=True, blank=True)
    enlarged_cardiomediastinum = models.FloatField(null=True, blank=True)
    lung_lesion = models.FloatField(null=True, blank=True)
    support_devices = models.FloatField(null=True, blank=True)
    
    # Severity level
    severity_level = models.IntegerField(null=True, blank=True, db_index=True)
    
    class Meta:
        # Add composite indexes for commonly queried combinations
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['model_used', 'created_at']),
            models.Index(fields=['filter_by_gender', 'created_at']),
            models.Index(fields=['filter_by_pathology', 'created_at']),
            models.Index(fields=['severity_level', 'created_at']),
        ]
        # Optimize database table order
        ordering = ['-created_at']
    
    @property
    def calculate_severity_level(self):
        """Calculate severity level based on average of pathology probabilities
        1: Insignificant findings (0-19%)
        2: Moderate findings (20-30%)
        3: Significant findings (31-100%)
        """
        pathology_fields = {
            'atelectasis': self.atelectasis,
            'cardiomegaly': self.cardiomegaly,
            'consolidation': self.consolidation,
            'edema': self.edema,
            'effusion': self.effusion,
            'emphysema': self.emphysema,
            'fibrosis': self.fibrosis,
            'hernia': self.hernia,
            'infiltration': self.infiltration,
            'mass': self.mass,
            'nodule': self.nodule,
            'pleural_thickening': self.pleural_thickening,
            'pneumonia': self.pneumonia,
            'pneumothorax': self.pneumothorax,
            'fracture': self.fracture,
            'lung_opacity': self.lung_opacity,
            'enlarged_cardiomediastinum': self.enlarged_cardiomediastinum,
            'lung_lesion': self.lung_lesion,
            'support_devices': self.support_devices,
        }
        
        # Filter out None values
        valid_values = [v for v in pathology_fields.values() if v is not None]
        
        if not valid_values:
            return None
        
        # Calculate average probability
        avg_probability = sum(valid_values) / len(valid_values)
        
        # Determine severity level
        if avg_probability <= 0.19:  # 0-19%
            return 1
        elif avg_probability <= 0.30:  # 20-30%
            return 2
        else:  # 31-100%
            return 3
    
    @property
    def severity_label(self):
        """Get severity level label"""
        severity_mapping = {
            1: "Insignificant findings",
            2: "Moderate findings",
            3: "Significant findings",
        }
        level = self.severity_level
        if level is None:
            level = self.calculate_severity_level
            
        return severity_mapping.get(level, "Unknown")
    
    def __str__(self):
        return f"Prediction #{self.id} for {self.xray} using {self.model_used}"


class UserProfile(models.Model):
    """Model to store additional user settings and preferences"""
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    
    # Role-based access control
    role = models.CharField(
        max_length=20,
        choices=USER_ROLES,
        default='Radiographer',
        db_index=True
    )
    
    # User preferences
    preferred_theme = models.CharField(
        max_length=10,
        choices=[('auto', 'System Default'), ('light', 'Light'), ('dark', 'Dark')],
        default='auto'
    )
    preferred_language = models.CharField(
        max_length=10,
        choices=[('en', 'English'), ('lt', 'Lithuanian')],
        default='en'
    )
    dashboard_view = models.CharField(
        max_length=10,
        choices=[('grid', 'Grid View'), ('list', 'List View')],
        default='grid'
    )
    email_notifications = models.BooleanField(default=True)
    processing_complete_notification = models.BooleanField(default=True)
    two_factor_auth_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Role-based permission methods
    def can_access_admin(self):
        """Check if user can access admin panel"""
        return self.role == 'Administrator'
    
    def can_upload_xrays(self):
        """Check if user can upload X-ray images"""
        return self.role in ['Administrator', 'Radiographer', 'Technologist']
    
    def can_view_all_patients(self):
        """Check if user can view all patients' data"""
        return self.role in ['Administrator', 'Radiographer', 'Radiologist']
    
    def can_edit_predictions(self):
        """Check if user can edit prediction results"""
        return self.role in ['Administrator', 'Radiographer', 'Radiologist']
    
    def can_delete_data(self):
        """Check if user can delete X-ray data"""
        return self.role in ['Administrator', 'Radiographer']
    
    def can_generate_interpretability(self):
        """Check if user can generate interpretability visualizations"""
        return self.role in ['Administrator', 'Radiographer', 'Radiologist']
    
    def can_view_interpretability(self):
        """Check if user can view interpretability visualizations"""
        return True  # All users can view interpretability
    
    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.role == 'Administrator'
    
    def can_view_prediction_history(self):
        """Check if user can view prediction history"""
        return True  # All users can view their own history
    
    def can_change_settings(self):
        """Check if user can change account settings"""
        return True  # All users can change their own settings

    def __str__(self):
        return f"{self.user.username} - {self.role}"
