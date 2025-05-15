# Deployment Guide for mcads on Ubuntu 22.04 (Low Memory Server)

This guide will help you deploy the mcads Django project on Ubuntu 22.04 with limited resources (2GB RAM) using Gunicorn (with ASGI), Nginx, and systemd.

## Server Specifications

- Operating System: Ubuntu 22.04 blank (64-bit)
- IPv4 Address: 162.0.223.203
- Hostname: ldcs18.com
- Disk Space: 40 GB
- Memory: 2 GB (limited)
- Swap: 17 MB (will be increased)

## 1. Pre-deployment Check

Before deploying the application, run the pre-deployment check script to verify that the server meets the requirements:

```bash
# Install the check requirements
pip install -r requirements.check.txt

# Run the check script
python check_deployment.py
```

The script will check:
- Python version
- System memory and swap space
- Available disk space
- PyTorch and torchxrayvision functionality
- Database connectivity

## 2. Automated Deployment

For automated deployment, use the provided script:

```bash
sudo bash deploy_to_production.sh
```

This script will:
1. Set up a 4GB swap file (critical for PyTorch on a 2GB server)
2. Install required packages
3. Create a virtual environment and install dependencies
4. Install the CPU-only version of PyTorch to save memory
5. Configure Gunicorn with memory optimizations
6. Set up Nginx and SSL

## 3. Manual Deployment Steps

If you prefer to deploy manually, follow these steps:

### Server Preparation

Update your system packages:

```bash
sudo apt update
sudo apt upgrade -y
```

Install required packages:

```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip nginx certbot python3-certbot-nginx build-essential
```

### Set Up Swap Space (Critical for 2GB RAM Server)

```bash
# Check if swap exists
swapon --show

# Create 4GB swap file if none exists
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make swap persistent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Optimize swap settings
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
echo 'vm.vfs_cache_pressure=50' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Project Setup

Clone the repository and set up the project:

```bash
git clone https://your-repository-url.git /var/www/mcads
cd /var/www/mcads
```

Create a virtual environment and install dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

# Install CPU-only PyTorch to save memory
pip install torch==2.3.0 torchvision==0.18.0 --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
pip install -r requirements.production.txt
```

### Environment Configuration

Create `.env.production` in the project root:

```bash
DEBUG=False
SECRET_KEY=your_secure_random_key_here
ALLOWED_HOSTS=ldcs18.com,www.ldcs18.com,162.0.223.203
PYTORCH_NO_CUDA=1
PYTORCH_CPU_ONLY=1
DJANGO_SETTINGS_MODULE=mcads_project.settings
```

Generate a secure random key with:

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Database and Static Files

```bash
source .venv/bin/activate
export $(cat .env.production | xargs)
python manage.py collectstatic --no-input
python manage.py migrate
```

### Gunicorn Configuration for Low Memory

Create a memory-optimized Gunicorn configuration (`gunicorn_config.py`):

```python
import multiprocessing

# Gunicorn configuration file for Django ASGI application
bind = "unix:/run/gunicorn.sock"
# Low memory configuration for 2GB server
workers = 2  # Just 2 workers for low memory server
threads = 2
worker_class = "uvicorn.workers.UvicornWorker"  # Use Uvicorn worker for ASGI
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 5
errorlog = "/var/log/gunicorn/error.log"
accesslog = "/var/log/gunicorn/access.log"
loglevel = "info"
proc_name = "mcads_asgi"
# Memory optimization
worker_tmp_dir = "/dev/shm"
```

Create the log directory:

```bash
sudo mkdir -p /var/log/gunicorn
sudo chown -R www-data:www-data /var/log/gunicorn
```

### Systemd Service with Memory Limits

Create a systemd service file (`/etc/systemd/system/mcads.service`):

```ini
[Unit]
Description=mcads Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/mcads
ExecStart=/var/www/mcads/.venv/bin/gunicorn -c gunicorn_config.py mcads_project.asgi:application
Restart=on-failure
# Memory optimizations
MemoryLow=512M
MemoryHigh=1.5G
MemoryMax=1.8G
Environment="PYTHONOPTIMIZE=1"
Environment="PATH=/var/www/mcads/.venv/bin:/usr/bin"
Environment="PYTORCH_NO_CUDA=1"
Environment="PYTORCH_CPU_ONLY=1"
EnvironmentFile=/var/www/mcads/.env.production

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcads
sudo systemctl start mcads
```

### Nginx Configuration

Create an Nginx configuration file (`/etc/nginx/sites-available/mcads.conf`):

```nginx
server {
    listen 80;
    server_name ldcs18.com www.ldcs18.com;
    
    # Static files
    location /static/ {
        alias /var/www/mcads/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
    
    # Media files
    location /media/ {
        alias /var/www/mcads/media/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
    
    # Proxy requests to Gunicorn
    location / {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
        client_max_body_size 20M;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    # Logging
    access_log /var/log/nginx/mcads_access.log;
    error_log /var/log/nginx/mcads_error.log;
}
```

Enable the configuration:

```bash
sudo ln -s /etc/nginx/sites-available/mcads.conf /etc/nginx/sites-enabled/
sudo nginx -t  # Test the configuration
sudo systemctl reload nginx
```

### SSL with Let's Encrypt

```bash
sudo certbot --nginx -d ldcs18.com -d www.ldcs18.com
```

### Security Measures

```bash
# Set up automatic security updates
sudo apt install -y unattended-upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades << EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# Set up firewall
sudo apt install -y ufw
sudo ufw allow 'Nginx Full'
sudo ufw allow 'OpenSSH'
sudo ufw --force enable
```

### Set Proper Permissions

```bash
sudo chown -R www-data:www-data /var/www/mcads
sudo chmod -R 755 /var/www/mcads/media
sudo chmod -R 755 /var/www/mcads/staticfiles
```

## 4. Memory Optimization for PyTorch

The server has only 2GB of RAM, which is tight for running PyTorch. The following optimizations are applied:

1. Using CPU-only PyTorch to save memory
2. Adding a 4GB swap file to prevent out-of-memory errors
3. Limiting Gunicorn to 2 workers
4. Using systemd memory limits to prevent the application from consuming all memory
5. Setting environment variables to ensure PyTorch doesn't try to use CUDA

## 5. Monitoring the Application

Check the status of your application:

```bash
sudo systemctl status mcads
```

View logs:

```bash
sudo journalctl -u mcads
sudo tail -f /var/log/nginx/mcads_error.log
sudo tail -f /var/log/gunicorn/error.log
```

Monitor memory usage:

```bash
# Real-time memory monitoring
htop

# Memory usage of the Gunicorn process
ps -o pid,user,%mem,command ax | grep gunicorn
```

## 6. Troubleshooting

### Out of Memory Issues

If you see "Killed" messages in the logs or the application crashes:

1. Check if swap is being used:
   ```bash
   free -h
   ```

2. Consider reducing Gunicorn workers to 1:
   ```python
   # In gunicorn_config.py
   workers = 1
   ```

3. Limit batch sizes in the PyTorch application code

### Slow Performance

The CPU-only PyTorch will be slower than the GPU version. For better performance:

1. Consider precomputing results for common inputs
2. Implement caching for model predictions
3. Use smaller model variants if possible

### Socket Permission Issues

Make sure the socket directory has the right permissions:

```bash
sudo mkdir -p /run/gunicorn
sudo chown www-data:www-data /run/gunicorn
```

## 7. Maintenance

To update the application:

```bash
cd /var/www/mcads
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
sudo systemctl restart mcads
```

To restart services:

```bash
sudo systemctl restart mcads
sudo systemctl reload nginx
``` 