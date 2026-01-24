#!/bin/bash
# ============================================================
# Firestarter Security Tools Installer
# ============================================================
# Usage:
#   ./install_tools.sh              # Install all tools
#   ./install_tools.sh --python     # Python tools only
#   ./install_tools.sh --go         # Go tools only
#   ./install_tools.sh --system     # System tools only (apt)
#   ./install_tools.sh --check      # Check what's installed
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================
# Python packages (pip install)
# ============================================================
PYTHON_PACKAGES=(
    "shodan"
    "dnspython"
    "python-whois"
    "requests"
    "httpx"
    "beautifulsoup4"
    "pyyaml"
    "sqlmap"
    "theharvester"
    "bbot"
)

# ============================================================
# Go tools (go install)
# ============================================================
declare -A GO_TOOLS=(
    ["subfinder"]="github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
    ["amass"]="github.com/owasp-amass/amass/v4/...@master"
    ["nuclei"]="github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
    ["httpx-go"]="github.com/projectdiscovery/httpx/cmd/httpx@latest"
    ["katana"]="github.com/projectdiscovery/katana/cmd/katana@latest"
    ["gobuster"]="github.com/OJ/gobuster/v3@latest"
    ["ffuf"]="github.com/ffuf/ffuf/v2@latest"
)

# ============================================================
# System tools (apt install)
# ============================================================
SYSTEM_PACKAGES=(
    "nmap"
    "masscan"
    "nikto"
    "whois"
    "dnsutils"
    "curl"
    "wget"
    "git"
)

# ============================================================
# Helper functions
# ============================================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# ============================================================
# Setup Python venv
# ============================================================
setup_venv() {
    VENV_DIR="$PROJECT_ROOT/.venv"
    
    if [ ! -d "$VENV_DIR" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
        log_success "Virtual environment created at $VENV_DIR"
    fi
    
    # Activate venv
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --upgrade pip -q
}

# ============================================================
# Install Python packages
# ============================================================
install_python() {
    log_info "Installing Python packages..."
    
    setup_venv
    
    for pkg in "${PYTHON_PACKAGES[@]}"; do
        echo -n "  📦 $pkg... "
        if pip install "$pkg" -q 2>/dev/null; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗${NC}"
        fi
    done
    
    log_success "Python packages installed"
}

# ============================================================
# Install Go tools
# ============================================================
install_go() {
    if ! check_command go; then
        log_error "Go is not installed. Please install Go first:"
        echo "  https://go.dev/dl/"
        return 1
    fi
    
    log_info "Installing Go tools..."
    
    for tool in "${!GO_TOOLS[@]}"; do
        echo -n "  📦 $tool... "
        if go install -v "${GO_TOOLS[$tool]}" 2>/dev/null; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗${NC}"
        fi
    done
    
    log_success "Go tools installed"
}

# ============================================================
# Install system packages (apt)
# ============================================================
install_system() {
    if ! check_command apt; then
        log_warning "apt not found - skipping system packages"
        return 0
    fi
    
    log_info "Installing system packages..."
    
    sudo apt update -qq
    
    for pkg in "${SYSTEM_PACKAGES[@]}"; do
        echo -n "  📦 $pkg... "
        if sudo apt install -y "$pkg" -qq 2>/dev/null; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗${NC}"
        fi
    done
    
    log_success "System packages installed"
}

# ============================================================
# Check installed tools
# ============================================================
check_installed() {
    echo ""
    log_info "Checking installed tools..."
    echo ""
    
    local installed=0
    local missing=0
    
    # Check Python packages
    echo "📦 Python packages:"
    setup_venv
    for pkg in "${PYTHON_PACKAGES[@]}"; do
        if pip show "$pkg" &>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $pkg"
            ((installed++))
        else
            echo -e "  ${RED}✗${NC} $pkg"
            ((missing++))
        fi
    done
    
    echo ""
    echo "🔧 CLI tools:"
    
    # Check Go/System tools
    local cli_tools=("subfinder" "amass" "nuclei" "httpx" "katana" "gobuster" "ffuf" "nmap" "masscan" "nikto" "whois" "dig")
    
    for tool in "${cli_tools[@]}"; do
        if check_command "$tool"; then
            echo -e "  ${GREEN}✓${NC} $tool"
            ((installed++))
        else
            echo -e "  ${RED}✗${NC} $tool"
            ((missing++))
        fi
    done
    
    echo ""
    log_info "Installed: $installed | Missing: $missing"
}

# ============================================================
# Main
# ============================================================
main() {
    echo ""
    echo "🚀 Firestarter Security Tools Installer"
    echo "========================================"
    echo ""
    
    case "${1:-all}" in
        --python)
            install_python
            ;;
        --go)
            install_go
            ;;
        --system)
            install_system
            ;;
        --check)
            check_installed
            ;;
        --help|-h)
            echo "Usage: $0 [--python|--go|--system|--check|--help]"
            echo ""
            echo "Options:"
            echo "  --python   Install Python packages only"
            echo "  --go       Install Go tools only"
            echo "  --system   Install system packages only (apt)"
            echo "  --check    Check installed tools"
            echo "  --help     Show this help"
            ;;
        all|*)
            install_system
            install_python
            install_go
            ;;
    esac
    
    echo ""
    log_success "Done! Run '$0 --check' to verify installation."
}

main "$@"
