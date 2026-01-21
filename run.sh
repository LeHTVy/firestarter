#!/bin/bash
# Run script for AI Pentest Agent

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Load .env file if exists
if [ -f ".env" ]; then
    # Load .env file properly (handle comments and empty lines)
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    echo "✅ Loaded environment variables from .env"
fi

# Activate virtual environment
source venv/bin/activate

# Check if Ollama is running
echo "🔍 Checking Ollama connection..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Warning: Ollama is not running or not accessible at http://localhost:11434"
    echo "   Please start Ollama first:"
    echo "   - Install: https://ollama.com"
    echo "   - Run: ollama serve"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Redis is running (optional, but recommended)
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
echo "🔍 Checking Redis connection..."
if command -v redis-cli &> /dev/null; then
    if ! redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} ping &> /dev/null; then
        echo "⚠️  Warning: Redis is not running or not accessible at ${REDIS_HOST}:${REDIS_PORT}"
        echo "   Redis is used for short-term memory buffer (optional but recommended)"
        echo "   Install: sudo apt install redis-server"
        echo "   See docs/REDIS_SETUP.md for setup instructions"
        echo ""
        read -p "Continue without Redis? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo "✅ Redis connection successful"
    fi
else
    echo "ℹ️  redis-cli not found. Skipping Redis check."
    echo "   Install: sudo apt install redis-server"
fi

# Run the application
echo "🚀 Starting AI Pentest Agent..."
python main.py
