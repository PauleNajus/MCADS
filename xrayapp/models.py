from django.db import models

# Create your models here.

class XRayImage(models.Model):
    """Model to store X-ray images and analysis results"""
    # Patient Information
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    patient_id = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_xray = models.DateField(null=True, blank=True)
    additional_info = models.TextField(blank=True)
    
    # X-ray image and processing
    image = models.ImageField(upload_to='xrays/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processing_status = models.CharField(max_length=20, default='pending')
    progress = models.IntegerField(default=0)
    
    # Image metadata
    image_format = models.CharField(max_length=10, blank=True)  # e.g., 'JPEG', 'PNG'
    image_size = models.CharField(max_length=20, blank=True)    # e.g., '2.4 MB'
    image_resolution = models.CharField(max_length=20, blank=True)  # e.g., '1024x768'
    image_date_created = models.DateTimeField(null=True, blank=True)
    
    # Interpretability visualizations
    has_gradcam = models.BooleanField(default=False)
    gradcam_visualization = models.CharField(max_length=255, null=True, blank=True)
    gradcam_heatmap = models.CharField(max_length=255, null=True, blank=True)
    gradcam_overlay = models.CharField(max_length=255, null=True, blank=True)
    gradcam_target_class = models.CharField(max_length=50, null=True, blank=True)
    
    has_pli = models.BooleanField(default=False)
    pli_visualization = models.CharField(max_length=255, null=True, blank=True)
    pli_overlay_visualization = models.CharField(max_length=255, null=True, blank=True)
    pli_saliency_map = models.CharField(max_length=255, null=True, blank=True)
    pli_target_class = models.CharField(max_length=50, null=True, blank=True)
    
    # Predicted pathologies (values range from 0.0 to 1.0)
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
    severity_level = models.IntegerField(null=True, blank=True)
    
    @property
    def calculate_severity_level(self):
        """Calculate severity level based on average of pathology probabilities
        1: Insignificant findings (0-20%)
        2: Moderate findings (21-25%)
        3: Significant findings (26-100%)
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
        if avg_probability <= 0.20:  # 0-20%
            return 1
        elif avg_probability <= 0.25:  # 21-25%
            return 2
        else:  # 26-100%
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
    xray = models.ForeignKey(XRayImage, on_delete=models.CASCADE, related_name='prediction_history')
    created_at = models.DateTimeField(auto_now_add=True)
    model_used = models.CharField(max_length=50)  # densenet, resnet, etc.
    
    # Filters
    filter_by_gender = models.CharField(max_length=10, blank=True)
    filter_by_age_min = models.IntegerField(null=True, blank=True)
    filter_by_age_max = models.IntegerField(null=True, blank=True)
    filter_by_date_min = models.DateField(null=True, blank=True)
    filter_by_date_max = models.DateField(null=True, blank=True)
    filter_by_pathology = models.CharField(max_length=50, blank=True)
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
    severity_level = models.IntegerField(null=True, blank=True)
    
    @property
    def calculate_severity_level(self):
        """Calculate severity level based on average of pathology probabilities
        1: Insignificant findings (0-20%)
        2: Moderate findings (21-25%)
        3: Significant findings (26-100%)
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
        if avg_probability <= 0.20:  # 0-20%
            return 1
        elif avg_probability <= 0.25:  # 21-25%
            return 2
        else:  # 26-100%
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
    
    def __str__(self):
        return f"Profile for {self.user.username}"
