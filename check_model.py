#!/usr/bin/env python
import torchxrayvision as xrv
import torch
import sys
from pathlib import Path

def print_model_structure(model_name):
    print(f"\n=== {model_name} Structure ===")
    try:
        if model_name == 'densenet':
            model = xrv.models.DenseNet(weights="densenet121-res224-all")
        else:  # resnet
            model = xrv.models.ResNet(weights="resnet50-res512-all")
        
        # Print pathologies information
        print(f"\nModel pathologies ({len(model.pathologies)} total):")
        print(model.pathologies)
        
        print(f"\nDefault pathologies ({len(xrv.datasets.default_pathologies)} total):")
        print(xrv.datasets.default_pathologies)
        
        # Check for differences
        if model_name == 'resnet':
            print("\nDifferences between model.pathologies and default_pathologies:")
            model_set = set(model.pathologies)
            default_set = set(xrv.datasets.default_pathologies)
            
            only_in_model = model_set - default_set
            only_in_default = default_set - model_set
            
            if only_in_model:
                print(f"Only in model.pathologies: {only_in_model}")
            if only_in_default:
                print(f"Only in default_pathologies: {only_in_default}")
        
        # Print model structure
        print(f"\nLayers that might be suitable for GradCAM:")
        for name, module in model.named_modules():
            if isinstance(module, torch.nn.Conv2d) and 'conv' in name.lower():
                print(f"Layer: {name}, Type: {type(module).__name__}")
        
        # For DenseNet, print the structure of denseblock4
        if model_name == 'densenet' and hasattr(model, 'features') and hasattr(model.features, 'denseblock4'):
            print("\nDenseblock4 structure:")
            for name, module in model.features.denseblock4.named_modules():
                if isinstance(module, torch.nn.Conv2d):
                    print(f"Layer: {name}, Type: {type(module).__name__}")
        
        # For ResNet, print the structure of layer4
        if model_name == 'resnet' and hasattr(model, 'layer4'):
            print("\nLayer4 structure:")
            for name, module in model.layer4.named_modules():
                if isinstance(module, torch.nn.Conv2d):
                    print(f"Layer: {name}, Type: {type(module).__name__}")
    except Exception as e:
        print(f"Error loading {model_name} model: {e}")
        return False
    
    return True

def check_cuda_availability():
    """Check if CUDA is available for PyTorch"""
    cuda_available = torch.cuda.is_available()
    print(f"\nCUDA Available: {cuda_available}")
    
    if cuda_available:
        device_count = torch.cuda.device_count()
        print(f"Number of CUDA devices: {device_count}")
        
        for i in range(device_count):
            device_name = torch.cuda.get_device_name(i)
            print(f"Device {i}: {device_name}")
    else:
        print("Running on CPU mode. Models will be slower to run.")
    
    return cuda_available

if __name__ == "__main__":
    print("Checking PyTorch and TorchXRayVision compatibility...")
    
    # Check CUDA availability
    check_cuda_availability()
    
    # Create models directory if it doesn't exist
    models_dir = Path("models")
    if not models_dir.exists():
        try:
            models_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created models directory at {models_dir.absolute()}")
        except Exception as e:
            print(f"Warning: Could not create models directory: {e}")
    
    # Check models
    densenet_ok = print_model_structure('densenet')
    resnet_ok = print_model_structure('resnet')
    
    if densenet_ok and resnet_ok:
        print("\nAll models loaded successfully!")
        sys.exit(0)
    else:
        print("\nWarning: Some models failed to load properly.")
        sys.exit(1) 