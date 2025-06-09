from django.shortcuts import render, redirect
import threading
import os
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .forms import XRayUploadForm, PredictionHistoryFilterForm, UserInfoForm, UserProfileForm, ChangePasswordForm
from .models import XRayImage, PredictionHistory, UserProfile
from .utils import (process_image, process_image_with_interpretability,
                   save_interpretability_visualization, save_overlay_visualization, save_saliency_map,
                   save_gradcam_heatmap, save_gradcam_overlay)
from .interpretability import apply_gradcam, apply_pixel_interpretability
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required


def process_image_async(image_path, xray_instance, model_type):
    """Process the image in a background thread and update the model with progress"""
    results = process_image(image_path, xray_instance, model_type)
    
    # Save predictions to the database - only save what's available in the results
    xray_instance.atelectasis = results.get('Atelectasis', None)
    xray_instance.cardiomegaly = results.get('Cardiomegaly', None)
    xray_instance.consolidation = results.get('Consolidation', None)
    xray_instance.edema = results.get('Edema', None)
    xray_instance.effusion = results.get('Effusion', None)
    xray_instance.emphysema = results.get('Emphysema', None)
    xray_instance.fibrosis = results.get('Fibrosis', None)
    xray_instance.hernia = results.get('Hernia', None)
    xray_instance.infiltration = results.get('Infiltration', None)
    xray_instance.mass = results.get('Mass', None)
    xray_instance.nodule = results.get('Nodule', None)
    xray_instance.pleural_thickening = results.get('Pleural_Thickening', None)
    xray_instance.pneumonia = results.get('Pneumonia', None)
    xray_instance.pneumothorax = results.get('Pneumothorax', None)
    xray_instance.fracture = results.get('Fracture', None)
    xray_instance.lung_opacity = results.get('Lung Opacity', None)
    
    # These fields will only be present in DenseNet results
    if 'Enlarged Cardiomediastinum' in results:
        xray_instance.enlarged_cardiomediastinum = results.get('Enlarged Cardiomediastinum', None)
    if 'Lung Lesion' in results:
        xray_instance.lung_lesion = results.get('Lung Lesion', None)
    
    xray_instance.save()
    
    # Create prediction history record
    create_prediction_history(xray_instance, model_type)


def process_with_interpretability_async(image_path, xray_instance, model_type, interpretation_method, target_class=None):
    """Process the image with interpretability visualization in a background thread"""
    try:
        # Set initial progress
        xray_instance.progress = 10
        xray_instance.save()
        
        print(f"Starting {interpretation_method} visualization for image {image_path} with model {model_type}")
        
        # Process the image with the selected interpretability method
        if interpretation_method == 'gradcam':
            try:
                results = apply_gradcam(image_path, model_type, target_class)
                results['method'] = 'gradcam'
                print(f"GradCAM generation completed successfully for {target_class}")
            except Exception as e:
                print(f"Error in GradCAM generation: {str(e)}")
                raise
        elif interpretation_method == 'pli':
            try:
                results = apply_pixel_interpretability(image_path, model_type, target_class)
                results['method'] = 'pli'
                print(f"PLI generation completed successfully for {target_class}")
            except Exception as e:
                print(f"Error in PLI generation: {str(e)}")
                raise
        else:
            # Invalid method, return error
            print(f"Invalid interpretation method: {interpretation_method}")
            xray_instance.processing_status = 'error'
            xray_instance.save()
            return
        
        # Update progress
        xray_instance.progress = 70
        xray_instance.save()
        
        print(f"Saving visualization results for {interpretation_method}")
        
        # Save interpretability visualizations
        if interpretation_method and 'method' in results:
            if results['method'] == 'gradcam':
                # Create output directory if it doesn't exist
                output_dir = Path(settings.MEDIA_ROOT) / 'interpretability' / 'gradcam'
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate filenames
                combined_filename = f"gradcam_{xray_instance.id}_{results['target_class']}.png"
                heatmap_filename = f"gradcam_heatmap_{xray_instance.id}_{results['target_class']}.png"
                overlay_filename = f"gradcam_overlay_{xray_instance.id}_{results['target_class']}.png"
                
                # Generate paths
                combined_path = output_dir / combined_filename
                heatmap_path = output_dir / heatmap_filename
                overlay_path = output_dir / overlay_filename
                
                print(f"Saving Grad-CAM combined visualization to {combined_path}")
                
                # Save combined visualization
                save_interpretability_visualization(results, combined_path)
                
                print(f"Saving Grad-CAM heatmap to {heatmap_path}")
                
                # Save heatmap separately
                save_gradcam_heatmap(results, heatmap_path)
                
                print(f"Saving Grad-CAM overlay to {overlay_path}")
                
                # Save overlay separately
                save_gradcam_overlay(results, overlay_path)
                
                # Update model
                xray_instance.has_gradcam = True
                xray_instance.gradcam_visualization = f"interpretability/gradcam/{combined_filename}"
                xray_instance.gradcam_heatmap = f"interpretability/gradcam/{heatmap_filename}"
                xray_instance.gradcam_overlay = f"interpretability/gradcam/{overlay_filename}"
                xray_instance.gradcam_target_class = results['target_class']
                
            elif results['method'] == 'pli':
                try:
                    # Create output directory if it doesn't exist
                    output_dir = Path(settings.MEDIA_ROOT) / 'interpretability' / 'pli'
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Generate filename for saliency map
                    saliency_filename = f"pli_{xray_instance.id}_{results['target_class']}.png"
                    saliency_path = output_dir / saliency_filename
                    
                    # Generate filename for overlay
                    overlay_filename = f"pli_overlay_{xray_instance.id}_{results['target_class']}.png"
                    overlay_path = output_dir / overlay_filename
                    
                    # Generate filename for separate saliency map
                    separate_saliency_filename = f"pli_saliency_{xray_instance.id}_{results['target_class']}.png"
                    separate_saliency_path = output_dir / separate_saliency_filename
                    
                    print(f"Saving PLI visualization to {saliency_path}")
                    
                    # Save saliency visualization (combined visualization)
                    save_interpretability_visualization(results, saliency_path)
                    
                    print(f"Saving PLI overlay to {overlay_path}")
                    
                    # Save overlay separately
                    save_overlay_visualization(results, overlay_path)
                    
                    print(f"Saving PLI saliency map to {separate_saliency_path}")
                    
                    # Save saliency map separately
                    save_saliency_map(results, separate_saliency_path)
                    
                    # Update model
                    xray_instance.has_pli = True
                    xray_instance.pli_visualization = f"interpretability/pli/{saliency_filename}"
                    xray_instance.pli_overlay_visualization = f"interpretability/pli/{overlay_filename}"
                    xray_instance.pli_saliency_map = f"interpretability/pli/{separate_saliency_filename}"
                    xray_instance.pli_target_class = results['target_class']
                except Exception as e:
                    print(f"Error saving PLI results: {str(e)}")
                    raise
        
        xray_instance.progress = 90
        xray_instance.processing_status = 'complete'
        xray_instance.save()
        
        # Create prediction history record
        create_prediction_history(xray_instance, model_type)
        
        # Set progress to 100%
        xray_instance.progress = 100
        xray_instance.save()
        
        print(f"Interpretability visualization complete for {interpretation_method}")
        
    except Exception as e:
        import traceback
        print(f"Error in interpretability processing: {str(e)}")
        print(traceback.format_exc())
        xray_instance.processing_status = 'error'
        xray_instance.save()


def create_prediction_history(xray_instance, model_type):
    """Create a prediction history record for an XRayImage"""
    history = PredictionHistory(
        user=xray_instance.user,
        xray=xray_instance,
        model_used=model_type,
        # Copy all pathology values for historical record
        atelectasis=xray_instance.atelectasis,
        cardiomegaly=xray_instance.cardiomegaly,
        consolidation=xray_instance.consolidation,
        edema=xray_instance.edema,
        effusion=xray_instance.effusion,
        emphysema=xray_instance.emphysema,
        fibrosis=xray_instance.fibrosis,
        hernia=xray_instance.hernia,
        infiltration=xray_instance.infiltration,
        mass=xray_instance.mass,
        nodule=xray_instance.nodule,
        pleural_thickening=xray_instance.pleural_thickening,
        pneumonia=xray_instance.pneumonia,
        pneumothorax=xray_instance.pneumothorax,
        fracture=xray_instance.fracture,
        lung_opacity=xray_instance.lung_opacity,
        enlarged_cardiomediastinum=xray_instance.enlarged_cardiomediastinum,
        lung_lesion=xray_instance.lung_lesion,
        # Copy severity level
        severity_level=xray_instance.severity_level,
    )
    # Only save if we have a user assigned
    if xray_instance.user:
        history.save()
    else:
        print("Warning: XRayImage has no user assigned, skipping prediction history creation")


@login_required
def home(request):
    """Home page with image upload form"""
    if request.method == 'POST':
        form = XRayUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Create a new XRayImage instance with all form data but don't save yet
            xray_instance = form.save(commit=False)
            # Assign the current user
            xray_instance.user = request.user
            # Now save the instance
            xray_instance.save()
            
            # Get the model type from the form
            model_type = request.POST.get('model_type', 'densenet')
            
            # Save image to disk
            image_path = Path(settings.MEDIA_ROOT) / xray_instance.image.name
            
            # Start background processing
            thread = threading.Thread(
                target=process_image_async, 
                args=(image_path, xray_instance, model_type)
            )
            thread.start()
            
            # Check if it's an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Return JSON response for AJAX requests
                return JsonResponse({
                    'upload_id': xray_instance.pk,
                    'xray_id': xray_instance.pk
                })
            else:
                # Redirect for normal form submissions
                return redirect('xray_results', pk=xray_instance.pk)
    else:
        form = XRayUploadForm()
        
    return render(request, 'xrayapp/home.html', {
        'form': form,
        'today_date': timezone.now()
    })


@login_required
def xray_results(request, pk):
    """View the results of the X-ray analysis"""
    xray_instance = XRayImage.objects.get(pk=pk, user=request.user)
    
    # Build predictions dictionary based on model fields
    predictions = {
        'Atelectasis': xray_instance.atelectasis,
        'Cardiomegaly': xray_instance.cardiomegaly,
        'Consolidation': xray_instance.consolidation,
        'Edema': xray_instance.edema,
        'Effusion': xray_instance.effusion,
        'Emphysema': xray_instance.emphysema,
        'Fibrosis': xray_instance.fibrosis,
        'Hernia': xray_instance.hernia,
        'Infiltration': xray_instance.infiltration,
        'Mass': xray_instance.mass,
        'Nodule': xray_instance.nodule,
        'Pleural_Thickening': xray_instance.pleural_thickening,
        'Pneumonia': xray_instance.pneumonia,
        'Pneumothorax': xray_instance.pneumothorax,
        'Fracture': xray_instance.fracture,
        'Lung Opacity': xray_instance.lung_opacity,
    }
    
    # Add DenseNet exclusive fields if they have values
    if xray_instance.enlarged_cardiomediastinum is not None:
        predictions['Enlarged Cardiomediastinum'] = xray_instance.enlarged_cardiomediastinum
    if xray_instance.lung_lesion is not None:
        predictions['Lung Lesion'] = xray_instance.lung_lesion
    
    # Filter out predictions with None values
    predictions = {k: v for k, v in predictions.items() if v is not None}
    
    # Sort predictions by value (highest to lowest)
    predictions = dict(sorted(predictions.items(), key=lambda item: item[1], reverse=True))
    
    # Calculate patient age if date_of_birth is provided
    patient_age = None
    if xray_instance.date_of_birth:
        today = timezone.now().date()
        patient_age = relativedelta(today, xray_instance.date_of_birth).years
    
    # Format patient information for display
    patient_info = {
        'Patient ID': xray_instance.patient_id,
        'Name': f"{xray_instance.first_name} {xray_instance.last_name}".strip() if xray_instance.first_name or xray_instance.last_name else None,
        'Gender': xray_instance.gender.capitalize() if xray_instance.gender else None,
        'Age': f"{patient_age} years" if patient_age is not None else None,
        'Date of Birth': xray_instance.date_of_birth.strftime("%B %d, %Y") if xray_instance.date_of_birth else None,
        'X-ray Date': xray_instance.date_of_xray.strftime("%B %d, %Y") if xray_instance.date_of_xray else None,
        'Additional Information': xray_instance.additional_info if xray_instance.additional_info else None,
    }
    
    # Create image metadata dictionary
    image_metadata = {
        'Image name': Path(xray_instance.image.name).name,
        'Format': xray_instance.image_format,
        'Size': xray_instance.image_size,
        'Resolution': xray_instance.image_resolution,
        'Date Created': xray_instance.image_date_created.strftime("%B %d, %Y %H:%M") if xray_instance.image_date_created else "Unknown",
    }
    
    # Filter out None values
    patient_info = {k: v for k, v in patient_info.items() if v is not None}
    
    # Get image URL
    image_url = xray_instance.image.url
    
    # Ensure severity level is calculated and stored
    if xray_instance.severity_level is None:
        xray_instance.severity_level = xray_instance.calculate_severity_level
        xray_instance.save()
    
    # Prepare GRAD-CAM URLs for display
    media_url = settings.MEDIA_URL
    gradcam_url = f"{media_url}{xray_instance.gradcam_visualization}" if xray_instance.has_gradcam and xray_instance.gradcam_visualization else None
    gradcam_heatmap_url = f"{media_url}{xray_instance.gradcam_heatmap}" if xray_instance.has_gradcam and xray_instance.gradcam_heatmap else None
    gradcam_overlay_url = f"{media_url}{xray_instance.gradcam_overlay}" if xray_instance.has_gradcam and xray_instance.gradcam_overlay else None

    context = {
        'xray': xray_instance,
        'image_url': image_url,
        'predictions': predictions,
        'patient_info': patient_info,
        'image_metadata': image_metadata,
        'severity_level': xray_instance.severity_level,
        'severity_label': xray_instance.severity_label,
        'has_gradcam': xray_instance.has_gradcam,
        'gradcam_url': gradcam_url,
        'gradcam_heatmap_url': gradcam_heatmap_url,
        'gradcam_overlay_url': gradcam_overlay_url,
        'gradcam_target': xray_instance.gradcam_target_class,
    }
    
    return render(request, 'xrayapp/results.html', context)


@login_required
def prediction_history(request):
    """View prediction history with advanced filtering"""
    form = PredictionHistoryFilterForm(request.GET)
    
    # Initialize query - filter by current user
    query = PredictionHistory.objects.filter(user=request.user).order_by('-created_at')
    
    # Apply filters if the form is valid
    if form.is_valid():
        # Gender filter
        if form.cleaned_data.get('gender'):
            query = query.filter(xray__gender=form.cleaned_data['gender'])
        
        # Age range filter
        if form.cleaned_data.get('age_min') is not None:
            # Calculate date based on minimum age
            min_age_date = timezone.now().date() - relativedelta(years=form.cleaned_data['age_min'])
            query = query.filter(xray__date_of_birth__lte=min_age_date)
            
        if form.cleaned_data.get('age_max') is not None:
            # Calculate date based on maximum age
            max_age_date = timezone.now().date() - relativedelta(years=form.cleaned_data['age_max'] + 1)
            query = query.filter(xray__date_of_birth__gte=max_age_date)
        
        # Date range filter
        if form.cleaned_data.get('date_min'):
            query = query.filter(xray__date_of_xray__gte=form.cleaned_data['date_min'])
            
        if form.cleaned_data.get('date_max'):
            query = query.filter(xray__date_of_xray__lte=form.cleaned_data['date_max'])
        
        # Pathology filter
        if form.cleaned_data.get('pathology') and form.cleaned_data.get('pathology_threshold') is not None:
            threshold = form.cleaned_data['pathology_threshold']
            field_name = form.cleaned_data['pathology']
            
            # Dynamic field filtering
            filter_kwargs = {f"{field_name}__gte": threshold}
            query = query.filter(**filter_kwargs)
    
    # Execute query
    history_items = query
    
    context = {
        'form': form,
        'history_items': history_items,
    }
    
    return render(request, 'xrayapp/prediction_history.html', context)


@login_required
def delete_prediction_history(request, pk):
    """Delete a prediction history record"""
    try:
        history_item = PredictionHistory.objects.get(pk=pk, user=request.user)
        history_item.delete()
        messages.success(request, 'Prediction history record has been deleted.')
    except PredictionHistory.DoesNotExist:
        messages.error(request, 'Prediction history record not found.')
    
    return redirect('prediction_history')


@login_required
def delete_all_prediction_history(request):
    """Delete all prediction history records"""
    if request.method == 'POST':
        # Count records before deletion for current user
        count = PredictionHistory.objects.filter(user=request.user).count()
        
        # Delete all records for current user
        PredictionHistory.objects.filter(user=request.user).delete()
        
        if count > 0:
            messages.success(request, f'All {count} prediction history records have been deleted.')
        else:
            messages.info(request, 'No prediction history records to delete.')
    
    return redirect('prediction_history')


@login_required
def edit_prediction_history(request, pk):
    """Edit a prediction history record"""
    try:
        history_item = PredictionHistory.objects.get(pk=pk, user=request.user)
        
        if request.method == 'POST':
            # Handle form submission
            form = XRayUploadForm(request.POST, instance=history_item.xray)
            if form.is_valid():
                form.save()
                messages.success(request, 'Prediction record has been updated.')
                return redirect('prediction_history')
        else:
            # Display form with current values
            form = XRayUploadForm(instance=history_item.xray)
        
        return render(request, 'xrayapp/edit_prediction.html', {
            'form': form,
            'history_item': history_item
        })
    except PredictionHistory.DoesNotExist:
        messages.error(request, 'Prediction history record not found.')
        return redirect('prediction_history')


@login_required
def generate_interpretability(request, pk):
    """Generate interpretability visualization for an X-ray image"""
    xray_instance = XRayImage.objects.get(pk=pk, user=request.user)
    
    # Get parameters from request
    interpretation_method = request.GET.get('method', 'gradcam')  # Default to Grad-CAM
    model_type = request.GET.get('model_type', 'densenet')  # Default to DenseNet
    target_class = request.GET.get('target_class', None)  # Default to None (use highest probability class)
    
    # Reset progress to 0 and set status to processing
    xray_instance.progress = 0
    xray_instance.processing_status = 'processing'
    xray_instance.save()
    
    # Get the image path
    image_path = Path(settings.MEDIA_ROOT) / xray_instance.image.name
    
    # Start background processing
    thread = threading.Thread(
        target=process_with_interpretability_async,
        args=(image_path, xray_instance, model_type, interpretation_method, target_class)
    )
    thread.start()
    
    # Redirect to the results page
    return redirect('xray_results', pk=pk)


@login_required
def view_interpretability(request, pk):
    """View interpretability visualizations for an X-ray image"""
    xray_instance = XRayImage.objects.get(pk=pk, user=request.user)
    
    # Build predictions dictionary
    predictions = {
        'Atelectasis': xray_instance.atelectasis,
        'Cardiomegaly': xray_instance.cardiomegaly,
        'Consolidation': xray_instance.consolidation,
        'Edema': xray_instance.edema,
        'Effusion': xray_instance.effusion,
        'Emphysema': xray_instance.emphysema,
        'Fibrosis': xray_instance.fibrosis,
        'Hernia': xray_instance.hernia,
        'Infiltration': xray_instance.infiltration,
        'Mass': xray_instance.mass,
        'Nodule': xray_instance.nodule,
        'Pleural_Thickening': xray_instance.pleural_thickening,
        'Pneumonia': xray_instance.pneumonia,
        'Pneumothorax': xray_instance.pneumothorax,
        'Fracture': xray_instance.fracture,
        'Lung Opacity': xray_instance.lung_opacity,
    }
    
    # Add DenseNet-specific fields if they exist
    if xray_instance.enlarged_cardiomediastinum is not None:
        predictions['Enlarged Cardiomediastinum'] = xray_instance.enlarged_cardiomediastinum
    if xray_instance.lung_lesion is not None:
        predictions['Lung Lesion'] = xray_instance.lung_lesion
    
    # Remove None values
    predictions = {k: v for k, v in predictions.items() if v is not None}
    
    # Sort by prediction value (descending)
    predictions = dict(sorted(predictions.items(), key=lambda item: item[1], reverse=True))
    
    # Create image metadata dictionary
    image_metadata = {
        'Image name': Path(xray_instance.image.name).name,
        'Format': xray_instance.image_format,
        'Size': xray_instance.image_size,
        'Resolution': xray_instance.image_resolution,
        'Date Created': xray_instance.image_date_created.strftime("%B %d, %Y %H:%M") if xray_instance.image_date_created else "Unknown",
    }
    
    # Prepare media URLs for visualizations
    media_url = settings.MEDIA_URL
    gradcam_url = f"{media_url}{xray_instance.gradcam_visualization}" if xray_instance.has_gradcam and xray_instance.gradcam_visualization else None
    gradcam_heatmap_url = f"{media_url}{xray_instance.gradcam_heatmap}" if xray_instance.has_gradcam and xray_instance.gradcam_heatmap else None
    gradcam_overlay_url = f"{media_url}{xray_instance.gradcam_overlay}" if xray_instance.has_gradcam and xray_instance.gradcam_overlay else None
    pli_url = f"{media_url}{xray_instance.pli_visualization}" if xray_instance.has_pli and xray_instance.pli_visualization else None
    pli_overlay_url = f"{media_url}{xray_instance.pli_overlay_visualization}" if xray_instance.has_pli and xray_instance.pli_overlay_visualization else None
    pli_saliency_url = f"{media_url}{xray_instance.pli_saliency_map}" if xray_instance.has_pli and xray_instance.pli_saliency_map else None
    
    context = {
        'xray': xray_instance,
        'predictions': predictions,
        'image_url': xray_instance.image.url,
        'has_gradcam': xray_instance.has_gradcam,
        'gradcam_url': gradcam_url,
        'gradcam_heatmap_url': gradcam_heatmap_url,
        'gradcam_overlay_url': gradcam_overlay_url,
        'gradcam_target': xray_instance.gradcam_target_class,
        'has_pli': xray_instance.has_pli,
        'pli_url': pli_url,
        'pli_overlay_url': pli_overlay_url,
        'pli_saliency_url': pli_saliency_url,
        'pli_target': xray_instance.pli_target_class,
        'image_metadata': image_metadata,
    }
    
    return render(request, 'xrayapp/interpretability.html', context)


@login_required
def check_progress(request, pk):
    """AJAX endpoint to check processing progress"""
    try:
        xray_instance = XRayImage.objects.get(pk=pk, user=request.user)
        return JsonResponse({
            'status': xray_instance.processing_status,
            'progress': xray_instance.progress,
            'xray_id': xray_instance.pk  # Add xray_id to the response
        })
    except XRayImage.DoesNotExist:
        return JsonResponse({'error': 'Image not found'}, status=404)


@login_required
def account_settings(request):
    """View for managing user account settings"""
    # Ensure user has a profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Handle form submissions
    active_tab = request.GET.get('tab', 'profile')
    
    # Process profile info form
    if request.method == 'POST' and 'update_profile' in request.POST:
        user_form = UserInfoForm(request.POST, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, 'Your profile information has been updated successfully.')
            active_tab = 'profile'
    else:
        user_form = UserInfoForm(instance=request.user)
    
    # Process settings form
    if request.method == 'POST' and 'update_settings' in request.POST:
        settings_form = UserProfileForm(request.POST, instance=profile)
        if settings_form.is_valid():
            settings_form.save()
            messages.success(request, 'Your settings have been updated successfully.')
            active_tab = 'settings'
    else:
        settings_form = UserProfileForm(instance=profile)
    
    # Process password change form
    if request.method == 'POST' and 'change_password' in request.POST:
        password_form = ChangePasswordForm(request.user, request.POST)
        if password_form.is_valid():
            user = request.user
            new_password = password_form.cleaned_data['new_password']
            user.set_password(new_password)
            user.save()
            # Update the session to prevent the user from being logged out
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password has been changed successfully.')
            active_tab = 'security'
    else:
        password_form = ChangePasswordForm(request.user)
    
    context = {
        'user_form': user_form,
        'settings_form': settings_form,
        'password_form': password_form,
        'active_tab': active_tab,
    }
    
    return render(request, 'xrayapp/account_settings.html', context)


def logout_confirmation(request):
    """Display a confirmation page before logging out the user."""
    return render(request, 'registration/logout.html')


# Error handler views
def handler400(request, exception=None):
    """400 Bad Request handler."""
    return render(request, 'errors/400.html', status=400)

def handler401(request, exception=None):
    """401 Unauthorized handler."""
    return render(request, 'errors/401.html', status=401)

def handler403(request, exception=None):
    """403 Forbidden handler."""
    return render(request, 'errors/403.html', status=403)

def handler404(request, exception=None):
    """404 Not Found handler."""
    return render(request, 'errors/404.html', status=404)

def handler408(request, exception=None):
    """408 Request Timeout handler."""
    return render(request, 'errors/408.html', status=408)

def handler429(request, exception=None):
    """429 Too Many Requests handler."""
    return render(request, 'errors/429.html', status=429)

def handler500(request):
    """500 Internal Server Error handler."""
    return render(request, 'errors/500.html', status=500)

def handler502(request):
    """502 Bad Gateway handler."""
    return render(request, 'errors/502.html', status=502)

def handler503(request):
    """503 Service Unavailable handler."""
    return render(request, 'errors/503.html', status=503)

def handler504(request):
    """504 Gateway Timeout handler."""
    return render(request, 'errors/504.html', status=504)
