#!/usr/bin/env python3
"""Install security tools using uv (fast Python package manager).

UV is 10-100x faster than pip. Install uv first:
  Windows: irm https://astral.sh/uv/install.ps1 | iex
  Linux/Mac: curl -LsSf https://astral.sh/uv/install.sh | sh

Usage:
  python install_tools_uv.py              # Install all tools
  python install_tools_uv.py --python     # Python tools only
  python install_tools_uv.py --go         # Go tools only
  python install_tools_uv.py --check      # Check what's installed
"""

import subprocess
import shutil
import sys
import argparse
from typing import Dict, List


# Python tools (install via uv pip)
PYTHON_TOOLS: Dict[str, str] = {
    "shodan": "shodan",
    "dnspython": "dnspython",
    "python-whois": "python-whois",
    "requests": "requests",
    "httpx": "httpx",
    "beautifulsoup4": "beautifulsoup4",
    "pyyaml": "pyyaml",
    "sqlmap": "sqlmap",
    "theHarvester": "theharvester",
}

# Go tools (install via go install)
GO_TOOLS: Dict[str, str] = {
    "subfinder": "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
    "amass": "github.com/owasp-amass/amass/v4/...@master",
    "nuclei": "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
    "httpx-go": "github.com/projectdiscovery/httpx/cmd/httpx@latest",
    "katana": "github.com/projectdiscovery/katana/cmd/katana@latest",
    "gobuster": "github.com/OJ/gobuster/v3@latest",
    "ffuf": "github.com/ffuf/ffuf/v2@latest",
}

# System tools (apt/brew)
SYSTEM_TOOLS: Dict[str, str] = {
    "nmap": "nmap",
    "masscan": "masscan",
    "nikto": "nikto",
    "whois": "whois",
    "dig": "dnsutils",  # dig is in dnsutils package
}


def check_uv_installed() -> bool:
    """Check if uv is installed."""
    return shutil.which("uv") is not None


def check_go_installed() -> bool:
    """Check if Go is installed."""
    return shutil.which("go") is not None


def install_uv():
    """Install uv package manager."""
    print("📦 Installing uv...")
    if sys.platform == "win32":
        subprocess.run(["powershell", "-c", "irm https://astral.sh/uv/install.ps1 | iex"], check=True)
    else:
        subprocess.run(["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"], check=True)
    print("✅ uv installed")


def install_python_tools(tools: Dict[str, str] = None):
    """Install Python tools using uv."""
    tools = tools or PYTHON_TOOLS
    
    if not check_uv_installed():
        print("⚠️ uv not found. Installing uv first...")
        install_uv()
    
    print(f"\n🐍 Installing {len(tools)} Python tools with uv...")
    
    for name, package in tools.items():
        print(f"  📦 {name}...", end=" ", flush=True)
        try:
            result = subprocess.run(
                ["uv", "pip", "install", package],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                print("✅")
            else:
                print(f"❌ {result.stderr[:50]}")
        except subprocess.TimeoutExpired:
            print("⏰ timeout")
        except Exception as e:
            print(f"❌ {e}")


def install_go_tools(tools: Dict[str, str] = None):
    """Install Go tools using go install."""
    tools = tools or GO_TOOLS
    
    if not check_go_installed():
        print("❌ Go is not installed. Please install Go first:")
        print("   https://go.dev/dl/")
        return
    
    print(f"\n🔧 Installing {len(tools)} Go tools...")
    
    for name, package in tools.items():
        print(f"  📦 {name}...", end=" ", flush=True)
        try:
            result = subprocess.run(
                ["go", "install", "-v", package],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                print("✅")
            else:
                print(f"❌")
        except subprocess.TimeoutExpired:
            print("⏰ timeout")
        except Exception as e:
            print(f"❌ {e}")


def check_installed():
    """Check which tools are installed."""
    print("\n🔍 Checking installed tools...\n")
    
    all_tools = list(PYTHON_TOOLS.keys()) + list(GO_TOOLS.keys()) + list(SYSTEM_TOOLS.keys())
    installed = []
    missing = []
    
    for tool in sorted(set(all_tools)):
        if shutil.which(tool):
            installed.append(tool)
            print(f"  ✅ {tool}")
        else:
            missing.append(tool)
            print(f"  ❌ {tool}")
    
    print(f"\n📊 Installed: {len(installed)}/{len(all_tools)}")
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")


def main():
    parser = argparse.ArgumentParser(description="Install security tools with uv/go")
    parser.add_argument("--python", action="store_true", help="Install Python tools only")
    parser.add_argument("--go", action="store_true", help="Install Go tools only")
    parser.add_argument("--check", action="store_true", help="Check installed tools")
    args = parser.parse_args()
    
    print("🚀 Firestarter Tool Installer (uv edition)")
    print("=" * 50)
    
    if args.check:
        check_installed()
        return
    
    if args.python or (not args.go):
        install_python_tools()
    
    if args.go or (not args.python):
        install_go_tools()
    
    print("\n✅ Installation complete!")
    print("\nRun 'python install_tools_uv.py --check' to verify")


if __name__ == "__main__":
    main()
