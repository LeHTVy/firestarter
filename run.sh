#!/bin/bash
# Run script for AI Pentest Agent

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${GREEN}✅ Running as root - privileged tools (nmap -sS, nikto) will work${NC}"
    SUDO_MODE=true
else
    echo -e "${YELLOW}⚠️  Not running as root - some tools may require sudo${NC}"
    echo "   For full functionality (nmap SYN scan, etc.), run: sudo ./run.sh"
    SUDO_MODE=false
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Load .env file if exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    echo -e "${GREEN}✅ Loaded environment variables from .env${NC}"
fi

# Activate virtual environment (works with sudo if using same user's venv)
source venv/bin/activate

# If running as root, ensure we use the venv's python
if [ "$SUDO_MODE" = true ]; then
    # Use absolute path to venv python
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
else
    PYTHON_CMD="python"
fi

# Check if Ollama is running
echo "🔍 Checking Ollama connection..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Warning: Ollama is not running or not accessible${NC}"
    echo "   Please start Ollama first: ollama serve"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✅ Ollama connection successful${NC}"
fi

# Check if Redis is running (optional)
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
echo "🔍 Checking Redis connection..."
if command -v redis-cli &> /dev/null; then
    if redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} ping &> /dev/null; then
        echo -e "${GREEN}✅ Redis connection successful${NC}"
    else
        echo -e "${YELLOW}⚠️  Redis not accessible. Continuing without Redis...${NC}"
    fi
else
    echo "ℹ️  redis-cli not found. Skipping Redis check."
fi

# Show mode info
echo ""
if [ "$SUDO_MODE" = true ]; then
    echo "🔓 Mode: PRIVILEGED (root) - All tools available"
else
    echo "🔒 Mode: USER - Limited tools (nmap TCP connect, etc.)"
fi
echo ""

# Run the application
echo "🚀 Starting AI Pentest Agent..."
$PYTHON_CMD main.py
