#!/usr/bin/env python

import os
import sys
import subprocess
from pathlib import Path
import platform

def setup_venv():
    """Create and activate a virtual environment"""
    print("Setting up virtual environment...")
    # Create the virtual environment
    if not Path(".venv").exists():
        subprocess.check_call([sys.executable, "-m", "venv", ".venv"])
        print("Virtual environment created!")
    else:
        print("Virtual environment already exists")
    
    # Instructions for activating the virtual environment
    system = platform.system()
    if system == "Windows":
        activate_script = ".venv\\Scripts\\activate"
        print(f"\nTo activate the virtual environment, run:\n{activate_script}")
    else:
        activate_script = "source .venv/bin/activate"
        print(f"\nTo activate the virtual environment, run:\n{activate_script}")

def install_requirements():
    """Install project requirements"""
    print("\nInstalling dependencies...")
    
    # Instructions based on the operating system
    system = platform.system()
    if system == "Windows":
        pip_path = ".venv\\Scripts\\pip"
    else:
        pip_path = ".venv/bin/pip"
    
    # Install dependencies
    try:
        subprocess.check_call([pip_path, "install", "-r", "requirements.txt"])
        print("All dependencies installed successfully!")
    except subprocess.CalledProcessError:
        print("Failed to install dependencies. Make sure to activate your virtual environment first.")
        sys.exit(1)

def setup_django():
    """Run Django setup commands"""
    print("\nSetting up Django project...")
    
    # Detect the Python executable in the virtual environment
    system = platform.system()
    if system == "Windows":
        python_path = ".venv\\Scripts\\python"
    else:
        python_path = ".venv/bin/python"
    
    # Create .env file if it doesn't exist
    if not Path(".env").exists():
        print("Creating .env file...")
        with open(".env", "w") as f:
            f.write("""# Django settings
DEBUG=True
SECRET_KEY=django-insecure-=d1*cs*9j%ofw)11j9mbkn(!1su@!+)(2rcy9pl*s17*n=ej(z
ALLOWED_HOSTS=localhost,127.0.0.1
""")
    
    # Run Django migrations
    try:
        print("Running migrations...")
        subprocess.check_call([python_path, "manage.py", "migrate"])
        
        # Collect static files
        print("Collecting static files...")
        subprocess.check_call([python_path, "manage.py", "collectstatic", "--noinput"])
        
        print("\nDjango setup completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error during Django setup: {e}")
        sys.exit(1)

def create_directories():
    """Create necessary directories if they don't exist"""
    print("\nCreating necessary directories...")
    
    # Create media directory if it doesn't exist
    media_dir = Path("media")
    if not media_dir.exists():
        media_dir.mkdir()
        print("Created media directory")
    
    # Create media/uploads directory if it doesn't exist
    uploads_dir = media_dir / "uploads"
    if not uploads_dir.exists():
        uploads_dir.mkdir()
        print("Created media/uploads directory")
    
    # Create static directory if it doesn't exist
    static_dir = Path("static")
    if not static_dir.exists():
        static_dir.mkdir()
        print("Created static directory")
    
    # Create staticfiles directory if it doesn't exist
    staticfiles_dir = Path("staticfiles")
    if not staticfiles_dir.exists():
        staticfiles_dir.mkdir()
        print("Created staticfiles directory")

def main():
    """Main setup function"""
    print("Setting up LDCS18 project...\n")
    
    # Setup virtual environment
    setup_venv()
    
    # Create necessary directories
    create_directories()
    
    # Check if requirements should be installed
    install_req = input("\nDo you want to install dependencies now? (y/n): ").lower()
    if install_req == 'y':
        install_requirements()
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