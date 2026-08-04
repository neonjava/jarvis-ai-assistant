#!/usr/bin/env bash
# JARVIS Quick Setup Script for Fedora Linux
set -euo pipefail

BLUE='\033[0;34m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${CYAN}[JARVIS]${NC} $*"; }
success() { echo -e "${GREEN}✅${NC} $*"; }
warn() { echo -e "${YELLOW}⚠️${NC} $*"; }
err() { echo -e "${RED}❌${NC} $*"; exit 1; }

echo -e "\n${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       JARVIS Setup — Fedora Linux    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}\n"

# Check Python
log "Checking Python version..."
python3 --version | grep -E "3\.(1[3-9]|[2-9][0-9])" || err "Python 3.13+ required"
success "Python OK"

# Install system packages
log "Installing system dependencies..."
sudo dnf install -y \
    portaudio-devel \
    ffmpeg \
    espeak-ng \
    xdotool \
    xclip \
    scrot \
    brightnessctl \
    libnotify \
    alsa-utils \
    pulseaudio-utils \
    pipewire-pulseaudio \
    2>/dev/null || warn "Some packages may have failed (non-critical)"

success "System packages installed"

# Create virtual environment
log "Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
success "Virtual environment created"

# Install Python packages
log "Installing Python dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"
success "Python packages installed"

# Setup .env
if [ ! -f ".env" ]; then
    log "Creating .env configuration..."
    cp .env.example .env
    # Generate a secure secret key
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/CHANGE_ME_USE_SECRETS_TOKEN_HEX_32/$SECRET/" .env
    success ".env created with secure key"
else
    warn ".env already exists, skipping"
fi

# Initialize database
log "Initializing database..."
mkdir -p data logs
python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from database.engine import init_db
asyncio.run(init_db())
print('Database initialized')
" && success "Database initialized"

# Check Ollama
log "Checking Ollama..."
if command -v ollama &>/dev/null; then
    success "Ollama found"
    
    # Check if model is available
    MODEL=$(grep OLLAMA_MODEL .env | cut -d= -f2)
    MODEL=${MODEL:-llama3.2}
    
    if ! ollama list | grep -q "$MODEL"; then
        log "Pulling Ollama model: $MODEL (this may take a while)..."
        ollama pull "$MODEL" && success "Model $MODEL downloaded"
    else
        success "Model $MODEL already available"
    fi
else
    warn "Ollama not found. Install from: https://ollama.com"
    warn "Then run: ollama pull llama3.2"
fi

# Create desktop shortcut
log "Creating desktop shortcut..."
JARVIS_DIR=$(pwd)
cat > ~/.local/share/applications/jarvis.desktop << EOF
[Desktop Entry]
Name=JARVIS
Comment=AI Desktop Assistant
Exec=bash -c "cd $JARVIS_DIR && source .venv/bin/activate && python main.py desktop"
Icon=$JARVIS_DIR/ui/assets/jarvis-icon.png
Terminal=false
Type=Application
Categories=Utility;AI;
StartupWMClass=JARVIS
EOF
success "Desktop shortcut created"

# Run tests
log "Running basic tests..."
python3 -m pytest tests/ -v --tb=short -x -q 2>&1 | tail -20 && success "Tests passed" || warn "Some tests failed (may need services)"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        JARVIS Setup Complete! 🚀             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Start API server:    python main.py serve"
echo "  Launch desktop UI:   python main.py desktop"
echo "  Voice mode only:     python main.py voice"
echo "  Quick chat:          python main.py chat 'open Firefox'"
echo "  Check status:        python main.py status"
echo ""
echo "  API docs:            http://localhost:8765/docs"
echo "  WebSocket:           ws://localhost:8765/ws/my-client"
echo ""
