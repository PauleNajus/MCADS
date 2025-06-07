#!/usr/bin/env python
"""
Manual data migration script for assigning users to existing records.
Run this script to assign all existing XRayImage and PredictionHistory records to the admin user.
"""

import os
import sys
import django

# Setup Django environment
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mcads_project.settings')
django.setup()

from django.contrib.auth.models import User
from xrayapp.models import XRayImage, PredictionHistory


def migrate_existing_data():
    """Migrate existing data to assign users"""
    
    print("=== Data Migration: Assigning Users to Existing Records ===")
    
    try:
        # Get the admin user
        admin_user = User.objects.get(username='admin')
        print(f"Found admin user: {admin_user.username}")
        
        # Check current state
        xrays_no_user = XRayImage.objects.filter(user__isnull=True).count()
        history_no_user = PredictionHistory.objects.filter(user__isnull=True).count()
        
        print(f"\nRecords without user assignment:")
        print(f"  XRayImage: {xrays_no_user}")
        print(f"  PredictionHistory: {history_no_user}")
        
        if xrays_no_user == 0 and history_no_user == 0:
            print("\n✅ All records already have users assigned!")
            return
        
        # Update XRayImage records
        if xrays_no_user > 0:
            updated_xrays = XRayImage.objects.filter(user__isnull=True).update(user=admin_user)
            print(f"\n✅ Updated {updated_xrays} XRayImage records")
        
        # Update PredictionHistory records  
        if history_no_user > 0:
            updated_history = PredictionHistory.objects.filter(user__isnull=True).update(user=admin_user)
            print(f"✅ Updated {updated_history} PredictionHistory records")
        
        print("\n🎉 Migration completed successfully!")
        
        # Verify the migration
        print("\n=== Verification ===")
        for user in User.objects.all():
            user_xrays = XRayImage.objects.filter(user=user).count()
            user_history = PredictionHistory.objects.filter(user=user).count()
            print(f"  {user.username}: {user_xrays} XRays, {user_history} History records")
            
    except User.DoesNotExist:
        print("❌ ERROR: Admin user not found!")
        print("   Please ensure the admin user exists before running this script.")
        print("   You can create it using: python manage.py create_users")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False
    
    return True


if __name__ == "__main__":
    print("This script will assign all existing records to the admin user.")
    response = input("Do you want to continue? (y/N): ")
    
    if response.lower() in ['y', 'yes']:
        migrate_existing_data()
    else:
        print("Migration cancelled.") 