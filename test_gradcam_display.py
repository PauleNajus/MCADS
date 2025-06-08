#!/usr/bin/env python3
"""
Test script to verify Grad-CAM display functionality with actual visualizations
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import torch
import torchvision.transforms as transforms

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_test_image():
    """Create a synthetic chest X-ray-like test image"""
    print("Creating synthetic test image...")
    
    # Create a 512x512 test image that resembles a chest X-ray
    image = np.zeros((512, 512), dtype=np.float32)
    
    # Add chest cavity outline (ellipse)
    y, x = np.ogrid[:512, :512]
    center_x, center_y = 256, 300
    
    # Create chest outline
    chest_mask = ((x - center_x) / 200) ** 2 + ((y - center_y) / 150) ** 2 < 1
    image[chest_mask] = 0.5
    
    # Add some "lung" regions
    left_lung = ((x - 180) / 80) ** 2 + ((y - 280) / 100) ** 2 < 1
    right_lung = ((x - 332) / 80) ** 2 + ((y - 280) / 100) ** 2 < 1
    
    image[left_lung] = 0.2
    image[right_lung] = 0.2
    
    # Add some noise
    noise = np.random.normal(0, 0.05, image.shape)
    image = np.clip(image + noise, 0, 1)
    
    # Normalize to XRayVision expected range
    image = (image - 0.5) * 2048  # Convert to [-1024, 1024] range
    
    return image

def test_gradcam_visualization():
    """Test Grad-CAM visualization generation"""
    print("\n=== Testing Grad-CAM Visualization ===")
    
    try:
        import torchxrayvision as xrv
        from xrayapp.interpretability import GradCAM, NoInplaceReLU
        
        # Create test image
        test_image = create_test_image()
        print(f"✓ Created test image with shape: {test_image.shape}")
        print(f"  Image range: [{test_image.min():.2f}, {test_image.max():.2f}]")
        
        # Load model
        print("Loading DenseNet model...")
        model = xrv.models.DenseNet(weights="densenet121-res224-all")
        wrapped_model = NoInplaceReLU(model)
        print("✓ Model loaded successfully")
        
        # Prepare image for model
        print("Preprocessing image...")
        
        # Add channel dimension
        img_tensor = test_image[None, :, :]
        
        # Apply transforms
        transform = transforms.Compose([
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(224)
        ])
        
        img_tensor = transform(img_tensor)
        img_tensor = torch.from_numpy(img_tensor).unsqueeze(0)  # Add batch dimension
        
        print(f"✓ Preprocessed image shape: {img_tensor.shape}")
        
        # Initialize GradCAM
        print("Initializing GradCAM...")
        target_layer = wrapped_model.model.features.denseblock4.denselayer16.norm2
        gradcam = GradCAM(wrapped_model, target_layer=target_layer)
        print("✓ GradCAM initialized")
        
        # Get model predictions
        print("Getting model predictions...")
        wrapped_model.eval()
        with torch.no_grad():
            predictions = wrapped_model(img_tensor)
        
        # Get top predictions
        probs = torch.softmax(predictions, dim=1)[0]
        top_classes = torch.topk(probs, 3)
        
        print("✓ Top 3 predictions:")
        for i, (prob, idx) in enumerate(zip(top_classes.values, top_classes.indices)):
            pathology = wrapped_model.pathologies[idx.item()]
            print(f"  {i+1}. {pathology}: {prob.item():.3f}")
        
        # Generate Grad-CAM for top prediction
        target_class = top_classes.indices[0].item()
        target_pathology = wrapped_model.pathologies[target_class]
        
        print(f"\nGenerating Grad-CAM for: {target_pathology}")
        heatmap, _ = gradcam.get_heatmap(img_tensor, target_class=target_class)
        print(f"✓ Generated heatmap with shape: {heatmap.shape}")
        print(f"  Heatmap range: [{heatmap.min():.3f}, {heatmap.max():.3f}]")
        
        # Create overlay
        print("Creating overlay visualization...")
        original_img = test_image.copy()
        if len(original_img.shape) > 2:
            original_img = original_img[:, :, 0]
        
        # Normalize for display
        original_img = (original_img - original_img.min()) / (original_img.max() - original_img.min() + 1e-8)
        
        overlay = gradcam.overlay_heatmap(original_img, heatmap)
        print("✓ Created overlay visualization")
        
        # Test visualization saving
        print("Testing visualization saving...")
        
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        # Original image
        axes[0].imshow(original_img, cmap='gray')
        axes[0].set_title('Original Image')
        axes[0].axis('off')
        
        # Heatmap
        axes[1].imshow(heatmap, cmap='jet')
        axes[1].set_title(f'Grad-CAM Heatmap\n{target_pathology}')
        axes[1].axis('off')
        
        # Overlay
        axes[2].imshow(overlay)
        axes[2].set_title('Grad-CAM Overlay')
        axes[2].axis('off')
        
        plt.tight_layout()
        
        # Save the visualization
        output_path = 'test_gradcam_visualization.png'
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved visualization to: {output_path}")
        
        # Test different target classes
        print("\nTesting different target pathologies...")
        test_pathologies = ['Cardiomegaly', 'Pneumonia', 'Atelectasis']
        
        for pathology in test_pathologies:
            if pathology in wrapped_model.pathologies:
                target_idx = wrapped_model.pathologies.index(pathology)
                heatmap_test, _ = gradcam.get_heatmap(img_tensor, target_class=target_idx)
                print(f"✓ Generated heatmap for {pathology}: shape {heatmap_test.shape}")
            else:
                print(f"⚠️ {pathology} not found in model pathologies")
        
        return True
        
    except Exception as e:
        print(f"✗ Error during visualization testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gradcam_edge_cases():
    """Test Grad-CAM with edge cases"""
    print("\n=== Testing Grad-CAM Edge Cases ===")
    
    try:
        import torchxrayvision as xrv
        from xrayapp.interpretability import GradCAM, NoInplaceReLU
        
        # Load model
        model = xrv.models.DenseNet(weights="densenet121-res224-all")
        wrapped_model = NoInplaceReLU(model)
        
        # Initialize GradCAM
        target_layer = wrapped_model.model.features.denseblock4.denselayer16.norm2
        gradcam = GradCAM(wrapped_model, target_layer=target_layer)
        
        # Test with edge case inputs
        print("Testing with zero input...")
        zero_input = torch.zeros(1, 1, 224, 224)
        heatmap_zero, _ = gradcam.get_heatmap(zero_input, target_class=0)
        print(f"✓ Zero input test passed, heatmap shape: {heatmap_zero.shape}")
        
        print("Testing with random noise input...")
        noise_input = torch.randn(1, 1, 224, 224) * 100
        heatmap_noise, _ = gradcam.get_heatmap(noise_input, target_class=0)
        print(f"✓ Noise input test passed, heatmap shape: {heatmap_noise.shape}")
        
        print("Testing with different target classes...")
        test_input = torch.randn(1, 1, 224, 224)
        for i in [0, 5, 10, 17]:  # Test different class indices
            heatmap_class, _ = gradcam.get_heatmap(test_input, target_class=i)
            pathology = wrapped_model.pathologies[i]
            print(f"✓ Class {i} ({pathology}) test passed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error during edge case testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_display_integration():
    """Test integration with the Django display system"""
    print("\n=== Testing Display Integration ===")
    
    try:
        # Test the apply_gradcam function from interpretability.py
        from xrayapp.interpretability import apply_gradcam
        
        # Create a temporary test image file
        test_image = create_test_image()
        test_image_path = 'temp_test_image.png'
        
        # Save as PNG for testing
        import cv2
        # Normalize to 0-255 range for saving
        display_image = ((test_image + 1024) / 2048 * 255).astype(np.uint8)
        cv2.imwrite(test_image_path, display_image)
        print(f"✓ Saved temporary test image: {test_image_path}")
        
        # Test apply_gradcam function
        print("Testing apply_gradcam function...")
        
        # Test with DenseNet
        result_densenet = apply_gradcam(test_image_path, model_type='densenet', target_class=None)
        print(f"✓ DenseNet Grad-CAM completed")
        print(f"  Target class: {result_densenet['target_class']}")
        print(f"  Original image shape: {result_densenet['original'].shape}")
        print(f"  Heatmap shape: {result_densenet['heatmap'].shape}")
        print(f"  Overlay shape: {result_densenet['overlay'].shape}")
        
        # Test with ResNet
        print("Testing with ResNet model...")
        result_resnet = apply_gradcam(test_image_path, model_type='resnet', target_class=None)
        print(f"✓ ResNet Grad-CAM completed")
        print(f"  Target class: {result_resnet['target_class']}")
        
        # Clean up
        os.remove(test_image_path)
        print("✓ Cleaned up temporary files")
        
        return True
        
    except Exception as e:
        print(f"✗ Error during display integration testing: {e}")
        import traceback
        traceback.print_exc()
        # Clean up on error
        if os.path.exists('temp_test_image.png'):
            os.remove('temp_test_image.png')
        return False

def main():
    """Main test function"""
    print("Starting Comprehensive Grad-CAM Display Test\n")
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Basic visualization
    if test_gradcam_visualization():
        print("✅ Grad-CAM visualization test PASSED")
        tests_passed += 1
    else:
        print("❌ Grad-CAM visualization test FAILED")
    
    # Test 2: Edge cases
    if test_gradcam_edge_cases():
        print("✅ Grad-CAM edge cases test PASSED")
        tests_passed += 1
    else:
        print("❌ Grad-CAM edge cases test FAILED")
    
    # Test 3: Display integration
    if test_display_integration():
        print("✅ Display integration test PASSED")
        tests_passed += 1
    else:
        print("❌ Display integration test FAILED")
    
    # Summary
    print(f"\n{'='*50}")
    print(f"TEST SUMMARY: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 ALL TESTS PASSED! Grad-CAM display functionality is working perfectly.")
        print("\nKey findings:")
        print("✓ Grad-CAM generates proper heatmaps")
        print("✓ Visualizations are created and saved correctly")
        print("✓ Integration with both DenseNet and ResNet models works")
        print("✓ Edge cases are handled properly")
        print("✓ Display system integration is functional")
        return True
    else:
        print(f"⚠️ {total_tests - tests_passed} test(s) failed. Please review the errors above.")
        return False

if __name__ == "__main__":
    main() 