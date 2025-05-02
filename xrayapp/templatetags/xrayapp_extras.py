from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def get_top_pathology(prediction_history):
    """Get the top pathology (highest probability) from a prediction history item
    Returns a tuple (pathology_name, probability)"""
    pathology_fields = {
        'Atelectasis': prediction_history.atelectasis,
        'Cardiomegaly': prediction_history.cardiomegaly,
        'Consolidation': prediction_history.consolidation,
        'Edema': prediction_history.edema,
        'Effusion': prediction_history.effusion,
        'Emphysema': prediction_history.emphysema,
        'Fibrosis': prediction_history.fibrosis,
        'Hernia': prediction_history.hernia,
        'Infiltration': prediction_history.infiltration,
        'Mass': prediction_history.mass,
        'Nodule': prediction_history.nodule,
        'Pleural_Thickening': prediction_history.pleural_thickening,
        'Pneumonia': prediction_history.pneumonia,
        'Pneumothorax': prediction_history.pneumothorax,
        'Fracture': prediction_history.fracture,
        'Lung Opacity': prediction_history.lung_opacity,
    }
    
    # Add DenseNet-only fields if they exist
    if prediction_history.enlarged_cardiomediastinum is not None:
        pathology_fields['Enlarged Cardiomediastinum'] = prediction_history.enlarged_cardiomediastinum
    if prediction_history.lung_lesion is not None:
        pathology_fields['Lung Lesion'] = prediction_history.lung_lesion
    
    # Filter out None values
    pathology_fields = {k: v for k, v in pathology_fields.items() if v is not None}
    
    # Find the max
    if not pathology_fields:
        return ('None', 0.0)
    
    top_pathology = max(pathology_fields.items(), key=lambda x: x[1])
    return top_pathology

@register.filter
def add_class(field, css_class):
    """Add a CSS class to a form field"""
    return field.as_widget(attrs={"class": css_class}) 