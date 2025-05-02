#!/usr/bin/env python
# coding: utf-8

import matplotlib.pyplot as plt
import numpy as np
import argparse
import skimage
import skimage.io
import pprint
import os
import sys
from pathlib import Path

import torch
import torch.nn.functional as F
import torchvision
import torchvision.transforms

import torchxrayvision as xrv


def load_model(model_type):
    """
    Load the selected model with appropriate weights
    
    Args:
        model_type (str): Type of model to load ('densenet' or 'resnet')
    
    Returns:
        model: The loaded model
        resize_dim: Resize dimension for images
    """
    try:
        if model_type == 'resnet':
            # ResNet model with all classes
            model = xrv.models.ResNet(weights="resnet50-res512-all")
            resize_dim = 512
        else:
            # DenseNet model with all classes
            model = xrv.models.DenseNet(weights="densenet121-res224-all")
            resize_dim = 224
        
        return model, resize_dim
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)


def filter_problematic_classes(model_name, predictions):
    """
    Filter out potentially problematic classes from predictions
    
    Args:
        model_name (str): Name of the model
        predictions (dict): Dictionary of pathology predictions
    
    Returns:
        dict: Filtered predictions
    """
    # Check for potentially problematic classes (values close to 0.5 might indicate untrained outputs)
    filtered_predictions = predictions.copy()
    suspicious_classes = []
    
    for pathology, value in predictions.items():
        if abs(value - 0.5) < 0.001:  # Very close to 0.5
            suspicious_classes.append(pathology)
            del filtered_predictions[pathology]
    
    if suspicious_classes:
        print(f"\nWARNING: The {model_name} model may have issues with the following classes:")
        for cls in suspicious_classes:
            print(f"  - {cls}: {predictions[cls]}")
        print("These classes have been filtered out from the results as they appear to be untrained.")
    
    return filtered_predictions


def check_predictions(model_name, predictions):
    """
    Check for potential issues with model predictions
    
    Args:
        model_name (str): Name of the model being checked
        predictions (dict): Dictionary of pathology predictions
    
    Returns:
        dict: The same predictions dictionary
    """
    # Check for potentially problematic classes (values close to 0.5 might indicate untrained outputs)
    suspicious_classes = []
    for pathology, value in predictions.items():
        if abs(value - 0.5) < 0.001:  # Very close to 0.5
            suspicious_classes.append(pathology)
    
    if suspicious_classes:
        print(f"\nWARNING: The {model_name} model may have issues with the following classes:")
        for cls in suspicious_classes:
            print(f"  - {cls}: {predictions[cls]}")
        print("These values are very close to 0.5, which might indicate these classes are not properly trained in this model.")
    
    return predictions


def load_and_preprocess_image(img_path):
    """
    Load and preprocess an image for model input
    
    Args:
        img_path (str): Path to the image file
    
    Returns:
        numpy.ndarray: Preprocessed image
    """
    try:
        # Load the image
        img = skimage.io.imread(img_path)
        
        # Convert 8-bit image to [-1024, 1024] range
        img = xrv.datasets.normalize(img, 255)
        
        # Check that images are 2D arrays
        if len(img.shape) > 2:
            img = img[:, :, 0]  # Take first channel instead of averaging
        if len(img.shape) < 2:
            raise ValueError("Error: dimension lower than 2 for image")
        
        # Add color channel
        img = img[None, :, :]
        
        return img
    except Exception as e:
        print(f"Error processing image {img_path}: {e}")
        sys.exit(1)


# Example usage directly in the script
def process_image_example():
    """Run an example test on sample images or generated dummy images"""
    # Prepare the image:
    sample_path = Path("00000001_000.png")
    if sample_path.exists():
        img = load_and_preprocess_image(sample_path)
    else:
        print("Sample image not found, using dummy image")
        dummy_img = np.ones((512, 512)) * 128  # Generate dummy image
        img = xrv.datasets.normalize(dummy_img, 255)
        img = img[None, :, :]
    
    # First test DenseNet
    print("\nTesting DenseNet model:")
    densenet_transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop(),
        xrv.datasets.XRayResizer(224)
    ])
    densenet_img = densenet_transform(img)
    densenet_img = torch.from_numpy(densenet_img)
    
    densenet_model = xrv.models.DenseNet(weights="densenet121-res224-all")
    print(f"DenseNet model has {len(densenet_model.pathologies)} pathologies: {densenet_model.pathologies}")
    densenet_outputs = densenet_model(densenet_img[None, ...])
    
    # Use model's own pathologies for consistent labeling
    densenet_results = dict(zip(densenet_model.pathologies, densenet_outputs[0].detach().numpy()))
    print("DenseNet predictions:")
    pprint.pprint(densenet_results)
    
    # Next test ResNet
    print("\nTesting ResNet model:")
    resnet_transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop(),
        xrv.datasets.XRayResizer(512)
    ])
    resnet_img = resnet_transform(img)
    resnet_img = torch.from_numpy(resnet_img)
    
    resnet_model = xrv.models.ResNet(weights="resnet50-res512-all")
    print(f"ResNet model has {len(resnet_model.pathologies)} pathologies: {resnet_model.pathologies}")
    resnet_outputs = resnet_model(resnet_img[None, ...])
    
    # Use model's own pathologies for consistent labeling
    resnet_results = dict(zip(resnet_model.pathologies, resnet_outputs[0].detach().numpy()))
    print("Raw ResNet predictions:")
    pprint.pprint(resnet_results)
    
    # Filter problematic classes
    filtered_resnet_results = filter_problematic_classes("ResNet", resnet_results)
    print("\nFiltered ResNet predictions:")
    pprint.pprint(filtered_resnet_results)
    
    return {"densenet": densenet_results, "resnet": filtered_resnet_results}


def main():
    """Main function for CLI usage"""
    parser = argparse.ArgumentParser(description="Analyze chest X-ray images using TorchXRayVision models")
    parser.add_argument('-f', type=str, default="", help='')
    parser.add_argument('img_path', type=str, nargs='?', default=None, help='Path to the X-ray image')
    parser.add_argument('-model', type=str, default="densenet",
                        choices=['densenet', 'resnet'],
                        help='Model type to use: "densenet" (DenseNet121, 224px, all classes) or "resnet" (ResNet50, 512px, filtered classes)')
    parser.add_argument('-feats', default=False,
                        help='Return features instead of predictions',
                        action='store_true')
    parser.add_argument('-cuda', default=False,
                        help='Use CUDA for processing',
                        action='store_true')
    parser.add_argument('-display', default=False,
                        help='Display the image and predictions',
                        action='store_true')
    parser.add_argument('-example', default=False,
                        help='Run the example code directly',
                        action='store_true')
    cfg = parser.parse_args()
    
    # Run the example directly if requested
    if cfg.example:
        process_image_example()
        return
    
    # Ensure img_path is provided if not in example mode
    if cfg.img_path is None:
        parser.error("img_path is required unless -example is used")
    
    # Load and preprocess the image
    img = load_and_preprocess_image(cfg.img_path)
    
    # Load model based on selected type
    model, resize_dim = load_model(cfg.model)
    
    # Apply transforms
    transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop(),
        xrv.datasets.XRayResizer(resize_dim)
    ])
    img = transform(img)
    
    # Convert to tensor
    img_tensor = torch.from_numpy(img)
    
    output = {}
    with torch.no_grad():
        # Add batch dimension if not already present
        if len(img_tensor.shape) < 3:
            img_tensor = img_tensor.unsqueeze(0).unsqueeze(0)
        elif len(img_tensor.shape) == 3:
            img_tensor = img_tensor.unsqueeze(0)
        
        if cfg.cuda:
            # Check if CUDA is available before trying to use it
            if not torch.cuda.is_available():
                print("Warning: CUDA requested but not available. Using CPU instead.")
            else:
                img_tensor = img_tensor.cuda()
                model = model.cuda()
                
        # Print tensor shape for debugging
        print(f"Tensor shape before prediction: {img_tensor.shape}")
        print(f"Model has {len(model.pathologies)} pathologies: {model.pathologies}")
        
        if cfg.feats:
            feats = model.features(img_tensor)
            feats = F.relu(feats, inplace=True)
            feats = F.adaptive_avg_pool2d(feats, (1, 1))
            output["feats"] = list(feats.cpu().detach().numpy().reshape(-1))
            
        preds = model(img_tensor).cpu()
        
        # Create a dictionary of pathology predictions
        pathologies = model.pathologies
        results = dict(zip(pathologies, preds[0].detach().numpy()))
        
        # Filter problematic classes if using ResNet
        if cfg.model == 'resnet':
            results = filter_problematic_classes(cfg.model, results)
        
        output["preds"] = results
    
    if cfg.display:
        # Display results
        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        plt.imshow(img[0], cmap='gray')
        plt.title('Input X-ray')
        plt.axis('off')
        
        # Plot top predictions
        plt.subplot(1, 2, 2)
        # Sort predictions by value in descending order
        sorted_preds = sorted(results.items(), key=lambda x: x[1], reverse=True)
        top_n = 10  # Show top 10 predictions
        
        labels = [item[0] for item in sorted_preds[:top_n]]
        values = [item[1] for item in sorted_preds[:top_n]]
        
        plt.barh(range(len(labels)), values)
        plt.yticks(range(len(labels)), labels)
        plt.xlabel('Probability')
        plt.title('Top Pathology Predictions')
        plt.tight_layout()
        plt.show()
    
    # Print results
    print("\nFinal predictions:")
    pprint.pprint(output)
    
    return output


if __name__ == "__main__":
    main()
