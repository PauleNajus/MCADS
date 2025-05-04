# Deployment Guide for ldcs on Ubuntu 22.04

This guide will help you deploy the ldcs Django project on Ubuntu 22.04 using Gunicorn (with ASGI), Nginx, and systemd.

## Prerequisites

- Ubuntu 22.04 LTS server
- Domain name pointing to your server (optional, but recommended for production)
- SSH access to your server

## 1. Server Preparation

Update your system packages:

```bash
sudo apt update
sudo apt upgrade -y
```

Install required packages:

```bash
sudo apt install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx
```

## 2. Project Setup

### Clone the Repository

```bash
git clone https://your-repository-url.git /path/to/ldcs
cd /path/to/ldcs
```

### Create Virtual Environment and Install Dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn==21.2.0 uvicorn==0.27.1
```

### Create Production Environment File

Create a `.env.production` file in the project root:

```bash
DEBUG=False
SECRET_KEY=your_secure_random_key_here
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

You can generate a secure random key with:

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Collect Static Files and Run Migrations

```bash
source .venv/bin/activate
export $(cat .env.production | xargs)
python manage.py collectstatic --no-input
python manage.py migrate
```

## 3. Gunicorn Configuration

Create a Gunicorn configuration file (`gunicorn_config.py`):

```python
import multiprocessing

# Gunicorn configuration file for Django ASGI application
bind = "unix:/run/gunicorn.sock"  # Use unix socket
workers = multiprocessing.cpu_count() * 2 + 1  # Recommended formula
worker_class = "uvicorn.workers.UvicornWorker"  # Use Uvicorn worker for ASGI
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 5
errorlog = "/var/log/gunicorn/error.log"
accesslog = "/var/log/gunicorn/access.log"
loglevel = "info"
proc_name = "ldcs_asgi"
```

Create the log directory:

```bash
sudo mkdir -p /var/log/gunicorn
sudo chown -R www-data:www-data /var/log/gunicorn
```

## 4. Systemd Service Setup

Create a systemd service file (`/etc/systemd/system/ldcs.service`):

```ini
[Unit]
Description=ldcs Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/ldcs
ExecStart=/var/www/ldcs/.venv/bin/gunicorn -c gunicorn_config.py ldcs_project.asgi:application
Restart=on-failure
Environment="PATH=/var/www/ldcs/.venv/bin:/usr/bin"
EnvironmentFile=/var/www/ldcs/.env.production

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ldcs
sudo systemctl start ldcs
```

## 5. Nginx Configuration

Create an Nginx configuration file (`/etc/nginx/sites-available/ldcs.conf`):

```nginx
server {
    listen 80;
    server_name ldcs18.com www.ldcs18.com;
    
    # Static files
    location /static/ {
        alias /var/www/ldcs/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
    
    # Media files
    location /media/ {
        alias /var/www/ldcs/media/;
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
    }
    
    # Logging
    access_log /var/log/nginx/ldcs_access.log;
    error_log /var/log/nginx/ldcs_error.log;
}
```

Enable the configuration:

```bash
sudo ln -s /etc/nginx/sites-available/ldcs.conf /etc/nginx/sites-enabled/
sudo nginx -t  # Test the configuration
sudo systemctl reload nginx
```

## 6. Set Up SSL with Let's Encrypt

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

This will automatically update your Nginx configuration to use HTTPS.

## 7. Set Proper Permissions

```bash
sudo chown -R www-data:www-data /path/to/ldcs/media
sudo chown -R www-data:www-data /path/to/ldcs/staticfiles
sudo chmod -R 755 /path/to/ldcs/media
sudo chmod -R 755 /path/to/ldcs/staticfiles
```

## 8. Monitor the Application

Check the status of your application:

```bash
sudo systemctl status ldcs
```

View logs:

```bash
sudo journalctl -u ldcs
sudo tail -f /var/log/nginx/ldcs_error.log
```

## 9. Common Issues and Troubleshooting

1. **Socket permission issues**: Make sure the socket directory has the right permissions.
   ```bash
   sudo mkdir -p /run/gunicorn
   sudo chown www-data:www-data /run/gunicorn
   ```

2. **Static files not found**: Verify paths in Nginx configuration and run `collectstatic` again.

3. **502 Bad Gateway**: Check Gunicorn is running and logs for errors:
   ```bash
   sudo systemctl status ldcs
   sudo tail -f /var/log/gunicorn/error.log
   ```

4. **ASGI application errors**: Verify ASGI configuration in the project's `asgi.py`.

## 10. Maintenance

To update the application:

```bash
cd /path/to/ldcs
git pull
source .venv/bin/activate
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
sudo systemctl restart ldcs
```

To restart services:

```bash
sudo systemctl restart ldcs
sudo systemctl reload nginx
``` 