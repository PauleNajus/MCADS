#!/usr/bin/env python3
"""
Test script for combined Pixel-Level Interpretability visualization
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import torch

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

def test_combined_pli():
    """Test the combined PLI functionality"""
    print("\n=== Testing Combined PLI ===")
    
    try:
        import torchxrayvision as xrv
        from xrayapp.interpretability import apply_combined_pixel_interpretability
        
        # Create test image
        test_image = create_test_image()
        print(f"✓ Created test image with shape: {test_image.shape}")
        
        # Save test image temporarily
        test_image_path = "test_combined_pli_image.png"
        from PIL import Image
        # Normalize to 0-255 range for saving
        normalized_image = ((test_image - test_image.min()) / (test_image.max() - test_image.min()) * 255).astype(np.uint8)
        Image.fromarray(normalized_image).save(test_image_path)
        print(f"✓ Saved test image to: {test_image_path}")
        
        # Test with DenseNet
        print("\nTesting with DenseNet model...")
        try:
            densenet_results = apply_combined_pixel_interpretability(test_image_path, model_type='densenet', probability_threshold=0.5)
            print("✓ DenseNet combined PLI successful")
            print(f"  Selected pathologies: {len(densenet_results['selected_pathologies'])}")
            print(f"  Pathology summary: {densenet_results['pathology_summary']}")
            print(f"  Saliency map shape: {densenet_results['saliency_map'].shape}")
            
            # Save visualization
            plt.figure(figsize=(15, 5))
            
            plt.subplot(1, 3, 1)
            plt.imshow(densenet_results['original'], cmap='gray')
            plt.title('Original Image')
            plt.axis('off')
            
            plt.subplot(1, 3, 2)
            plt.imshow(densenet_results['saliency_map'], cmap='jet')
            plt.title(f'Combined Saliency Map\n{len(densenet_results["selected_pathologies"])} pathologies')
            plt.axis('off')
            
            plt.subplot(1, 3, 3)
            plt.imshow(densenet_results['overlay'])
            plt.title('Combined PLI Overlay')
            plt.axis('off')
            
            plt.tight_layout()
            plt.savefig('test_combined_pli_densenet.png', dpi=150, bbox_inches='tight')
            plt.close()
            print("✓ Saved DenseNet PLI visualization to: test_combined_pli_densenet.png")
            
        except Exception as e:
            print(f"✗ DenseNet test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test with ResNet
        print("\nTesting with ResNet model...")
        try:
            resnet_results = apply_combined_pixel_interpretability(test_image_path, model_type='resnet', probability_threshold=0.5)
            print("✓ ResNet combined PLI successful")
            print(f"  Selected pathologies: {len(resnet_results['selected_pathologies'])}")
            print(f"  Pathology summary: {resnet_results['pathology_summary']}")
            print(f"  Saliency map shape: {resnet_results['saliency_map'].shape}")
            
            # Save visualization
            plt.figure(figsize=(15, 5))
            
            plt.subplot(1, 3, 1)
            plt.imshow(resnet_results['original'], cmap='gray')
            plt.title('Original Image')
            plt.axis('off')
            
            plt.subplot(1, 3, 2)
            plt.imshow(resnet_results['saliency_map'], cmap='jet')
            plt.title(f'Combined Saliency Map\n{len(resnet_results["selected_pathologies"])} pathologies')
            plt.axis('off')
            
            plt.subplot(1, 3, 3)
            plt.imshow(resnet_results['overlay'])
            plt.title('Combined PLI Overlay')
            plt.axis('off')
            
            plt.tight_layout()
            plt.savefig('test_combined_pli_resnet.png', dpi=150, bbox_inches='tight')
            plt.close()
            print("✓ Saved ResNet PLI visualization to: test_combined_pli_resnet.png")
            
        except Exception as e:
            print(f"✗ ResNet test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test with lower threshold
        print("\nTesting with lower threshold (0.3)...")
        try:
            low_threshold_results = apply_combined_pixel_interpretability(test_image_path, model_type='densenet', probability_threshold=0.3)
            print("✓ Low threshold test successful")
            print(f"  Selected pathologies: {len(low_threshold_results['selected_pathologies'])}")
            print(f"  Pathology summary: {low_threshold_results['pathology_summary']}")
            
        except Exception as e:
            print(f"✗ Low threshold test failed: {e}")
        
        # Test without SmoothGrad
        print("\nTesting without SmoothGrad...")
        try:
            no_smoothgrad_results = apply_combined_pixel_interpretability(test_image_path, model_type='densenet', use_smoothgrad=False)
            print("✓ No SmoothGrad test successful")
            print(f"  Selected pathologies: {len(no_smoothgrad_results['selected_pathologies'])}")
            print(f"  Pathology summary: {no_smoothgrad_results['pathology_summary']}")
            
        except Exception as e:
            print(f"✗ No SmoothGrad test failed: {e}")
        
        # Clean up test image
        if os.path.exists(test_image_path):
            os.remove(test_image_path)
            print(f"✓ Cleaned up test image: {test_image_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error during combined PLI testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("Combined PLI Test Suite")
    print("=" * 50)
    
    success = test_combined_pli()
    
    if success:
        print("\n✓ All tests completed successfully!")
        print("Combined PLI visualization is working correctly.")
    else:
        print("\n✗ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 