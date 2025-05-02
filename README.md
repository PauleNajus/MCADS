# LDCS18

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
git clone https://github.com/yourusername/LDCS18.git
cd LDCS18
```

2. Run the setup script:
```bash
# On Windows
python setup.py

# On Linux/Mac
python3 setup.py
```

3. Follow the prompts to set up your virtual environment, install dependencies, and configure Django.

4. Start the development server:
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
git clone https://github.com/yourusername/LDCS18.git
cd LDCS18
```

2. Create and activate a virtual environment:
```bash
# On Windows
python -m venv .venv
.\.venv\Scripts\activate

# On Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a .env file in the project root with the following content:
```
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Collect static files:
```bash
python manage.py collectstatic
```

7. Start the development server:
```bash
python manage.py runserver
```

8. Open your browser and navigate to http://127.0.0.1:8000/

### Additional Steps for Linux Users

If you're on Linux, you may need to install additional system dependencies for PyTorch and image processing libraries:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-dev libjpeg-dev zlib1g-dev
```

## Usage

1. Upload a chest X-ray image (JPG, PNG, or DICOM format)
2. Wait for the analysis to complete
3. View the pathology prediction results
4. Toggle between light and dark modes using the theme toggle button in the navigation bar

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
- Linux
- macOS

All paths are handled using Python's `pathlib` library to ensure cross-platform compatibility.

## Acknowledgements

This project uses the [TorchXRayVision](https://github.com/mlmed/torchxrayvision) library by Joseph Paul Cohen et al.

## License

This project is licensed under the [MIT License](LICENSE). 