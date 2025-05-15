#!/usr/bin/env python3
"""
Pre-deployment check script for MCADS
Verifies system requirements and tests PyTorch/torchxrayvision functionality
"""

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path
import importlib.util
import multiprocessing
import psutil

def print_header(message):
    """Print a formatted header message"""
    print("\n" + "=" * 80)
    print(f" {message}")
    print("=" * 80)

def check_python_version():
    """Check if Python version is compatible"""
    print_header("Checking Python version")
    required_version = (3, 11)
    current_version = sys.version_info
    
    print(f"Required Python version: {required_version[0]}.{required_version[1]}+")
    print(f"Current Python version: {current_version.major}.{current_version.minor}.{current_version.micro}")
    
    if current_version.major != required_version[0] or current_version.minor < required_version[1]:
        print("❌ Python version check failed")
        return False
    
    print("✅ Python version check passed")
    return True

def check_memory():
    """Check if system has enough memory"""
    print_header("Checking system memory")
    
    total_ram = psutil.virtual_memory().total / (1024 ** 3)  # Convert to GB
    swap = psutil.swap_memory().total / (1024 ** 3)  # Convert to GB
    
    print(f"Available RAM: {total_ram:.2f} GB")
    print(f"Available swap: {swap:.2f} GB")
    
    min_ram = 1.8  # Minimum 1.8 GB required
    
    if total_ram < min_ram and swap < 2:
        print("❌ Memory check failed - not enough RAM and swap space")
        print("   Recommended: At least 2GB RAM or 4GB swap")
        return False
    
    print("✅ Memory check passed")
    return True

def check_disk_space():
    """Check if there's enough disk space"""
    print_header("Checking disk space")
    
    # Get the disk usage of the current directory
    disk_usage = shutil.disk_usage('/')
    free_space_gb = disk_usage.free / (1024 ** 3)
    
    print(f"Free disk space: {free_space_gb:.2f} GB")
    
    if free_space_gb < 5:
        print("❌ Disk space check failed - less than 5GB available")
        return False
    
    print("✅ Disk space check passed")
    return True

def check_dependencies():
    """Check if required Python packages are installed"""
    print_header("Checking Python dependencies")
    
    required_packages = [
        'django==5.2',
        'django-bootstrap5==25.1',
        'torch==2.3.0',
        'torchvision==0.18.0',
        'torchxrayvision==0.0.38',
        'gunicorn==21.2.0',
        'uvicorn==0.27.1'
    ]
    
    missing_packages = []
    for package_spec in required_packages:
        package_name = package_spec.split('==')[0]
        try:
            spec = importlib.util.find_spec(package_name)
            if spec is None:
                missing_packages.append(package_spec)
                continue
                
            # Check if it's PyTorch - we need to ensure it's CPU only
            if package_name == 'torch':
                import torch
                print(f"PyTorch version: {torch.__version__}")
                print(f"PyTorch CUDA available: {torch.cuda.is_available()}")
                print(f"PyTorch device: {torch.device('cuda' if torch.cuda.is_available() else 'cpu')}")
                
            # For other packages, just print the version
            if package_name not in ['torch']:
                module = importlib.import_module(package_name)
                if hasattr(module, '__version__'):
                    print(f"{package_name} version: {module.__version__}")
                else:
                    print(f"{package_name} installed (version unknown)")
        except ImportError:
            missing_packages.append(package_spec)
    
    if missing_packages:
        print("❌ Dependency check failed - missing packages:")
        for package in missing_packages:
            print(f"  - {package}")
        return False
    
    print("✅ Dependency check passed")
    return True

def test_pytorch():
    """Test basic PyTorch functionality"""
    print_header("Testing PyTorch")
    
    try:
        import torch
        import numpy as np
        
        # Create random tensor
        x = torch.rand(5, 3)
        print("Random tensor:")
        print(x)
        
        # Perform basic operation
        y = torch.tensor([[1.0, 2.0], [3.0, 4.0]])
        z = y + y
        print("\nBasic addition:")
        print(z)
        
        # Memory usage test
        print("\nMemory usage test:")
        # Try to create a large tensor (1GB) to check memory handling
        try:
            large_tensor_size = 1024 * 1024 * 256  # 1GB (in float32)
            initial_memory = psutil.virtual_memory().used / (1024 * 1024)
            print(f"Memory before large tensor: {initial_memory:.2f} MB")
            
            large_tensor = torch.rand(large_tensor_size, dtype=torch.float32)
            peak_memory = psutil.virtual_memory().used / (1024 * 1024)
            print(f"Memory after large tensor: {peak_memory:.2f} MB")
            print(f"Memory increase: {peak_memory - initial_memory:.2f} MB")
            
            # Clean up
            del large_tensor
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            final_memory = psutil.virtual_memory().used / (1024 * 1024)
            print(f"Memory after cleanup: {final_memory:.2f} MB")
            
        except Exception as e:
            print(f"Large tensor creation failed: {e}")
            print("This might indicate memory constraints, but the server might still work with smaller batches")
        
        print("✅ PyTorch test passed")
        return True
        
    except Exception as e:
        print(f"❌ PyTorch test failed: {e}")
        return False

def test_torchxrayvision():
    """Test torchxrayvision model loading"""
    print_header("Testing torchxrayvision")
    
    try:
        import torchxrayvision as xrv
        import torch
        
        print("Loading DenseNet model...")
        model = xrv.models.DenseNet(weights="densenet121-res224-all")
        print(f"Model loaded successfully with {len(model.pathologies)} pathologies")
        
        # Create a dummy image
        dummy_img = torch.ones((1, 1, 224, 224))
        
        print("\nRunning inference on dummy image...")
        with torch.no_grad():
            outputs = model(dummy_img)
        
        print(f"Inference successful, output shape: {outputs.shape}")
        
        print("✅ torchxrayvision test passed")
        return True
        
    except Exception as e:
        print(f"❌ torchxrayvision test failed: {e}")
        print("Error details:", str(e))
        return False

def check_database():
    """Check if Django can connect to the database"""
    print_header("Checking Django database connection")
    
    try:
        import django
        from django.conf import settings
        from django.core.management import call_command
        
        # Setup Django environment
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mcads_project.settings')
        django.setup()
        
        # Check if we can connect to the database
        from django.db import connections
        connections['default'].ensure_connection()
        
        # Check migrations status
        print("\nMigration status:")
        call_command('showmigrations')
        
        print("✅ Database check passed")
        return True
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

def run_all_checks():
    """Run all deployment checks"""
    print_header("MCADS Deployment Checks")
    
    checks = [
        ("Python Version", check_python_version),
        ("System Memory", check_memory),
        ("Disk Space", check_disk_space),
        ("Python Dependencies", check_dependencies),
        ("PyTorch Functionality", test_pytorch),
        ("TorchXRayVision Functionality", test_torchxrayvision),
        ("Django Database", check_database)
    ]
    
    results = {}
    for name, check_func in checks:
        results[name] = check_func()
    
    print_header("Deployment Check Summary")
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All checks passed! The system is ready for deployment.")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_checks()) 