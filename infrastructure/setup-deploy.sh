#!/bin/bash
# Setup script for Anaconda MVP deployment server

set -e

echo "🔧 Anaconda MVP Server Setup"
echo "=============================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}❌ Please do not run as root${NC}"
   exit 1
fi

# 1. Install Docker & Docker Compose
echo -e "${YELLOW}📦 Installing Docker & Docker Compose...${NC}"
if ! command -v docker &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose git curl
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✅ Docker installed${NC}"
else
    echo -e "${GREEN}✓ Docker already installed${NC}"
fi

# 2. Clone repository
PROJECT_DIR="/home/$USER/kip-service/anaconda_mvp"
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}📥 Cloning repository...${NC}"
    mkdir -p /home/$USER/kip-service
    cd /home/$USER/kip-service
    git clone https://github.com/Nepomnyashiy/anaconda-mvp.git
    echo -e "${GREEN}✅ Repository cloned${NC}"
else
    echo -e "${GREEN}✓ Repository already exists${NC}"
fi

cd "$PROJECT_DIR"

# 3. Setup environment
echo -e "${YELLOW}⚙️ Setting up environment...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    echo -e "${YELLOW}⚠️ Created .env from .env.example${NC}"
    echo -e "${YELLOW}📝 Please edit .env with your settings:${NC}"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - EMAIL_IMAP_USER & PASSWORD"
    echo "   - DATABASE_URL"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# 4. Setup SSH key for GitHub Actions
echo -e "${YELLOW}🔑 Setting up SSH key for GitHub Actions...${NC}"
SSH_KEY_PATH="$HOME/.ssh/anaconda_deploy"
if [ ! -f "$SSH_KEY_PATH" ]; then
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -N ""
    cat "$SSH_KEY_PATH.pub" >> "$HOME/.ssh/authorized_keys"
    chmod 600 "$HOME/.ssh/authorized_keys"
    
    echo -e "${GREEN}✅ SSH key created${NC}"
    echo ""
    echo -e "${YELLOW}📋 Private key created at $SSH_KEY_PATH.${NC}"
    echo -e "${YELLOW}Load it into GitHub Secrets locally without printing it to terminal.${NC}"
else
    echo -e "${GREEN}✓ SSH key already exists${NC}"
fi

# 5. Build and start containers
echo -e "${YELLOW}🔨 Building Docker images...${NC}"
docker-compose build

echo -e "${YELLOW}🟢 Starting containers...${NC}"
docker-compose up -d

# 6. Wait for API to be ready
echo -e "${YELLOW}⏳ Waiting for API to be ready...${NC}"
for i in {1..30}; do
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ API is ready${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# 7. Check status
echo ""
echo -e "${YELLOW}📊 Container Status:${NC}"
docker-compose ps

# 8. Display info
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📍 Services:"
echo "  - API: http://localhost:8000"
echo "  - Web: http://localhost:5173"
echo "  - Health: http://localhost:8000/health"
echo ""
echo "📝 Next steps:"
echo "  1. Check .env configuration"
echo "  2. Add SSH key to GitHub Secrets"
echo "  3. Monitor with: docker-compose logs -f"
echo ""
echo "🚀 For GitHub Actions deployment:"
echo "  - DEPLOY_HOST: $(hostname -I | awk '{print $1}')"
echo "  - DEPLOY_USER: $USER"
echo "  - DEPLOY_SSH_KEY: Copy from above"
echo ""
