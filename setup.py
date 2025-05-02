#!/usr/bin/env python

import os
import sys
import subprocess
from pathlib import Path
import platform
import shutil

def setup_venv():
    """Create and activate a virtual environment"""
    print("Setting up virtual environment...")
    venv_path = Path(".venv")
    
    # Create the virtual environment
    if not venv_path.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
        print("Virtual environment created!")
    else:
        print("Virtual environment already exists")
    
    # Instructions for activating the virtual environment
    system = platform.system()
    if system == "Windows":
        activate_script = str(venv_path / "Scripts" / "activate")
        print(f"\nTo activate the virtual environment, run:\n{activate_script}")
    else:
        activate_script = f"source {venv_path}/bin/activate"
        print(f"\nTo activate the virtual environment, run:\n{activate_script}")
    
    return venv_path

def install_requirements():
    """Install project requirements"""
    print("\nInstalling dependencies...")
    
    # Get the correct pip path based on OS
    venv_path = Path(".venv")
    system = platform.system()
    if system == "Windows":
        pip_path = venv_path / "Scripts" / "pip"
    else:
        pip_path = venv_path / "bin" / "pip"
    
    # Install dependencies
    try:
        subprocess.check_call([str(pip_path), "install", "--upgrade", "pip"])
        subprocess.check_call([str(pip_path), "install", "-r", "requirements.txt"])
        print("All dependencies installed successfully!")
    except subprocess.CalledProcessError:
        print("Failed to install dependencies. Make sure to activate your virtual environment first.")
        sys.exit(1)

def setup_django():
    """Run Django setup commands"""
    print("\nSetting up Django project...")
    
    # Detect the Python executable in the virtual environment
    venv_path = Path(".venv")
    system = platform.system()
    if system == "Windows":
        python_path = venv_path / "Scripts" / "python"
    else:
        python_path = venv_path / "bin" / "python"
    
    # Create .env file if it doesn't exist
    env_file = Path(".env")
    if not env_file.exists():
        print("Creating .env file...")
        with open(env_file, "w") as f:
            f.write("""# Django settings
DEBUG=True
SECRET_KEY=django-insecure-=d1*cs*9j%ofw)11j9mbkn(!1su@!+)(2rcy9pl*s17*n=ej(z
ALLOWED_HOSTS=localhost,127.0.0.1
""")
    
    # Run Django migrations
    try:
        print("Running migrations...")
        subprocess.check_call([str(python_path), "manage.py", "migrate"])
        
        # Collect static files
        print("Collecting static files...")
        subprocess.check_call([str(python_path), "manage.py", "collectstatic", "--noinput"])
        
        print("\nDjango setup completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error during Django setup: {e}")
        sys.exit(1)

def create_directories():
    """Create necessary directories if they don't exist"""
    print("\nCreating necessary directories...")
    
    # Create media directory and subdirectories
    media_dir = Path("media")
    uploads_dir = media_dir / "uploads"
    
    for directory in [media_dir, uploads_dir]:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            print(f"Created {directory} directory")
    
    # Create static directory
    static_dir = Path("static")
    if not static_dir.exists():
        static_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created {static_dir} directory")
    
    # Create staticfiles directory
    staticfiles_dir = Path("staticfiles")
    if not staticfiles_dir.exists():
        staticfiles_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created {staticfiles_dir} directory")
    
    # Set appropriate permissions on Linux
    if platform.system() != "Windows":
        for directory in [media_dir, uploads_dir]:
            try:
                directory.chmod(0o755)  # rwxr-xr-x
            except Exception as e:
                print(f"Warning: Could not set permissions on {directory}: {e}")

def check_gpu_support():
    """Check if GPU support is available"""
    print("\nChecking for GPU support...")
    
    try:
        # Get the correct python path based on OS
        venv_path = Path(".venv")
        system = platform.system()
        if system == "Windows":
            python_path = venv_path / "Scripts" / "python"
        else:
            python_path = venv_path / "bin" / "python"
        
        # Run a Python script to check for GPU support
        result = subprocess.run(
            [str(python_path), "-c", "import torch; print(torch.cuda.is_available())"],
            capture_output=True,
            text=True
        )
        
        if "True" in result.stdout:
            print("GPU support is available! Model inference will be accelerated.")
        else:
            print("GPU support is not available. The application will run on CPU only.")
    except Exception as e:
        print(f"Could not check GPU support: {e}")
        print("The application will default to CPU mode.")

def main():
    """Main setup function"""
    print("Setting up LDCS18 project...\n")
    
    # Setup virtual environment
    venv_path = setup_venv()
    
    # Create necessary directories
    create_directories()
    
    # Check if requirements should be installed
    install_req = input("\nDo you want to install dependencies now? (y/n): ").lower()
    if install_req == 'y':
        install_requirements()
        check_gpu_support()
    else:
        print("\nSkipping dependency installation.")
        print("Remember to activate your virtual environment and run 'pip install -r requirements.txt' before proceeding.")
    
    # Check if Django setup should be run
    setup_django_now = input("\nDo you want to set up the Django project now? (y/n): ").lower()
    if setup_django_now == 'y':
        setup_django()
    else:
        print("\nSkipping Django setup.")
        print("Remember to run the following commands after activating your virtual environment:")
        print("  python manage.py migrate")
        print("  python manage.py collectstatic")
    
    print("\nSetup process completed!")
    print("\nTo start the development server, activate your virtual environment and run:")
    print("  python manage.py runserver")

if __name__ == "__main__":
    main() 