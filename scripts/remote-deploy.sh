#!/bin/bash
# Deploy to remote server via SSH

set -e

# Configuration
REMOTE_HOST="${1:-}"
REMOTE_USER="${2:-nsadmin}"
REMOTE_PORT="${3:-22}"
SSH_KEY="${4:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ 🚀 Anaconda MVP Remote Deployment ${NC}${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
}

print_step() {
    echo -e "\n${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

show_usage() {
    cat << EOF
Usage: $0 <host> [user] [port] [ssh_key]

Examples:
  # Using default settings (port 22, user nsadmin)
  $0 192.168.1.100

  # With custom user
  $0 192.168.1.100 ubuntu 22

  # With SSH key
  $0 192.168.1.100 nsadmin 22 ~/.ssh/id_rsa

Arguments:
  host      - Remote server IP or hostname (REQUIRED)
  user      - SSH user (default: nsadmin)
  port      - SSH port (default: 22)
  ssh_key   - Path to SSH private key (optional)
EOF
    exit 1
}

# Main script
main() {
    print_header
    
    if [ -z "$REMOTE_HOST" ]; then
        print_error "Remote host is required"
        show_usage
    fi
    
    echo -e "\n${BLUE}Configuration:${NC}"
    echo "  Host: $REMOTE_HOST"
    echo "  User: $REMOTE_USER"
    echo "  Port: $REMOTE_PORT"
    [ -n "$SSH_KEY" ] && echo "  Key: $SSH_KEY" || echo "  Auth: Password"
    
    # Build SSH command
    SSH_CMD="ssh -p $REMOTE_PORT"
    SCP_CMD="scp -P $REMOTE_PORT"
    
    if [ -n "$SSH_KEY" ]; then
        SSH_CMD="$SSH_CMD -i $SSH_KEY"
        SCP_CMD="$SCP_CMD -i $SSH_KEY"
    fi
    
    SSH_TARGET="$REMOTE_USER@$REMOTE_HOST"
    
    # Test connection
    print_step "Testing SSH connection..."
    if $SSH_CMD $SSH_TARGET "echo 'SSH connection successful'" > /dev/null 2>&1; then
        print_success "SSH connection established"
    else
        print_error "Failed to connect to $SSH_TARGET"
        echo "Please check:"
        echo "  - Host: $REMOTE_HOST"
        echo "  - User: $REMOTE_USER"
        echo "  - Port: $REMOTE_PORT"
        echo "  - SSH key: $SSH_KEY"
        exit 1
    fi
    
    # Copy files
    print_step "Copying project files..."
    
    # Create remote directory
    $SSH_CMD $SSH_TARGET "mkdir -p /home/$REMOTE_USER/kip-service/anaconda_mvp"
    
    # Copy entire project
    $SCP_CMD -r . $SSH_TARGET:/home/$REMOTE_USER/kip-service/anaconda_mvp/
    print_success "Files copied"
    
    # Run setup on remote
    print_step "Running setup on remote server..."
    
    $SSH_CMD $SSH_TARGET << 'REMOTE_SCRIPT'
        set -e
        
        cd /home/nsadmin/kip-service/anaconda_mvp
        
        echo "📋 System information:"
        uname -a
        
        echo ""
        echo "🐳 Checking Docker..."
        docker --version || echo "Docker not installed"
        
        echo ""
        echo "🔧 Installing dependencies..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq git curl docker.io docker-compose 2>/dev/null || true
        
        echo ""
        echo "👤 Adding user to docker group..."
        sudo usermod -aG docker nsadmin || true
        
        echo ""
        echo "📦 Building Docker images..."
        docker-compose build --no-cache 2>&1 | tail -5
        
        echo ""
        echo "🟢 Starting containers..."
        docker-compose up -d
        
        echo ""
        echo "⏳ Waiting for API..."
        for i in {1..30}; do
            if curl -f http://localhost:8000/health >/dev/null 2>&1; then
                echo "✅ API is ready"
                break
            fi
            echo -n "."
            sleep 2
        done
        
        echo ""
        echo "📊 Container status:"
        docker-compose ps
        
        echo ""
        echo "=========================================="
        echo "✅ DEPLOYMENT SUCCESSFUL"
        echo "=========================================="
        echo "API: http://localhost:8000"
        echo "Web: http://localhost:5173"
        echo "Health: http://localhost:8000/health"
        echo ""
        echo "View logs: docker-compose logs -f"
        echo "=========================================="
REMOTE_SCRIPT
    
    print_success "Remote deployment completed!"
    
    # Display access information
    echo ""
    echo -e "${BLUE}Access Information:${NC}"
    echo "  SSH: ssh -p $REMOTE_PORT $SSH_TARGET"
    echo "  Project: /home/$REMOTE_USER/kip-service/anaconda_mvp"
    echo "  API: http://$REMOTE_HOST:8000"
    echo "  Web: http://$REMOTE_HOST:5173"
    
    echo ""
    echo -e "${GREEN}🎉 Next steps:${NC}"
    echo "  1. Check API health: curl http://$REMOTE_HOST:8000/health"
    echo "  2. View logs: ssh $SSH_TARGET 'cd /home/$REMOTE_USER/kip-service/anaconda_mvp && docker-compose logs -f'"
    echo "  3. Configure GitHub Secrets for CI/CD (see QUICKSTART-DEPLOY.md)"
    
}

# Run main function
main
