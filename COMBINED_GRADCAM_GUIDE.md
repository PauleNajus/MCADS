# Combined Grad-CAM Visualization Guide

## Overview

The Combined Grad-CAM visualization is a new feature that generates a unified heatmap showing all pathologies with probability values above a specified threshold (default: 0.5). This provides a comprehensive view of multiple potential abnormalities in a single visualization.

## Features

### What it does:
- Automatically identifies all pathologies with probability ≥ 0.5 (or custom threshold)
- Generates individual Grad-CAM heatmaps for each selected pathology
- Combines all heatmaps into a single weighted visualization
- Weights each heatmap by its corresponding probability value
- Normalizes the final combined heatmap for optimal visualization

### Key Benefits:
1. **Comprehensive view**: See multiple pathologies in one visualization
2. **Probability-weighted**: More significant pathologies have stronger influence
3. **Automatic selection**: No need to manually select target pathologies
4. **Fallback mechanism**: Uses top pathology if none exceed threshold

## Usage

### Web Interface
1. Upload an X-ray image and wait for processing to complete
2. Navigate to the "Interpretability" tab
3. Select "Combined Grad-CAM (pathologies > 0.5)" from the interpretation method dropdown
4. Choose your preferred model (DenseNet-121 or ResNet-50)
5. Click "Generate visualization"

### Programmatic Usage

```python
from xrayapp.interpretability import apply_combined_gradcam

# Basic usage with default threshold (0.5)
results = apply_combined_gradcam(
    image_path="path/to/xray.jpg",
    model_type='densenet'  # or 'resnet'
)

# With custom threshold
results = apply_combined_gradcam(
    image_path="path/to/xray.jpg",
    model_type='densenet',
    probability_threshold=0.3
)

# Access results
combined_heatmap = results['heatmap']
selected_pathologies = results['selected_pathologies']
overlay_image = results['overlay']
pathology_summary = results['pathology_summary']
```

## Output Structure

The function returns a dictionary containing:

- `original`: Preprocessed original image
- `heatmap`: Combined Grad-CAM heatmap (numpy array)
- `overlay`: Heatmap overlaid on original image
- `selected_pathologies`: List of (pathology_name, probability) tuples
- `pathology_summary`: Human-readable summary string
- `method`: 'combined_gradcam'
- `threshold`: Probability threshold used

## Technical Implementation

### Algorithm:
1. Load and preprocess the X-ray image
2. Run forward pass to get predictions for all pathologies
3. Apply sigmoid activation to convert logits to probabilities
4. Filter pathologies above the specified threshold
5. For each selected pathology:
   - Generate individual Grad-CAM heatmap
   - Weight by probability value
6. Sum all weighted heatmaps
7. Normalize final result

### Model Support:
- **DenseNet-121**: Uses `densenet121-res224-all` weights
- **ResNet-50**: Uses `resnet50-res512-all` weights
- Both models handle different pathology sets appropriately

### Fallback Behavior:
If no pathologies exceed the threshold, the system:
1. Displays a warning message
2. Shows the top 3 pathologies with their probabilities
3. Uses the highest-probability pathology for visualization

## Example Output

```
Selected pathologies above 0.5 threshold:
  Atelectasis: 0.603
  Consolidation: 0.624
  Infiltration: 0.520
  Pneumothorax: 0.623
  Edema: 0.639
  Emphysema: 0.634
  Fibrosis: 0.532
  Effusion: 0.637
  Pneumonia: 0.623
  Cardiomegaly: 0.570
  Nodule: 0.529
  Mass: 0.532
  Hernia: 0.537
  Lung Lesion: 0.586
  Fracture: 0.632
  Lung Opacity: 0.636
  Enlarged Cardiomediastinum: 0.614
```

## Best Practices

### When to use Combined Grad-CAM:
- When multiple pathologies are detected (≥2 above threshold)
- For comprehensive overview of all potential abnormalities
- When you want to see interaction patterns between pathologies

### When to use regular Grad-CAM:
- When focusing on a specific pathology
- When only one pathology is significantly elevated
- For detailed analysis of individual conditions

### Threshold Selection:
- **0.5**: Default, conservative threshold for clinically significant findings
- **0.3-0.4**: More inclusive, captures borderline cases
- **0.6-0.7**: Very conservative, only strong predictions

## File Storage

Combined Grad-CAM visualizations are stored in:
- Combined view: `media/interpretability/combined_gradcam/combined_gradcam_{id}_threshold_{threshold}.png`
- Heatmap only: `media/interpretability/combined_gradcam/combined_gradcam_heatmap_{id}_threshold_{threshold}.png`
- Overlay only: `media/interpretability/combined_gradcam/combined_gradcam_overlay_{id}_threshold_{threshold}.png`

## Testing

Run the test suite to verify functionality:

```bash
python test_combined_gradcam.py
```

This will test both DenseNet and ResNet models with various thresholds and generate sample visualizations.

## Integration with Existing System

The Combined Grad-CAM feature seamlessly integrates with the existing MCADS system:
- Uses the same database models and storage structure
- Compatible with user authentication and history tracking
- Follows the same processing pipeline as regular Grad-CAM
- Supports both AJAX and standard form submissions 