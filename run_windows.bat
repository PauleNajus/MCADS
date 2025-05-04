@echo off
echo =====================================================
echo   Setting up Chest X-Ray Analysis Application (ldcs)
echo =====================================================

REM Check if Python is installed
python --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH. Please install Python 3 first.
    exit /b 1
)

REM Check if virtual environment exists, create if not
if not exist .venv\ (
    echo Creating virtual environment...
    python -m venv .venv
    echo Virtual environment created successfully!
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate

REM Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file...
    echo # Django settings > .env
    echo DEBUG=True >> .env
    REM Generate a random secret key
    for /f "delims=" %%i in ('python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"') do set SECRET_KEY=%%i
    echo SECRET_KEY=%SECRET_KEY% >> .env
    echo ALLOWED_HOSTS=localhost,127.0.0.1 >> .env
    echo .env file created with a secure random secret key!
) else (
    echo .env file already exists.
)

REM Run migrations
echo Running database migrations...
python manage.py migrate

REM Collect static files
echo Collecting static files...
python manage.py collectstatic --noinput

REM Create media directories if they don't exist
if not exist media\uploads\ (
    echo Creating media directories...
    mkdir media\uploads
)

REM Success message
echo =====================================================
echo Setup completed successfully!
echo =====================================================
echo.
echo Starting Django development server...
echo You can access the application at http://127.0.0.1:8000/
echo.
echo Press Ctrl+C to stop the server when you're done.
echo =====================================================

REM Start Django development server
python manage.py runserver 