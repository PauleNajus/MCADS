#!/bin/bash
# Remote deployment script for LDCS
# Run this from your local machine to deploy to the remote server

# Configuration
REMOTE_HOST="ldcs18.com"
REMOTE_USER="root"
REMOTE_IP="162.0.223.203"
REMOTE_PATH="/var/www/ldcs"
LOCAL_PATH="."  # Current directory

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== LDCS Remote Deployment ===${NC}"
echo -e "This script will deploy the LDCS application to ${YELLOW}$REMOTE_HOST${NC} ($REMOTE_IP)"
echo ""

# 1. Check if we can connect to the server
echo -e "${YELLOW}Testing connection to server...${NC}"
ssh -o BatchMode=yes -o ConnectTimeout=5 $REMOTE_USER@$REMOTE_IP echo "Connection successful" > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Cannot connect to server. Please check your SSH configuration.${NC}"
    echo "Make sure you can connect with: ssh $REMOTE_USER@$REMOTE_IP"
    exit 1
fi
echo -e "${GREEN}Connection successful!${NC}"

# 2. Create the remote directory if it doesn't exist
echo -e "${YELLOW}Creating remote directory structure...${NC}"
ssh $REMOTE_USER@$REMOTE_IP "mkdir -p $REMOTE_PATH"
echo -e "${GREEN}Done!${NC}"

# 3. Upload the application files
echo -e "${YELLOW}Uploading application files...${NC}"
rsync -avz --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='.DS_Store' --exclude='node_modules' \
    $LOCAL_PATH/ $REMOTE_USER@$REMOTE_IP:$REMOTE_PATH/
echo -e "${GREEN}Files uploaded successfully!${NC}"

# 4. Make scripts executable
echo -e "${YELLOW}Making scripts executable...${NC}"
ssh $REMOTE_USER@$REMOTE_IP "chmod +x $REMOTE_PATH/deploy_to_production.sh $REMOTE_PATH/check_deployment.py"
echo -e "${GREEN}Done!${NC}"

# 5. Run the pre-deployment check
echo -e "${YELLOW}Running pre-deployment check...${NC}"
ssh $REMOTE_USER@$REMOTE_IP "cd $REMOTE_PATH && pip install -r requirements.check.txt && python check_deployment.py"

if [ $? -ne 0 ]; then
    echo -e "${RED}Pre-deployment check failed. Please fix the issues before continuing.${NC}"
    echo -e "${YELLOW}Do you want to continue with deployment anyway? (y/n)${NC}"
    read -r continue_anyway
    if [[ ! "$continue_anyway" =~ ^[Yy]$ ]]; then
        echo "Deployment aborted."
        exit 1
    fi
fi

# 6. Run the deployment script
echo -e "${YELLOW}Running deployment script on the server...${NC}"
ssh $REMOTE_USER@$REMOTE_IP "cd $REMOTE_PATH && bash deploy_to_production.sh"

if [ $? -ne 0 ]; then
    echo -e "${RED}Deployment script encountered errors. Please check the server logs.${NC}"
    exit 1
fi

# 7. Final check
echo -e "${YELLOW}Verifying deployment...${NC}"
ssh $REMOTE_USER@$REMOTE_IP "systemctl status ldcs"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo -e "Your application should now be running at ${YELLOW}https://$REMOTE_HOST${NC}"
echo -e "To check the status: ${YELLOW}ssh $REMOTE_USER@$REMOTE_IP 'systemctl status ldcs'${NC}"
echo -e "To view logs: ${YELLOW}ssh $REMOTE_USER@$REMOTE_IP 'journalctl -u ldcs'${NC}" 