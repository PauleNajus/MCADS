# mcads

A Django web application for analyzing chest X-ray images using the TorchXRayVision library and pre-trained ResNet50 model.

## Features

- Upload chest X-ray images for analysis
- Automatic detection of 14+ pathological conditions
- Visualization of pathology probabilities
- Responsive UI with Bootstrap 5
- Light and dark mode support
- Professional medical color scheme

## Technology Stack

- Python 3.11.9
- Django 5.2
- PyTorch 2.7.0
- TorchXRayVision 1.3.4
- Bootstrap 5.3.5
- SQLite 3.49.1

## Installation

### Quick Setup (Recommended)

1. Clone the repository:

```bash
git clone https://github.com/yourusername/mcads.git
cd mcads
```

1. Run the setup script:

```bash
# On Windows
python setup.py

# On Linux/Mac
python3 setup.py
```

1. Follow the prompts to set up your virtual environment, install dependencies, and configure Django.

1. Start the development server:

```bash
# On Windows
.\.venv\Scripts\activate
python manage.py runserver

# On Linux/Mac
source .venv/bin/activate
python manage.py runserver
```

### Manual Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/mcads.git
cd mcads
```

1. Create and activate a virtual environment:

```bash
# On Windows
python -m venv .venv
.\.venv\Scripts\activate

# On Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

1. Install dependencies:

```bash
pip install -r requirements.txt
```

1. Create a .env file in the project root with the following content:

```text
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
```

1. Run migrations:

```bash
python manage.py migrate
```

1. Collect static files:

```bash
python manage.py collectstatic
```

1. Start the development server:

```bash
python manage.py runserver
```

1. Open your browser and navigate to <http://127.0.0.1:8000/>

### Additional Steps for Linux Users

If you're on Linux, you may need to install additional system dependencies for PyTorch and image processing libraries:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-dev libjpeg-dev zlib1g-dev
```

## Usage

1. Upload a chest X-ray image (JPG, PNG, or DICOM format)
1. Wait for the analysis to complete
1. View the pathology prediction results
1. Toggle between light and dark modes using the theme toggle button in the navigation bar

## Model Details

The application uses pre-trained models from TorchXRayVision:

- **DenseNet121** (default): 224px resolution, trained on all classes
- **ResNet50**: 512px resolution, trained on all classes

These models are trained on large datasets of chest X-rays to detect various pathological conditions including:

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Effusion
- Emphysema
- Fibrosis
- Hernia
- Infiltration
- Mass
- Nodule
- Pleural Thickening
- Pneumonia
- Pneumothorax

## Cross-Platform Compatibility

This project is designed to work across different operating systems:

- Windows
- Linux (Ubuntu, Debian, Fedora, CentOS, Arch)
- macOS

All paths are handled using Python's `pathlib` library to ensure cross-platform compatibility.

### Linux-Specific Setup

The application is fully compatible with modern Linux distributions. For the best experience, follow these distribution-specific instructions:

#### Ubuntu/Debian

```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3-dev python3-pip python3-venv libjpeg-dev zlib1g-dev libopenblas-dev

# Create and set up the project
git clone https://github.com/yourusername/mcads.git
cd mcads
chmod +x run_linux.sh
./run_linux.sh
```

#### Fedora

```bash
# Install system dependencies
sudo dnf install -y python3-devel python3-pip libjpeg-turbo-devel zlib-devel openblas-devel

# Create and set up the project
git clone https://github.com/yourusername/mcads.git
cd mcads
chmod +x run_linux.sh
./run_linux.sh
```

#### Arch Linux

```bash
# Install system dependencies
sudo pacman -Sy python python-pip libjpeg-turbo zlib openblas

# Create and set up the project
git clone https://github.com/yourusername/mcads.git
cd mcads
chmod +x run_linux.sh
./run_linux.sh
```

#### CentOS/RHEL

```bash
# Install system dependencies
sudo yum install -y python3-devel python3-pip libjpeg-devel zlib-devel openblas-devel

# Create and set up the project
git clone https://github.com/yourusername/mcads.git
cd mcads
chmod +x run_linux.sh
./run_linux.sh
```

### GPU Support on Linux

For GPU acceleration with NVIDIA GPUs on Linux:

1. Install the appropriate NVIDIA drivers for your distribution
1. Install CUDA and cuDNN following the [official PyTorch documentation](https://pytorch.org/get-started/locally/)

Example for Ubuntu with CUDA 12.1:

```bash
# Add NVIDIA repository
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update

# Install CUDA
sudo apt-get -y install cuda-toolkit-12-1

# Add CUDA to your path
echo 'export PATH=/usr/local/cuda-12.1/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# Verify installation
nvcc --version
```

After installing CUDA, you can set up the project as usual. The application will automatically detect and use your GPU if available.

### File Permissions on Linux

If you encounter permission issues with media uploads:

```bash
# Set correct permissions for media directory
chmod -R 755 media/
```

For production environments, ensure your web server user has appropriate permissions:

```bash
# For Nginx/Apache with www-data user
sudo chown -R www-data:www-data media/
```

## Acknowledgements

This project uses the [TorchXRayVision](https://github.com/mlmed/torchxrayvision) library by Joseph Paul Cohen et al.

## License

This project is licensed under the [MIT License](LICENSE).

