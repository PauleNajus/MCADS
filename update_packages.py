#!/usr/bin/env python3
"""
MCADS Package Update Script
Safely updates outdated Python packages for the Multi-label Chest Abnormality Detection System
"""

import subprocess
import sys
from typing import List, Tuple

def run_command(command: List[str]) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr"""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def backup_requirements():
    """Create a backup of current requirements"""
    print("📋 Creating backup of current requirements...")
    code, stdout, stderr = run_command([sys.executable, "-m", "pip", "freeze"])
    if code == 0:
        with open("requirements_backup.txt", "w") as f:
            f.write(stdout)
        print("✅ Backup saved to requirements_backup.txt")
        return True
    else:
        print(f"❌ Failed to create backup: {stderr}")
        return False

def update_package(package_name: str, version: str = None):
    """Update a single package"""
    if version:
        package_spec = f"{package_name}=={version}"
    else:
        package_spec = package_name
    
    print(f"🔄 Updating {package_name}...")
    code, stdout, stderr = run_command([sys.executable, "-m", "pip", "install", "--upgrade", package_spec])
    
    if code == 0:
        print(f"✅ {package_name} updated successfully")
        return True
    else:
        print(f"❌ Failed to update {package_name}: {stderr}")
        return False

def main():
    print("🏥 MCADS Package Update Script")
    print("=" * 50)
    
    # Create backup first
    if not backup_requirements():
        print("❌ Cannot proceed without backup. Exiting.")
        return 1
    
    # Priority updates (security-related)
    priority_updates = [
        ("Django", "5.2.4"),
        ("Pillow", "11.3.0"),
        ("asgiref", "3.9.1"),
    ]
    
    # Standard updates
    standard_updates = [
        ("numpy", "2.3.1"),
        ("opencv-python", "4.12.0.88"),
        ("matplotlib", "3.10.3"),
        ("python-dateutil", "2.9.0.post0"),
    ]
    
    # Optional updates (larger version jumps)
    optional_updates = [
        ("psutil", "7.0.0"),
        ("python-dotenv", "1.1.1"),
        ("uvicorn", "0.35.0"),
    ]
    
    print("\n🔴 Installing Priority Updates (Security & Core)...")
    failed_priority = []
    for package, version in priority_updates:
        if not update_package(package, version):
            failed_priority.append(package)
    
    if failed_priority:
        print(f"❌ Priority updates failed for: {', '.join(failed_priority)}")
        print("⚠️  Consider manual intervention before proceeding.")
        return 1
    
    print("\n🟡 Installing Standard Updates...")
    failed_standard = []
    for package, version in standard_updates:
        if not update_package(package, version):
            failed_standard.append(package)
    
    print("\n🔵 Optional Updates (Test recommended)...")
    response = input("Install optional updates? (y/N): ").lower().strip()
    if response == 'y':
        failed_optional = []
        for package, version in optional_updates:
            if not update_package(package, version):
                failed_optional.append(package)
    
    print("\n" + "=" * 50)
    print("📊 Update Summary:")
    print(f"✅ Priority updates: {len(priority_updates) - len(failed_priority)}/{len(priority_updates)}")
    print(f"✅ Standard updates: {len(standard_updates) - len(failed_standard)}/{len(standard_updates)}")
    
    if failed_priority or failed_standard:
        print("\n⚠️  Some updates failed. Check logs above.")
        print("💡 You can restore from backup: pip install -r requirements_backup.txt")
    else:
        print("\n🎉 All updates completed successfully!")
        print("💡 Run your tests to ensure everything works correctly.")
    
    # Generate new requirements file
    print("\n📝 Generating updated requirements.txt...")
    code, stdout, stderr = run_command([sys.executable, "-m", "pip", "freeze"])
    if code == 0:
        with open("requirements_updated.txt", "w") as f:
            f.write(stdout)
        print("✅ New requirements saved to requirements_updated.txt")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 