#!/usr/bin/env python3
"""
Test script to check Grad-CAM implementation and library versions
"""

import sys
import os

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_library_versions():
    """Check and print versions of all libraries used in Grad-CAM"""
    print("=== Library Version Check ===")
    
    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
    except ImportError as e:
        print(f"PyTorch: ERROR - {e}")
        return False
    
    try:
        import torchvision
        print(f"Torchvision: {torchvision.__version__}")
    except ImportError as e:
        print(f"Torchvision: ERROR - {e}")
        return False
    
    try:
        import cv2
        print(f"OpenCV: {cv2.__version__}")
    except ImportError as e:
        print(f"OpenCV: ERROR - {e}")
        return False
    
    try:
        import matplotlib
        print(f"Matplotlib: {matplotlib.__version__}")
    except ImportError as e:
        print(f"Matplotlib: ERROR - {e}")
        return False
    
    try:
        import numpy as np
        print(f"NumPy: {np.__version__}")
    except ImportError as e:
        print(f"NumPy: ERROR - {e}")
        return False
    
    try:
        import skimage
        print(f"scikit-image: {skimage.__version__}")
    except ImportError as e:
        print(f"scikit-image: ERROR - {e}")
        return False
    
    try:
        import torchxrayvision as xrv
        print(f"TorchXRayVision: {xrv.__version__ if hasattr(xrv, '__version__') else 'version not available'}")
    except ImportError as e:
        print(f"TorchXRayVision: ERROR - {e}")
        return False
    
    print("\n=== Python Version ===")
    print(f"Python: {sys.version}")
    
    return True

def test_gradcam_imports():
    """Test if the Grad-CAM implementation can be imported without errors"""
    print("\n=== Testing Grad-CAM Imports ===")
    
    try:
        # Import step by step to identify issues
        print("Importing GradCAM class...")
        from xrayapp.interpretability import GradCAM
        print("✓ Successfully imported GradCAM")
        
        print("Importing NoInplaceReLU class...")
        from xrayapp.interpretability import NoInplaceReLU
        print("✓ Successfully imported NoInplaceReLU")
        
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Other error: {e}")
        return False

def test_gradcam_basic_functionality():
    """Test basic Grad-CAM functionality without requiring actual images"""
    print("\n=== Testing Basic Grad-CAM Functionality ===")
    
    try:
        import torch
        import torchxrayvision as xrv
        from xrayapp.interpretability import GradCAM, NoInplaceReLU
        
        # Test model loading
        print("Loading DenseNet model...")
        model = xrv.models.DenseNet(weights="densenet121-res224-all")
        wrapped_model = NoInplaceReLU(model)
        print("✓ Model loaded successfully")
        
        # Test GradCAM initialization
        print("Initializing GradCAM...")
        target_layer = wrapped_model.model.features.denseblock4.denselayer16.norm2
        gradcam = GradCAM(wrapped_model, target_layer=target_layer)
        print("✓ GradCAM initialized successfully")
        
        # Test with dummy tensor
        print("Testing with dummy input...")
        dummy_input = torch.randn(1, 1, 224, 224)
        
        # Test forward pass
        with torch.no_grad():
            output = wrapped_model(dummy_input)
        print(f"✓ Forward pass successful, output shape: {output.shape}")
        
        # Test heatmap generation
        heatmap, model_output = gradcam.get_heatmap(dummy_input, target_class=0)
        print(f"✓ Heatmap generation successful, heatmap shape: {heatmap.shape}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_newer_versions():
    """Check if newer versions of libraries are available"""
    print("\n=== Checking for Newer Versions ===")
    
    # Get actual current versions
    try:
        import torch
        current_torch = torch.__version__
    except:
        current_torch = "unknown"
    
    try:
        import torchvision
        current_torchvision = torchvision.__version__
    except:
        current_torchvision = "unknown"
    
    try:
        import cv2
        current_opencv = cv2.__version__
    except:
        current_opencv = "unknown"
    
    try:
        import matplotlib
        current_matplotlib = matplotlib.__version__
    except:
        current_matplotlib = "unknown"
    
    try:
        import numpy as np
        current_numpy = np.__version__
    except:
        current_numpy = "unknown"
    
    try:
        import skimage
        current_skimage = skimage.__version__
    except:
        current_skimage = "unknown"
    
    current_versions = {
        'torch': current_torch,
        'torchvision': current_torchvision,
        'opencv-python': current_opencv,
        'matplotlib': current_matplotlib,
        'numpy': current_numpy,
        'scikit-image': current_skimage
    }
    
    latest_versions = {
        'torch': '2.7.0',
        'torchvision': '0.22.1', 
        'opencv-python': '4.10.0.84',
        'matplotlib': '3.10.0',
        'numpy': '2.2.1',
        'scikit-image': '0.25.0'
    }
    
    print("Current vs Latest versions:")
    updates_needed = []
    for lib, current in current_versions.items():
        latest = latest_versions.get(lib, 'unknown')
        if latest != 'unknown' and current != 'unknown':
            # Simple version comparison
            try:
                current_parts = [int(x) for x in current.split('+')[0].split('.')]
                latest_parts = [int(x) for x in latest.split('.')]
                
                # Pad with zeros to make same length
                max_len = max(len(current_parts), len(latest_parts))
                current_parts.extend([0] * (max_len - len(current_parts)))
                latest_parts.extend([0] * (max_len - len(latest_parts)))
                
                needs_update = current_parts < latest_parts
                status = "⚠️ UPDATE AVAILABLE" if needs_update else "✓ OK"
                if needs_update:
                    updates_needed.append(lib)
            except:
                status = "? CANNOT COMPARE"
        else:
            status = "? UNKNOWN"
        
        print(f"{lib:15}: {current:12} -> {latest:12} {status}")
    
    return updates_needed

def suggest_updates(updates_needed):
    """Suggest how to update libraries"""
    if not updates_needed:
        print("\n✅ All libraries are up to date!")
        return
    
    print(f"\n⚠️ Updates needed for: {', '.join(updates_needed)}")
    print("\nTo update these libraries, run:")
    
    if 'torch' in updates_needed or 'torchvision' in updates_needed:
        print("pip install torch torchvision --upgrade --index-url https://download.pytorch.org/whl/cpu")
    
    other_updates = [lib for lib in updates_needed if lib not in ['torch', 'torchvision']]
    if other_updates:
        lib_names = []
        for lib in other_updates:
            if lib == 'opencv-python':
                lib_names.append('opencv-python')
            elif lib == 'scikit-image':
                lib_names.append('scikit-image')
            else:
                lib_names.append(lib)
        print(f"pip install {' '.join(lib_names)} --upgrade")

def main():
    """Main test function"""
    print("Starting Grad-CAM Library and Functionality Test\n")
    
    # Check library versions
    if not check_library_versions():
        print("❌ Some required libraries are missing or have import errors")
        return False
    
    # Test imports
    if not test_gradcam_imports():
        print("❌ Failed to import Grad-CAM implementation")
        return False
    
    # Test basic functionality
    if not test_gradcam_basic_functionality():
        print("❌ Grad-CAM functionality test failed")
        return False
    
    # Check for newer versions
    updates_needed = check_newer_versions()
    suggest_updates(updates_needed)
    
    print("\n✅ All tests passed! Grad-CAM implementation is working correctly.")
    return True

if __name__ == "__main__":
    main() 