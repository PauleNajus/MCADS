#!/usr/bin/env python
"""
Script to update all existing XRayImage and PredictionHistory records 
with severity levels based on pathology probabilities.
"""
import os
import django
import sys
from pathlib import Path

# Add the project directory to the sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mcads_project.settings')
django.setup()

from xrayapp.models import XRayImage, PredictionHistory


def update_severity_levels():
    """Calculate and update severity levels for all records"""
    # Process XRayImage records
    xrays = XRayImage.objects.all()
    xray_count = xrays.count()
    print(f"Processing {xray_count} XRayImage records...")
    
    for i, xray in enumerate(xrays):
        severity = xray.calculate_severity_level
        if severity is not None:
            xray.severity_level = severity
            xray.save(update_fields=['severity_level'])
        
        # Print progress every 50 records
        if (i + 1) % 50 == 0 or i + 1 == xray_count:
            print(f"  Processed {i + 1}/{xray_count} XRayImage records")
    
    # Process PredictionHistory records
    histories = PredictionHistory.objects.all()
    history_count = histories.count()
    print(f"Processing {history_count} PredictionHistory records...")
    
    for i, history in enumerate(histories):
        severity = history.calculate_severity_level
        if severity is not None:
            history.severity_level = severity
            history.save(update_fields=['severity_level'])
        
        # Print progress every 50 records
        if (i + 1) % 50 == 0 or i + 1 == history_count:
            print(f"  Processed {i + 1}/{history_count} PredictionHistory records")
    
    print("\nDone! Severity levels have been updated for all records.")


if __name__ == "__main__":
    update_severity_levels() 