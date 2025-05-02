import torchxrayvision as xrv
import torch

def print_model_structure(model_name):
    print(f"\n=== {model_name} Structure ===")
    if model_name == 'densenet':
        model = xrv.models.DenseNet(weights="densenet121-res224-all")
    else:  # resnet
        model = xrv.models.ResNet(weights="resnet50-res512-all")
        
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

if __name__ == "__main__":
    print_model_structure('densenet')
    print_model_structure('resnet') 