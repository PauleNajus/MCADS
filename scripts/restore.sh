#!/bin/bash
# MCADS Docker Restore Script
set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_name>"
    echo "Available backups:"
    ls -1 ./backups/mcads_backup_*.tar.gz 2>/dev/null | sed 's/.*mcads_backup_\(.*\)\.tar\.gz/\1/' || echo "No backups found"
    exit 1
fi

BACKUP_NAME="$1"
BACKUP_DIR="./backups"
BACKUP_FILE="${BACKUP_DIR}/mcads_backup_${BACKUP_NAME}.tar.gz"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Starting MCADS restore from backup: $BACKUP_NAME"

# Stop services
echo "Stopping Docker services..."
docker-compose down

# Extract backup
echo "Extracting backup..."
cd "$BACKUP_DIR"
tar -xzf "mcads_backup_${BACKUP_NAME}.tar.gz"
cd ..

# Restore database
echo "Restoring PostgreSQL database..."
docker-compose up -d db
sleep 10  # Wait for database to be ready

# Drop and recreate database
docker-compose exec -T db psql -U mcads_user -d postgres -c "DROP DATABASE IF EXISTS mcads_db;"
docker-compose exec -T db psql -U mcads_user -d postgres -c "CREATE DATABASE mcads_db;"

# Restore database data
docker-compose exec -T db psql -U mcads_user -d mcads_db < "${BACKUP_DIR}/mcads_backup_${BACKUP_NAME}/database.sql"

# Restore media files
echo "Restoring media files..."
rm -rf ./media
tar -xzf "${BACKUP_DIR}/mcads_backup_${BACKUP_NAME}/media.tar.gz"

# Restore static files
echo "Restoring static files..."
rm -rf ./staticfiles
tar -xzf "${BACKUP_DIR}/mcads_backup_${BACKUP_NAME}/staticfiles.tar.gz"

# Restore logs
echo "Restoring logs..."
rm -rf ./logs
tar -xzf "${BACKUP_DIR}/mcads_backup_${BACKUP_NAME}/logs.tar.gz"

# Clean up extracted backup directory
rm -rf "${BACKUP_DIR}/mcads_backup_${BACKUP_NAME}/"

# Start all services
echo "Starting Docker services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 30

# Verify restore
echo "Verifying restore..."
if curl -f http://localhost:8000/health/ > /dev/null 2>&1; then
    echo "✓ Application is responding"
else
    echo "⚠ Application health check failed"
fi

echo "Restore completed successfully!"
echo "Access your application at: http://localhost"