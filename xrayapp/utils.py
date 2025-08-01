import torch
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
from .interpretability import apply_gradcam, apply_pixel_interpretability, apply_combined_gradcam, apply_combined_pixel_interpretability

# CRITICAL FIX: PyTorch CPU backend configuration to prevent 75% stuck issue
import logging
logger = logging.getLogger(__name__)

# PyTorch environment fixes - MUST be set before any PyTorch operations
os.environ['MKLDNN_ENABLED'] = '0'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Force PyTorch to use simple CPU backend to prevent "could not create a primitive" error
torch.backends.mkldnn.enabled = False
torch.set_num_threads(1)

# Additional memory optimizations to prevent model inference hanging
if hasattr(torch.backends, 'openmp'):
    torch.backends.openmp.is_available = lambda: False
if hasattr(torch.backends, 'cudnn'):
    torch.backends.cudnn.enabled = False

logger.info("PyTorch optimized for MCADS - fixes applied to prevent 75% processing hang")


# Global model cache to prevent reloading
_model_cache = {}

def load_model(model_type='densenet'):
    """
    Load the pre-trained torchxrayvision model with memory-efficient caching
    
    Args:
        model_type (str): 'densenet' or 'resnet'
        
    Returns:
        model: Loaded model
        resize_dim (int): Resize dimension for preprocessing
    """
    # Check cache first
    if model_type in _model_cache:
        logger.info(f"Using cached {model_type} model")
        return _model_cache[model_type]
    logger.info(f"Loading {model_type} model...")
    
    # Force CPU to save memory and prevent hardware issues
    device = torch.device("cpu")
    
    # Set cache directory to a writable location and force XRayVision to use it
    cache_dir = os.environ.get('TORCHXRAYVISION_CACHE_DIR', '/app/.torchxrayvision')
    os.makedirs(cache_dir, exist_ok=True)
    
    # Force TorchXRayVision to use our cache directory by setting environment variables
    os.environ['XRV_DATA_DIR'] = cache_dir
    os.environ['TORCHXRAYVISION_CACHE_DIR'] = cache_dir
    os.environ['TORCH_HOME'] = cache_dir
    
    # Also set the HOME environment variable to our cache directory to prevent TorchXRayVision from using /home/mcads
    original_home = os.environ.get('HOME', '')
    os.environ['HOME'] = cache_dir
    
    try:
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
        
        # Cache the model
        _model_cache[model_type] = (model, resize_dim)
        logger.info(f"✅ {model_type} model loaded and cached successfully")
        
        return model, resize_dim
        
    except Exception as e:
        logger.error(f"❌ Failed to load {model_type} model: {e}")
        raise e
    finally:
        # Restore original HOME environment variable
        if original_home:
            os.environ['HOME'] = original_home
        else:
            os.environ.pop('HOME', None)


def clear_model_cache():
    """Clear model cache to free memory"""
    global _model_cache
    logger.info(f"Clearing model cache ({len(_model_cache)} models)")
    _model_cache.clear()
    
    # Force garbage collection
    import gc
    gc.collect()
    
    # Also clear PyTorch cache if available
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def get_memory_info():
    """Get current memory usage information"""
    import psutil
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size in MB
        'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size in MB
        'percent': process.memory_percent(),
        'cached_models': len(_model_cache)
    }


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
            
            # Try to get creation date from EXIF data using proper method
            date_created = None
            try:
                # Use getexif() method instead of _getexif()
                exif_data = img.getexif()
                if exif_data:
                    exif = {
                        TAGS.get(tag, tag): value
                        for tag, value in exif_data.items()
                    }
                    if 'DateTimeOriginal' in exif:
                        date_created = datetime.strptime(exif['DateTimeOriginal'], '%Y:%m:%d %H:%M:%S')
            except (AttributeError, ValueError, TypeError):
                # Fallback if EXIF extraction fails
                pass
            
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
                'name': Path(image_path).name,
                'format': image_format,
                'size': size,
                'resolution': resolution,
                'date_created': date_created
            }
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        return {
            'name': 'Unknown',
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
    # For resnet50-res512-all, we need to resize first, then center crop
    if model_type == 'resnet':
        transform = torchvision.transforms.Compose([
            xrv.datasets.XRayResizer(resize_dim),
            xrv.datasets.XRayCenterCrop()
        ])
    else:
        # For densenet, keep the original order
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
    # For ResNet, ALWAYS use default_pathologies for correct mapping
    if model_type == 'resnet':
        # ResNet model outputs 18 values in the order of default_pathologies
        results = dict(zip(xrv.datasets.default_pathologies, preds[0].detach().numpy()))
    else:
        # For DenseNet, we can use the model's pathologies directly
        results = dict(zip(model.pathologies, preds[0].detach().numpy()))
    
    # Filter out specific classes for ResNet if needed
    # Note: These classes will always output 0.5 for ResNet as they're not trained
    if model_type == 'resnet':
        excluded_classes = ["Enlarged Cardiomediastinum", "Lung Lesion"]
        results = {k: v for k, v in results.items() if k not in excluded_classes}
    
    # If we have an XRay instance, update its severity level
    if xray_instance:
        # Calculate severity level
        xray_instance.severity_level = xray_instance.calculate_severity_level
        
        # Update progress to 90%
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
        elif interpretation_method == 'combined_gradcam':
            # Apply Combined interpretability for pathologies above 0.5 threshold
            combined_results = apply_combined_gradcam(image_path, model_type)
            interpretation_results = {
                'method': 'combined_gradcam',
                'original': combined_results['original'],
                'heatmap': combined_results['heatmap'],
                'overlay': combined_results['overlay'],
                'selected_pathologies': combined_results['selected_pathologies'],
                'pathology_summary': combined_results['pathology_summary'],
                'threshold': combined_results['threshold'],
                'metadata': metadata  # Include metadata
            }
        elif interpretation_method == 'combined_pli':
            # Apply Combined Pixel-Level Interpretability for pathologies above 0.5 threshold
            combined_pli_results = apply_combined_pixel_interpretability(image_path, model_type)
            interpretation_results = {
                'method': 'combined_pli',
                'original': combined_pli_results['original'],
                'saliency_map': combined_pli_results['saliency_map'],
                'saliency_colored': combined_pli_results['saliency_colored'],
                'overlay': combined_pli_results['overlay'],
                'selected_pathologies': combined_pli_results['selected_pathologies'],
                'pathology_summary': combined_pli_results['pathology_summary'],
                'threshold': combined_pli_results['threshold'],
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
        plt.title(f'Heatmap\n{interpretation_results["target_class"]}')
        plt.axis('off')
        
        # Plot overlay
        plt.subplot(1, 3, 3)
        plt.imshow(cv2.cvtColor(interpretation_results['overlay'], cv2.COLOR_BGR2RGB))
        plt.title('Grad-CAM Overlay')
        plt.axis('off')
    
    elif interpretation_results.get('method') == 'combined_gradcam':
        # Plot combined heatmap
        plt.subplot(1, 3, 2)
        plt.imshow(interpretation_results['heatmap'], cmap='jet')
        plt.title(f'Combined Heatmap\n{len(interpretation_results["selected_pathologies"])} pathologies > {interpretation_results["threshold"]}')
        plt.axis('off')
        
        # Plot overlay
        plt.subplot(1, 3, 3)
        plt.imshow(cv2.cvtColor(interpretation_results['overlay'], cv2.COLOR_BGR2RGB))
        plt.title('Combined Overlay')
        plt.axis('off')
    
    elif interpretation_results.get('method') == 'combined_pli':
        # Plot combined saliency map
        plt.subplot(1, 3, 2)
        plt.imshow(interpretation_results['saliency_map'], cmap='jet')
        plt.title(f'Combined PLI Saliency\n{len(interpretation_results["selected_pathologies"])} pathologies > {interpretation_results["threshold"]}')
        plt.axis('off')
        
        # Plot overlay
        plt.subplot(1, 3, 3)
        plt.imshow(interpretation_results['overlay'])
        plt.title('Combined PLI Overlay')
        plt.axis('off')
    
    elif interpretation_results.get('method') == 'pli':
        # Plot saliency map
        plt.subplot(1, 3, 2)
        plt.imshow(interpretation_results['saliency_map'], cmap='jet')
        plt.title(f'Saliency Map\n{interpretation_results["target_class"]}')
        plt.axis('off')
        
        # Plot overlay rather than colored saliency
        plt.subplot(1, 3, 3)
        plt.imshow(interpretation_results['overlay'])
        plt.title('Pixel-Level Overlay')
        plt.axis('off')
    
    # Add image metadata as text if available
    if 'metadata' in interpretation_results:
        metadata = interpretation_results['metadata']
        metadata_text = f"Image: {metadata.get('name', 'Unknown')} | Format: {metadata.get('format', 'Unknown')} | Size: {metadata.get('size', 'Unknown')} | Resolution: {metadata.get('resolution', 'Unknown')}"
        plt.figtext(0.5, 0.01, metadata_text, ha='center', fontsize=8, bbox={"facecolor":"lightgray", "alpha":0.5, "pad":5})
    
    # Save the figure with metadata preserved
    plt.tight_layout()
    plt.savefig(output_path, format=format, dpi=300, bbox_inches='tight', metadata={'Interpretation': interpretation_results.get('method', 'Unknown'), 
                                                                                    'Target': interpretation_results.get('target_class', 'Unknown')})
    plt.close()
    
    return output_path


def save_overlay_visualization(interpretation_results, output_path, format='png'):
    """
    Save only the overlay visualization to a file for pixel-level interpretability without white spaces
    
    Args:
        interpretation_results: Results from apply_pixel_interpretability
        output_path: Path to save the visualization
        format: Image format to save (png, jpg, etc.)
        
    Returns:
        Path to saved file
    """
    if 'overlay' in interpretation_results:
        # Get the overlay data (should already be in proper RGB format)
        overlay = interpretation_results['overlay']
        
        # Save directly as image without matplotlib padding
        from PIL import Image
        Image.fromarray(overlay).save(output_path, format=format.upper())
    
    return output_path


def save_saliency_map(interpretation_results, output_path, format='png'):
    """
    Save only the saliency map to a file for pixel-level interpretability without white spaces
    
    Args:
        interpretation_results: Results from apply_pixel_interpretability
        output_path: Path to save the visualization
        format: Image format to save (png, jpg, etc.)
        
    Returns:
        Path to saved file
    """
    if 'saliency_map' in interpretation_results:
        # Get the saliency map data
        saliency_map = interpretation_results['saliency_map']
        
        # Apply colormap to saliency map (convert to 0-255 range)
        saliency_colored = cv2.applyColorMap(np.uint8(255 * saliency_map), cv2.COLORMAP_JET)  # type: ignore
        
        # Convert BGR to RGB for proper color display
        saliency_rgb = cv2.cvtColor(saliency_colored, cv2.COLOR_BGR2RGB)
        
        # Save directly as image without matplotlib padding
        from PIL import Image
        Image.fromarray(saliency_rgb).save(output_path, format=format.upper())
    
    return output_path


def save_heatmap(interpretation_results, output_path, format='png'):
    """
    Save only the heatmap to a file without white spaces
    
    Args:
        interpretation_results: Results from interpretability analysis
        output_path: Path to save the visualization
        format: Image format to save (png, jpg, etc.)
        
    Returns:
        Path to saved file
    """
    if 'heatmap' in interpretation_results and 'original' in interpretation_results:
        # Get the heatmap data and original image dimensions
        heatmap = interpretation_results['heatmap']
        original_shape = interpretation_results['original'].shape
        
        # Resize heatmap to match original image dimensions
        heatmap_resized = cv2.resize(heatmap, (original_shape[1], original_shape[0]))
        
        # Apply colormap to heatmap (convert to 0-255 range)
        heatmap_colored = cv2.applyColorMap(np.uint8(255 * heatmap_resized), cv2.COLORMAP_JET)  # type: ignore
        
        # Convert BGR to RGB for proper color display
        heatmap_rgb = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
        
        # Save directly as image without matplotlib padding
        from PIL import Image
        Image.fromarray(heatmap_rgb).save(output_path, format=format.upper())
    
    return output_path


def save_overlay(interpretation_results, output_path, format='png'):
    """
    Save only the overlay to a file without white spaces
    
    Args:
        interpretation_results: Results from interpretability analysis
        output_path: Path to save the visualization
        format: Image format to save (png, jpg, etc.)
        
    Returns:
        Path to saved file
    """
    if 'overlay' in interpretation_results:
        # Get the overlay data (already in RGB format from overlay_heatmap method)
        overlay = interpretation_results['overlay']
        
        # Convert BGR to RGB if needed (overlay_heatmap returns BGR format)
        overlay_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
        
        # Save directly as image without matplotlib padding
        from PIL import Image
        Image.fromarray(overlay_rgb).save(output_path, format=format.upper())
    
    return output_path 