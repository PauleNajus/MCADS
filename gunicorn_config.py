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