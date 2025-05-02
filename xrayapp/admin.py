from django.contrib import admin
from .models import XRayImage, PredictionHistory


@admin.register(XRayImage)
class XRayImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient_id', 'first_name', 'last_name', 'gender', 'date_of_xray', 'uploaded_at')
    list_filter = ('gender', 'date_of_xray', 'uploaded_at')
    search_fields = ('id', 'patient_id', 'first_name', 'last_name')
    readonly_fields = (
        'atelectasis', 'cardiomegaly', 'consolidation', 'edema', 
        'effusion', 'emphysema', 'fibrosis', 'hernia', 'infiltration',
        'mass', 'nodule', 'pleural_thickening', 'pneumonia', 'pneumothorax',
        'fracture', 'lung_opacity', 'support_devices', 'enlarged_cardiomediastinum',
        'lung_lesion',
    )
    fieldsets = (
        ('Patient Information', {
            'fields': ('first_name', 'last_name', 'patient_id', 'gender', 'date_of_birth', 'date_of_xray', 'additional_info')
        }),
        ('Image', {
            'fields': ('image', 'uploaded_at')
        }),
        ('Pathology Predictions', {
            'fields': readonly_fields
        })
    )


@admin.register(PredictionHistory)
class PredictionHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'xray', 'created_at', 'model_used')
    list_filter = ('model_used', 'created_at')
    search_fields = ('xray__patient_id', 'xray__first_name', 'xray__last_name')
    readonly_fields = (
        'xray', 'created_at', 'model_used',
        'atelectasis', 'cardiomegaly', 'consolidation', 'edema', 
        'effusion', 'emphysema', 'fibrosis', 'hernia', 'infiltration',
        'mass', 'nodule', 'pleural_thickening', 'pneumonia', 'pneumothorax',
        'fracture', 'lung_opacity', 'enlarged_cardiomediastinum', 'lung_lesion',
    )
