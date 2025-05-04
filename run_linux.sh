#!/bin/bash

# Make sure script stops on errors
set -e

echo "====================================================="
echo "  Setting up Chest X-Ray Analysis Application (ldcs)"
echo "====================================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MINIMUM_VERSION="3.8"
if [ "$(printf '%s\n' "$MINIMUM_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$MINIMUM_VERSION" ]; then
    echo "Error: Python version $PYTHON_VERSION is less than the required minimum version $MINIMUM_VERSION"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "Virtual environment created successfully!"
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check for GPU availability
if python3 -c "import torch; print(torch.cuda.is_available())" | grep -q "True"; then
    echo "GPU is available for PyTorch acceleration!"
else
    echo "No GPU detected. The application will run on CPU only."
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# Django settings
DEBUG=True
SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
ALLOWED_HOSTS=localhost,127.0.0.1
EOF
    echo ".env file created with a secure random secret key!"
else
    echo ".env file already exists."
fi

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create media directories if they don't exist
if [ ! -d "media/uploads" ]; then
    echo "Creating media directories..."
    mkdir -p media/uploads
fi

# Set proper permissions for media directory
echo "Setting proper permissions..."
chmod -R 755 media

# Success message
echo "====================================================="
echo "Setup completed successfully!"
echo "====================================================="
echo ""
echo "Starting Django development server..."
echo "You can access the application at http://127.0.0.1:8000/"
echo ""
echo "Press Ctrl+C to stop the server when you're done."
echo "====================================================="

# Start Django development server
python manage.py runserver 