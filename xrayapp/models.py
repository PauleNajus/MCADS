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
    gradcam_visualization = models.ImageField(upload_to='interpretability/gradcam/', null=True, blank=True)
    gradcam_target_class = models.CharField(max_length=50, null=True, blank=True)
    
    has_pli = models.BooleanField(default=False)
    pli_visualization = models.ImageField(upload_to='interpretability/pli/', null=True, blank=True)
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
    
    def __str__(self):
        if self.patient_id and (self.first_name or self.last_name):
            return f"{self.first_name} {self.last_name} (ID: {self.patient_id}) - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"
        return f"X-ray #{self.id} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"
        
    def get_patient_display(self):
        """Return formatted patient information"""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return "Unknown Patient"


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
