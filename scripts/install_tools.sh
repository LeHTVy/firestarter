#!/bin/bash
# Install script for Firestarter tools
# This is a wrapper around install_tools.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

# Run the Python install script
python3 "$SCRIPT_DIR/install_tools.py" "$@"
