from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import XRayImage, PredictionHistory, UserProfile, USER_ROLES


# Unregister the default User admin
admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Enhanced User admin with role information"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined', 'profile__role')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    
    def get_role(self, obj):
        """Get user role with color coding"""
        try:
            role = obj.profile.role
            colors = {
                'Administrator': '#dc3545',  # Red
                'Radiographer': '#28a745',   # Green
                'Technologist': '#007bff',   # Blue
                'Radiologist': '#6f42c1'     # Purple
            }
            color = colors.get(role, '#6c757d')
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color, role
            )
        except:
            return format_html('<span style="color: #dc3545;">No Profile</span>')
    get_role.short_description = 'Role'
    get_role.admin_order_field = 'profile__role'

    def get_fieldsets(self, request, obj=None):
        """Override fieldsets to include role management"""
        fieldsets = super().get_fieldsets(request, obj)
        if obj and hasattr(obj, 'profile'):
            # Add role information to personal info
            fieldsets = list(fieldsets)
            fieldsets[1] = (
                'Personal info',
                {'fields': ('first_name', 'last_name', 'email', 'get_role_info')}
            )
        return fieldsets

    def get_role_info(self, obj):
        """Display role information in user edit form"""
        try:
            profile = obj.profile
            return format_html(
                '<strong>Current Role:</strong> {} <br>'
                '<a href="{}" class="button">Edit Profile & Role</a>',
                profile.role,
                reverse('admin:xrayapp_userprofile_change', args=[profile.pk])
            )
        except:
            return format_html(
                '<span style="color: red;">No profile found</span><br>'
                '<a href="{}" class="button">Create Profile</a>',
                reverse('admin:xrayapp_userprofile_add') + f'?user={obj.pk}'
            )
    get_role_info.short_description = 'Role Information'

    readonly_fields = UserAdmin.readonly_fields + ('get_role_info',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Enhanced UserProfile admin with role management"""
    list_display = (
        'user', 'get_user_full_name', 'role', 'get_role_permissions', 
        'preferred_theme', 'email_notifications', 'created_at'
    )
    list_filter = ('role', 'preferred_theme', 'preferred_language', 'email_notifications', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    ordering = ('user__username',)
    
    fieldsets = (
        ('User', {
            'fields': ('user', 'get_user_info')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'get_permissions_display'),
            'description': 'Role determines what actions the user can perform in the system.'
        }),
        ('Preferences', {
            'fields': ('preferred_theme', 'preferred_language', 'dashboard_view'),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'processing_complete_notification'),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': ('two_factor_auth_enabled',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('get_user_info', 'get_permissions_display', 'created_at', 'updated_at')

    def get_user_full_name(self, obj):
        """Get user's full name"""
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
    get_user_full_name.short_description = 'Full Name'
    get_user_full_name.admin_order_field = 'user__first_name'

    def get_user_info(self, obj):
        """Display user information"""
        user = obj.user
        return format_html(
            '<strong>Username:</strong> {}<br>'
            '<strong>Email:</strong> {}<br>'
            '<strong>Staff:</strong> {}<br>'
            '<strong>Superuser:</strong> {}<br>'
            '<a href="{}" class="button">Edit User Details</a>',
            user.username,
            user.email,
            '✅' if user.is_staff else '❌',
            '✅' if user.is_superuser else '❌',
            reverse('admin:auth_user_change', args=[user.pk])
        )
    get_user_info.short_description = 'User Information'

    def get_role_permissions(self, obj):
        """Show key permissions for the role"""
        perms = []
        if obj.can_access_admin():
            perms.append('Admin')
        if obj.can_upload_xrays():
            perms.append('Upload')
        if obj.can_edit_predictions():
            perms.append('Edit')
        if obj.can_delete_data():
            perms.append('Delete')
        
        return ', '.join(perms) if perms else 'View Only'
    get_role_permissions.short_description = 'Key Permissions'

    def get_permissions_display(self, obj):
        """Display all permissions for the role"""
        permissions = [
            ('Access Admin Panel', obj.can_access_admin()),
            ('Upload X-rays', obj.can_upload_xrays()),
            ('View All Patients', obj.can_view_all_patients()),
            ('Edit Predictions', obj.can_edit_predictions()),
            ('Delete Data', obj.can_delete_data()),
            ('Generate Interpretability', obj.can_generate_interpretability()),
            ('View Interpretability', obj.can_view_interpretability()),
            ('Manage Users', obj.can_manage_users()),
        ]
        
        html = '<table style="width: 100%;">'
        for perm_name, has_perm in permissions:
            icon = '✅' if has_perm else '❌'
            html += f'<tr><td>{perm_name}</td><td>{icon}</td></tr>'
        html += '</table>'
        
        return format_html(html)
    get_permissions_display.short_description = 'Role Permissions'


@admin.register(XRayImage)
class XRayImageAdmin(admin.ModelAdmin):
    """Enhanced XRayImage admin with role-based features"""
    list_display = (
        'id', 'get_user_with_role', 'get_patient_display', 'patient_id', 
        'gender', 'uploaded_at', 'processing_status', 'get_severity_display'
    )
    list_filter = (
        'user__profile__role', 'processing_status', 'gender', 'uploaded_at', 
        'severity_level', 'has_gradcam', 'has_pli'
    )
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
            'fields': ('user', 'get_user_role_info')
        }),
        ('Patient Information', {
            'fields': ('first_name', 'last_name', 'patient_id', 'gender', 'date_of_birth', 'date_of_xray', 'additional_info')
        }),
        ('Image Processing', {
            'fields': ('image', 'uploaded_at', 'processing_status', 'progress', 'image_format', 'image_size', 'image_resolution')
        }),
        ('Pathology Predictions', {
            'fields': (
                'atelectasis', 'cardiomegaly', 'consolidation', 'edema', 
                'effusion', 'emphysema', 'fibrosis', 'hernia', 'infiltration',
                'mass', 'nodule', 'pleural_thickening', 'pneumonia', 'pneumothorax',
                'fracture', 'lung_opacity', 'enlarged_cardiomediastinum', 'lung_lesion',
                'severity_level'
            ),
            'classes': ('collapse',)
        }),
        ('Interpretability Visualizations', {
            'fields': (
                'has_gradcam', 'gradcam_visualization', 'gradcam_heatmap',
                'gradcam_overlay', 'gradcam_target_class', 'has_pli', 'pli_visualization',
                'pli_overlay_visualization', 'pli_saliency_map', 'pli_target_class'
            ),
            'classes': ('collapse',)
        })
    )

    def get_user_with_role(self, obj):
        """Display user with their role"""
        try:
            role = obj.user.profile.role
            colors = {
                'Administrator': '#dc3545',
                'Radiographer': '#28a745',
                'Technologist': '#007bff',
                'Radiologist': '#6f42c1'
            }
            color = colors.get(role, '#6c757d')
            return format_html(
                '{} <span style="color: {}; font-size: 0.8em;">({})</span>',
                obj.user.username, color, role
            )
        except:
            return obj.user.username
    get_user_with_role.short_description = 'User (Role)'
    get_user_with_role.admin_order_field = 'user__username'

    def get_user_role_info(self, obj):
        """Display user role information in detail view"""
        try:
            profile = obj.user.profile
            return format_html(
                '<strong>Role:</strong> {}<br>'
                '<strong>Can Edit Predictions:</strong> {}<br>'
                '<strong>Can Delete:</strong> {}',
                profile.role,
                '✅' if profile.can_edit_predictions() else '❌',
                '✅' if profile.can_delete_data() else '❌'
            )
        except:
            return 'No profile information available'
    get_user_role_info.short_description = 'User Role Info'

    def get_severity_display(self, obj):
        """Display severity with color coding"""
        level = obj.severity_level or obj.calculate_severity_level
        if level == 1:
            return format_html('<span style="color: #28a745;">Insignificant</span>')
        elif level == 2:
            return format_html('<span style="color: #ffc107;">Moderate</span>')
        elif level == 3:
            return format_html('<span style="color: #dc3545;">Significant</span>')
        return 'Unknown'
    get_severity_display.short_description = 'Severity'


@admin.register(PredictionHistory)
class PredictionHistoryAdmin(admin.ModelAdmin):
    """Enhanced PredictionHistory admin"""
    list_display = ('id', 'get_user_with_role', 'xray', 'created_at', 'model_used', 'get_severity_display')
    list_filter = ('user__profile__role', 'model_used', 'created_at', 'severity_level')
    search_fields = ('user__username', 'xray__patient_id', 'xray__first_name', 'xray__last_name')
    readonly_fields = (
        'user', 'xray', 'created_at', 'model_used',
        'atelectasis', 'cardiomegaly', 'consolidation', 'edema', 
        'effusion', 'emphysema', 'fibrosis', 'hernia', 'infiltration',
        'mass', 'nodule', 'pleural_thickening', 'pneumonia', 'pneumothorax',
        'fracture', 'lung_opacity', 'enlarged_cardiomediastinum', 'lung_lesion',
        'severity_level'
    )

    def get_user_with_role(self, obj):
        """Display user with their role"""
        try:
            role = obj.user.profile.role
            colors = {
                'Administrator': '#dc3545',
                'Radiographer': '#28a745',
                'Technologist': '#007bff',
                'Radiologist': '#6f42c1'
            }
            color = colors.get(role, '#6c757d')
            return format_html(
                '{} <span style="color: {}; font-size: 0.8em;">({})</span>',
                obj.user.username, color, role
            )
        except:
            return obj.user.username
    get_user_with_role.short_description = 'User (Role)'
    get_user_with_role.admin_order_field = 'user__username'

    def get_severity_display(self, obj):
        """Display severity with color coding"""
        level = obj.severity_level or obj.calculate_severity_level
        if level == 1:
            return format_html('<span style="color: #28a745;">Insignificant</span>')
        elif level == 2:
            return format_html('<span style="color: #ffc107;">Moderate</span>')
        elif level == 3:
            return format_html('<span style="color: #dc3545;">Significant</span>')
        return 'Unknown'
    get_severity_display.short_description = 'Severity'


# Customize admin site headers
admin.site.site_header = "MCADS Administration"
admin.site.site_title = "MCADS Admin"
admin.site.index_title = "Multi-label Chest Abnormality Detection System"
