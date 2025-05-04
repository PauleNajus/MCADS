#!/bin/bash
set -e

# Configuration Variables
APP_DIR="/var/www/ldcs"
DOMAIN="ldcs18.com"
APP_USER="www-data"
APP_GROUP="www-data"
VENV_DIR="$APP_DIR/.venv"
LOG_DIR="/var/log/gunicorn"
NGINX_AVAILABLE="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"
SYSTEMD_DIR="/etc/systemd/system"

# Print header
echo "=== ldcs Production Deployment on Ubuntu 22.04 ==="
echo "This script will set up your Django application with Gunicorn and Nginx."

# 1. Update system packages
echo -e "\n=== Updating system packages ==="
apt update
apt upgrade -y

# 2. Install required packages
echo -e "\n=== Installing required packages ==="
apt install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx

# 3. Activate or create virtual environment
echo -e "\n=== Setting up Python virtual environment ==="
if [ ! -d "$VENV_DIR" ]; then
    python3.11 -m venv "$VENV_DIR"
fi

# 4. Activate virtual environment and install dependencies
echo -e "\n=== Installing Python dependencies ==="
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$APP_DIR/requirements.production.txt"

# 5. Set up environment file
echo -e "\n=== Setting up environment file ==="
if [ ! -f "$APP_DIR/.env.production" ]; then
    echo "Creating .env.production file..."
    SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
    cat > "$APP_DIR/.env.production" << EOF
DEBUG=False
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=ldcs18.com,www.ldcs18.com,162.0.223.203
DATABASE_URL=sqlite:///$APP_DIR/db.sqlite3
EOF
    echo "Created .env.production with a secure random key."
else
    echo ".env.production already exists. Skipping creation."
fi

# 6. Collect static files
echo -e "\n=== Collecting static files ==="
cd "$APP_DIR"
source "$VENV_DIR/bin/activate"
export $(cat "$APP_DIR/.env.production" | xargs)
python manage.py collectstatic --no-input

# 7. Run migrations
echo -e "\n=== Running database migrations ==="
python manage.py migrate

# 8. Create Gunicorn log directory
echo -e "\n=== Setting up Gunicorn logs ==="
mkdir -p "$LOG_DIR"
chown -R "$APP_USER:$APP_GROUP" "$LOG_DIR"

# 9. Update Gunicorn config
echo -e "\n=== Setting up Gunicorn configuration ==="
cat > "$APP_DIR/gunicorn_config.py" << EOF
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
EOF

# 10. Set up systemd service
echo -e "\n=== Setting up systemd service ==="
cat > "$APP_DIR/ldcs.service" << EOF
[Unit]
Description=ldcs Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/gunicorn -c gunicorn_config.py ldcs_project.asgi:application
Restart=on-failure
Environment="PATH=$APP_DIR/.venv/bin:/usr/bin"
EnvironmentFile=$APP_DIR/.env.production

[Install]
WantedBy=multi-user.target
EOF

cp "$APP_DIR/ldcs.service" "$SYSTEMD_DIR/"
systemctl daemon-reload
systemctl enable ldcs

# 11. Configure Nginx
echo -e "\n=== Setting up Nginx ==="
cat > "$NGINX_AVAILABLE/ldcs.conf" << EOF
server {
    listen 80;
    server_name ldcs18.com www.ldcs18.com;
    
    # Static files
    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
    
    # Media files
    location /media/ {
        alias $APP_DIR/media/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
    
    # Proxy requests to Gunicorn
    location / {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
        client_max_body_size 20M;
    }
    
    # Logging
    access_log /var/log/nginx/ldcs_access.log;
    error_log /var/log/nginx/ldcs_error.log;
}
EOF

ln -sf "$NGINX_AVAILABLE/ldcs.conf" "$NGINX_ENABLED/"
nginx -t  # Test Nginx configuration
systemctl reload nginx

# 12. Set proper permissions
echo -e "\n=== Setting proper file permissions ==="
mkdir -p "$APP_DIR/media"
mkdir -p "$APP_DIR/staticfiles"
chown -R "$APP_USER:$APP_GROUP" "$APP_DIR/media"
chown -R "$APP_USER:$APP_GROUP" "$APP_DIR/staticfiles"
chmod -R 755 "$APP_DIR/media"
chmod -R 755 "$APP_DIR/staticfiles"

# 13. Set up SSL with Let's Encrypt
echo -e "\n=== Setting up SSL with Let's Encrypt ==="
echo "Setting up HTTPS with Let's Encrypt..."
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --email admin@$DOMAIN

# 14. Create socket directory
echo -e "\n=== Creating socket directory ==="
mkdir -p /run/gunicorn
chown "$APP_USER:$APP_GROUP" /run/gunicorn

# 15. Start the application
echo -e "\n=== Starting the application ==="
systemctl start ldcs

echo -e "\n=== Deployment completed successfully! ==="
echo "Your application should now be running at https://$DOMAIN"
echo "Check the status with: systemctl status ldcs"
echo "View logs with: journalctl -u ldcs" 