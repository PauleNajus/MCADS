#!/usr/bin/env python
"""Test script to verify user separation in history records"""

import os
import sys
import django

# Setup Django environment
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mcads_project.settings')
django.setup()

from django.contrib.auth.models import User
from xrayapp.models import XRayImage, PredictionHistory


def test_user_separation():
    """Test that history records are properly separated by user"""
    
    print("=== Testing User Separation ===")
    
    # Get users
    users = User.objects.all()
    print(f"Available users: {[u.username for u in users]}")
    
    # Check existing XRayImage records
    total_xrays = XRayImage.objects.count()
    print(f"\nTotal XRay records: {total_xrays}")
    
    # Check XRay records by user
    for user in users:
        user_xrays = XRayImage.objects.filter(user=user).count()
        print(f"  {user.username}: {user_xrays} XRay records")
        
    # Check existing PredictionHistory records
    total_history = PredictionHistory.objects.count()
    print(f"\nTotal History records: {total_history}")
    
    # Check History records by user
    for user in users:
        user_history = PredictionHistory.objects.filter(user=user).count()
        print(f"  {user.username}: {user_history} History records")
        
    # Check for records without users
    xrays_no_user = XRayImage.objects.filter(user__isnull=True).count()
    history_no_user = PredictionHistory.objects.filter(user__isnull=True).count()
    
    print(f"\nRecords without user assignment:")
    print(f"  XRays: {xrays_no_user}")
    print(f"  History: {history_no_user}")
    
    if xrays_no_user > 0 or history_no_user > 0:
        print("\n⚠️  WARNING: Some records don't have users assigned!")
        print("   Consider running the migration to assign them to admin user.")
    else:
        print("\n✅ All records have users assigned!")


if __name__ == "__main__":
    test_user_separation() 