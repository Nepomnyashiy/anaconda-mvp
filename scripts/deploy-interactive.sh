#!/bin/bash
# Quick deployment script - interactive mode

set -e

echo "🚀 Anaconda MVP Quick Deploy"
echo "============================"
echo ""

# Ask for server details
read -p "Enter server IP or hostname: " SERVER_HOST
read -p "Enter SSH user (default: nsadmin): " SSH_USER
SSH_USER=${SSH_USER:-nsadmin}

read -p "Enter SSH port (default: 22): " SSH_PORT
SSH_PORT=${SSH_PORT:-22}

read -p "Do you have an SSH key? (y/n): " USE_KEY
if [ "$USE_KEY" = "y" ] || [ "$USE_KEY" = "Y" ]; then
    read -p "Enter path to SSH key (e.g., ~/.ssh/id_rsa): " SSH_KEY
    SSH_KEY=$(eval echo "$SSH_KEY")
else
    SSH_KEY=""
fi

echo ""
echo "Configuration:"
echo "  Server: $SERVER_HOST"
echo "  User: $SSH_USER"
echo "  Port: $SSH_PORT"
[ -n "$SSH_KEY" ] && echo "  Key: $SSH_KEY" || echo "  Auth: Password"

read -p "Continue? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Cancelled"
    exit 0
fi

echo ""
echo "Deploying..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run deployment
if [ -n "$SSH_KEY" ]; then
    bash "$SCRIPT_DIR/remote-deploy.sh" "$SERVER_HOST" "$SSH_USER" "$SSH_PORT" "$SSH_KEY"
else
    bash "$SCRIPT_DIR/remote-deploy.sh" "$SERVER_HOST" "$SSH_USER" "$SSH_PORT"
fi
