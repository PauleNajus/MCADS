from django.contrib import admin
from .models import XRayImage, PredictionHistory, UserProfile


@admin.register(XRayImage)
class XRayImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_patient_display', 'patient_id', 'gender', 'uploaded_at', 'processing_status')
    list_filter = ('user', 'processing_status', 'gender', 'uploaded_at')
    search_fields = ('user__username', 'patient_id', 'first_name', 'last_name')
    readonly_fields = (
        'uploaded_at', 'progress', 'image_format', 'image_size', 'image_resolution',
        'atelectasis', 'cardiomegaly', 'consolidation', 'edema', 
        'effusion', 'emphysema', 'fibrosis', 'hernia', 'infiltration',
        'mass', 'nodule', 'pleural_thickening', 'pneumonia', 'pneumothorax',
        'fracture', 'lung_opacity', 'enlarged_cardiomediastinum', 'lung_lesion',
        'severity_level', 'has_gradcam', 'gradcam_visualization', 'gradcam_heatmap',
        'gradcam_overlay', 'gradcam_target_class', 'has_pli', 'pli_visualization',
        'pli_overlay_visualization', 'pli_saliency_map', 'pli_target_class'
    )
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Patient Information', {
            'fields': ('first_name', 'last_name', 'patient_id', 'gender', 'date_of_birth', 'date_of_xray', 'additional_info')
        }),
        ('Image', {
            'fields': ('image', 'uploaded_at', 'processing_status', 'progress', 'image_format', 'image_size', 'image_resolution')
        }),
        ('Pathology Predictions', {
            'fields': (
                'atelectasis', 'cardiomegaly', 'consolidation', 'edema', 
                'effusion', 'emphysema', 'fibrosis', 'hernia', 'infiltration',
                'mass', 'nodule', 'pleural_thickening', 'pneumonia', 'pneumothorax',
                'fracture', 'lung_opacity', 'enlarged_cardiomediastinum', 'lung_lesion',
                'severity_level'
            )
        }),
        ('Interpretability', {
            'fields': (
                'has_gradcam', 'gradcam_visualization', 'gradcam_heatmap',
                'gradcam_overlay', 'gradcam_target_class', 'has_pli', 'pli_visualization',
                'pli_overlay_visualization', 'pli_saliency_map', 'pli_target_class'
            )
        })
    )


@admin.register(PredictionHistory)
class PredictionHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'xray', 'created_at', 'model_used')
    list_filter = ('user', 'model_used', 'created_at')
    search_fields = ('user__username', 'xray__patient_id', 'xray__first_name', 'xray__last_name')
    readonly_fields = (
        'user', 'xray', 'created_at', 'model_used',
        'atelectasis', 'cardiomegaly', 'consolidation', 'edema', 
        'effusion', 'emphysema', 'fibrosis', 'hernia', 'infiltration',
        'mass', 'nodule', 'pleural_thickening', 'pneumonia', 'pneumothorax',
        'fracture', 'lung_opacity', 'enlarged_cardiomediastinum', 'lung_lesion',
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'preferred_theme', 'preferred_language', 'created_at')
    list_filter = ('preferred_theme', 'preferred_language', 'created_at')
    search_fields = ('user__username', 'user__email')
