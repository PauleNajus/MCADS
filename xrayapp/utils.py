import torch
import torch.nn.functional as F
import torchxrayvision as xrv
import skimage.io
import torchvision
import time
import numpy as np
import cv2
import matplotlib.pyplot as plt
from pathlib import Path
import os
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime
from .interpretability import apply_gradcam, apply_pixel_interpretability


def load_model(model_type='densenet'):
    """
    Load the pre-trained torchxrayvision model
    
    Args:
        model_type (str): 'densenet' or 'resnet'
        
    Returns:
        model: Loaded model
        resize_dim (int): Resize dimension for preprocessing
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    if model_type == 'resnet':
        # Load ResNet model - all classes except "Enlarged Cardiomediastinum" and "Lung Lesion"
        model = xrv.models.ResNet(weights="resnet50-res512-all")
        resize_dim = 512
    else:
        # Default to DenseNet with all classes
        model = xrv.models.DenseNet(weights="densenet121-res224-all")
        resize_dim = 224
    
    model.to(device)
    model.eval()
    return model, resize_dim


def extract_image_metadata(image_path):
    """
    Extract metadata from an image file
    
    Args:
        image_path: Path to the image file
        
    Returns:
        dict: Dictionary with metadata (format, size, resolution, date_created)
    """
    try:
        # Ensure image_path is a Path object for cross-platform compatibility
        img_path = Path(image_path)
        
        # Open the image with PIL
        with Image.open(img_path) as img:
            # Get format
            image_format = img.format
            
            # Get resolution
            width, height = img.size
            resolution = f"{width}x{height}"
            
            # Get file size
            file_size_bytes = img_path.stat().st_size
            # Convert to KB or MB as appropriate
            if file_size_bytes < 1024 * 1024:
                size = f"{file_size_bytes / 1024:.1f} KB"
            else:
                size = f"{file_size_bytes / (1024 * 1024):.1f} MB"
            
            # Try to get creation date from EXIF data
            date_created = None
            if hasattr(img, '_getexif') and img._getexif() is not None:
                exif = {
                    TAGS.get(tag, tag): value
                    for tag, value in img._getexif().items()
                }
                if 'DateTimeOriginal' in exif:
                    date_created = datetime.strptime(exif['DateTimeOriginal'], '%Y:%m:%d %H:%M:%S')
            
            # If no EXIF data, use file creation/modification time
            if date_created is None:
                # Use cross-platform stats
                stats = img_path.stat()
                # Try creation time first, then modification time as fallback
                try:
                    # ctime is creation time on Windows, change time on Unix
                    date_created = datetime.fromtimestamp(stats.st_ctime)
                except:
                    # If there's an error, use modification time
                    date_created = datetime.fromtimestamp(stats.st_mtime)
            
            return {
                'format': image_format,
                'size': size,
                'resolution': resolution,
                'date_created': date_created
            }
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        return {
            'format': 'Unknown',
            'size': 'Unknown',
            'resolution': 'Unknown',
            'date_created': None
        }


def process_image(image_path, xray_instance=None, model_type='densenet'):
    """
    Process an X-ray image and return predictions
    If xray_instance is provided, will update progress
    
    Args:
        image_path: Path to the image
        xray_instance: Database instance for progress tracking
        model_type (str): 'densenet' or 'resnet'
    """
    # Update status to processing
    if xray_instance:
        xray_instance.processing_status = 'processing'
        xray_instance.progress = 5
        xray_instance.save()
    
    # Extract and save image metadata
    if xray_instance:
        metadata = extract_image_metadata(image_path)
        xray_instance.image_format = metadata['format']
        xray_instance.image_size = metadata['size']
        xray_instance.image_resolution = metadata['resolution']
        xray_instance.image_date_created = metadata['date_created']
        xray_instance.save()
    
    # Load and preprocess the image
    # Update progress to 10%
    if xray_instance:
        xray_instance.progress = 10
        xray_instance.save()
    
    # Ensure image_path is a Path object, then convert to string for skimage
    image_path = Path(image_path)
    image_path_str = str(image_path)
    
    # Load image
    img = skimage.io.imread(image_path_str)
    
    # Normalize the image
    # Update progress to 20%
    if xray_instance:
        xray_instance.progress = 20
        xray_instance.save()
    
    img = xrv.datasets.normalize(img, 255)
    
    # Check that images are 2D arrays - use first channel instead of averaging
    if len(img.shape) > 2:
        img = img[:, :, 0]
    if len(img.shape) < 2:
        raise ValueError("Input image must have at least 2 dimensions")
    
    # Add channel dimension
    img = img[None, :, :]
    
    # Load model and get resize dimension
    # Update progress to 40%
    if xray_instance:
        xray_instance.progress = 40
        xray_instance.save()
    
    model, resize_dim = load_model(model_type)
    
    # Apply transforms for model
    transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop(),
        xrv.datasets.XRayResizer(resize_dim)
    ])
    img = transform(img)
    
    # Convert to tensor
    img_tensor = torch.from_numpy(img)
    
    # Add batch dimension
    if len(img_tensor.shape) < 3:
        img_tensor = img_tensor.unsqueeze(0).unsqueeze(0)
    elif len(img_tensor.shape) == 3:
        img_tensor = img_tensor.unsqueeze(0)
    
    # Get device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    img_tensor = img_tensor.to(device)
    model = model.to(device)
    
    # Update progress to 60%
    if xray_instance:
        xray_instance.progress = 60
        xray_instance.save()
    
    # Get predictions
    # Update progress to 75%
    if xray_instance:
        xray_instance.progress = 75
        xray_instance.save()
    
    with torch.no_grad():
        # Use the model's forward method for both model types
        preds = model(img_tensor).cpu()
    
    # Create a dictionary of pathology predictions
    # Use the model's pathologies attribute directly
    pathologies = model.pathologies
    results = dict(zip(pathologies, preds[0].detach().numpy()))
    
    # Filter out specific classes for ResNet if needed
    if model_type == 'resnet':
        excluded_classes = ["Enlarged Cardiomediastinum", "Lung Lesion"]
        results = {k: v for k, v in results.items() if k not in excluded_classes}
    # For DenseNet, ensure we include all classes (no filtering)
    
    # Update progress to 90%
    if xray_instance:
        xray_instance.progress = 90
        xray_instance.save()
        
        # Add a small delay to ensure progress is displayed
        time.sleep(0.5)
        
        # Update status to completed and progress to 100%
        xray_instance.progress = 100
        xray_instance.processing_status = 'completed'
        xray_instance.save()
    
    return results 


def process_image_with_interpretability(image_path, xray_instance=None, model_type='densenet', interpretation_method=None, target_class=None):
    """
    Process an X-ray image with interpretability visualization
    
    Args:
        image_path: Path to the image
        xray_instance: Database instance for progress tracking
        model_type: 'densenet' or 'resnet'
        interpretation_method: 'gradcam' or 'pli' or None
        target_class: Target class for interpretability visualization
        
    Returns:
        Dictionary with predictions and interpretability results
    """
    # Update status to processing if xray_instance is provided
    if xray_instance:
        xray_instance.processing_status = 'processing'
        xray_instance.progress = 5
        xray_instance.save()
    
    # Convert Path to string
    if isinstance(image_path, Path):
        image_path = str(image_path)
    
    # Extract image metadata
    metadata = extract_image_metadata(image_path)
    
    # Run standard image processing to get predictions
    if xray_instance:
        xray_instance.progress = 50
        xray_instance.save()
        
    results = process_image(image_path, None, model_type)  # Don't update xray_instance here
    
    # Apply interpretability method if requested
    interpretation_results = {}
    if interpretation_method:
        if xray_instance:
            xray_instance.progress = 75
            xray_instance.save()
            
        if interpretation_method == 'gradcam':
            # Apply Grad-CAM
            cam_results = apply_gradcam(image_path, model_type, target_class)
            interpretation_results = {
                'method': 'gradcam',
                'original': cam_results['original'],
                'heatmap': cam_results['heatmap'],
                'overlay': cam_results['overlay'],
                'target_class': cam_results['target_class'],
                'metadata': metadata  # Include metadata
            }
        elif interpretation_method == 'pli':
            # Apply Pixel-Level Interpretability
            pli_results = apply_pixel_interpretability(image_path, model_type, target_class)
            interpretation_results = {
                'method': 'pli',
                'original': pli_results['original'],
                'saliency_map': pli_results['saliency_map'],
                'saliency_colored': pli_results['saliency_colored'],
                'target_class': pli_results['target_class'],
                'metadata': metadata  # Include metadata
            }
    
    # Update status to completed if xray_instance is provided
    if xray_instance:
        # Add a small delay to ensure progress is displayed
        time.sleep(0.5)
        xray_instance.progress = 100
        xray_instance.processing_status = 'completed'
        xray_instance.save()
    
    # Include metadata in the final results
    final_results = {**results, **interpretation_results}
    if 'metadata' not in final_results:
        final_results['metadata'] = metadata
    
    return final_results


def save_interpretability_visualization(interpretation_results, output_path, format='png'):
    """
    Save interpretability visualization to a file
    
    Args:
        interpretation_results: Results from process_image_with_interpretability
        output_path: Path to save the visualization
        format: Image format to save (png, jpg, etc.)
        
    Returns:
        Path to saved file
    """
    # Create figure with subplots
    plt.figure(figsize=(12, 4))
    
    # Plot original image
    plt.subplot(1, 3, 1)
    plt.imshow(interpretation_results['original'], cmap='gray')
    plt.title('Original X-ray')
    plt.axis('off')
    
    # Plot method-specific visualizations
    if interpretation_results.get('method') == 'gradcam':
        # Plot heatmap
        plt.subplot(1, 3, 2)
        plt.imshow(interpretation_results['heatmap'], cmap='jet')
        plt.title(f'Grad-CAM Heatmap\n{interpretation_results["target_class"]}')
        plt.axis('off')
        
        # Plot overlay
        plt.subplot(1, 3, 3)
        plt.imshow(cv2.cvtColor(interpretation_results['overlay'], cv2.COLOR_BGR2RGB))
        plt.title('Grad-CAM Overlay')
        plt.axis('off')
    
    elif interpretation_results.get('method') == 'pli':
        # Plot saliency map
        plt.subplot(1, 3, 2)
        plt.imshow(interpretation_results['saliency_map'], cmap='hot')
        plt.title(f'Pixel Saliency Map\n{interpretation_results["target_class"]}')
        plt.axis('off')
        
        # Plot colored saliency
        plt.subplot(1, 3, 3)
        plt.imshow(interpretation_results['saliency_colored'])
        plt.title('Colored Saliency')
        plt.axis('off')
    
    # Add image metadata as text if available
    if 'metadata' in interpretation_results:
        metadata = interpretation_results['metadata']
        metadata_text = f"Format: {metadata.get('format', 'Unknown')} | Size: {metadata.get('size', 'Unknown')} | Resolution: {metadata.get('resolution', 'Unknown')}"
        plt.figtext(0.5, 0.01, metadata_text, ha='center', fontsize=8, bbox={"facecolor":"lightgray", "alpha":0.5, "pad":5})
    
    # Save the figure with metadata preserved
    plt.tight_layout()
    plt.savefig(output_path, format=format, dpi=300, bbox_inches='tight', metadata={'Interpretation': interpretation_results.get('method', 'Unknown'), 
                                                                                    'Target': interpretation_results.get('target_class', 'Unknown')})
    plt.close()
    
    return output_path 