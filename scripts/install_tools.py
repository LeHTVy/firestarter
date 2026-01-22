#!/usr/bin/env python3
"""Install script for Firestarter tools.

This script parses tools.json and installs all required tools.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

# Tool name to package mapping - ONLY packages that exist in apt repositories
# Many security tools are not in apt, they need to be installed via pip, git, or snap
TOOL_PACKAGE_MAP = {
    # System packages (apt) - verified to exist
    "nmap_scan": "nmap",
    "port_scan": "nmap",
    "service_detection": "nmap",
    "os_detection": "nmap",
    "banner_grabbing": "nmap",
    "metasploit_exploit": "metasploit-framework",
    "dns_enum": "dnsutils",
    "whois_lookup": "whois",
    "ssl_cert_scan": "openssl",
    "subdomain_discovery": "dnsutils",
    "password_crack": "hashcat",
    "brute_force_login": "hydra",
    "credential_stuffing": "hydra",
    "network_traffic_analysis": "wireshark",
    "log_analyzer": "logwatch",
    "ioc_checker": "yara",
    "vulnerability_scanner": "gvm",  # OpenVAS/GVM
    "reverse_shell": "netcat-traditional",  # Explicitly select netcat variant
}

# Python packages (pip) - ONLY packages that exist on PyPI
# Many security tools are not on PyPI, they need to be installed via git or manual setup
PYTHON_PACKAGES = {
    "shodan_search": "shodan",
    "virustotal_scan": "virustotal-api",
    "web_search": "google-search-results",
    "http_header_analysis": "requests",
    "dns_enum": "dnspython",
    "whois_lookup": "python-whois",
    "ip_geolocation": "geoip2",
    "reverse_ip_lookup": "dnspython",
    "web_archive_search": "waybackpy",
    "technology_detection": "python-Wappalyzer",
    "waf_detection": "wafw00f",
    "jwt_analysis": "pyjwt",
    "oauth_test": "requests-oauthlib",
    "template_injection_test": "tplmap",
    "nosql_injection_test": "pymongo",
    "xpath_injection_test": "lxml",
    "xxe_blind_test": "lxml",
    "websocket_test": "websocket-client",
    "dns_rebinding": "dnspython",
    "secret_scanning": "truffleHog",
    "email_harvesting": "theHarvester",
    "social_media_recon": "sherlock-project",
    "certificate_transparency": "ctfr",
    "breach_check": "h8mail",
    "password_leak_check": "haveibeenpwned",
    "sql_injection_test": "sqlmap",
    "time_based_blind_sqli": "sqlmap",
    "boolean_blind_sqli": "sqlmap",
    "union_based_sqli": "sqlmap",
    "error_based_sqli": "sqlmap",
}

# Packages that don't exist on PyPI (need git install or manual setup)
# These are commented out to avoid installation errors
PYTHON_PACKAGES_NOT_ON_PYPI = {
    "cms_detection": "CMSeeK",  # Not on PyPI - needs git install
    "api_endpoint_discovery": "arjun",  # Not on PyPI - needs git install
    "graphql_introspection": "graphqlmap",  # Not on PyPI - needs git install
    "subdomain_takeover": "subjack",  # Not on PyPI - needs git install
    "github_recon": "gitrob",  # Not on PyPI - needs git install
}

# Git-based tools (need to clone and install manually)
# These are tools that are typically installed from GitHub
GIT_TOOLS = {
    "directory_bruteforce": "https://github.com/OJ/gobuster.git",
    "command_injection_test": "https://github.com/commixproject/commix.git",
    "path_traversal_test": "https://github.com/wireghoul/dotdotpwn.git",
    "deserialization_test": "https://github.com/frohoff/ysoserial.git",
    "api_fuzzing": "https://github.com/ffuf/ffuf.git",
    "privilege_escalation_check": "https://github.com/carlospolop/PEASS-ng.git",
    "exploit_search": "https://github.com/offensive-security/exploitdb.git",
    "reverse_ip_lookup": "https://github.com/darkoperator/dnsrecon.git",
    "subdomain_discovery": "https://github.com/projectdiscovery/subfinder.git",
    "xss_test": "https://github.com/epsylon/xsser.git",
    "csrf_test": "https://github.com/0xInfection/XSRFProbe.git",
    "ssrf_test": "https://github.com/swisskyrepo/SSRFmap.git",
    "xxe_test": "https://github.com/enjoiz/XXEinjector.git",
    "ldap_injection_test": "ldapsearch",  # Usually comes with ldap-utils
    "file_upload_test": "upload-scanner",  # Generic - may need custom implementation
    "open_redirect_test": "open-redirect-scanner",  # Generic - may need custom implementation
    "idor_test": "idor-scanner",  # Generic - may need custom implementation
    "rate_limit_test": "rate-limit-test",  # Generic - may need custom implementation
    "clickjacking_test": "clickjacking-tester",  # Generic - may need custom implementation
    "host_header_injection": "host-header-injection",  # Generic - may need custom implementation
    "http_parameter_pollution": "hpp",  # Generic - may need custom implementation
    "race_condition_test": "race-condition-tester",  # Generic - may need custom implementation
    "business_logic_test": "business-logic-scanner",  # Generic - may need custom implementation
    "file_inclusion_test": "lfi-scanner",  # Generic - may need custom implementation
    "code_injection_test": "code-injection-scanner",  # Generic - may need custom implementation
    "xpath_injection_test": "xpath-scanner",  # Generic - may need custom implementation
    "xxe_blind_test": "xxe-scanner",  # Generic - may need custom implementation
    "websocket_test": "websocket-scanner",  # Generic - may need custom implementation
    "dns_rebinding": "dns-rebinding-scanner",  # Generic - may need custom implementation
    "cache_poisoning_test": "cache-poisoning-scanner",  # Generic - may need custom implementation
    "http_smuggling_test": "http-smuggling-scanner",  # Generic - may need custom implementation
    "pipeline_test": "http-pipeline-scanner",  # Generic - may need custom implementation
    "desync_attack": "http-desync-scanner",  # Generic - may need custom implementation
    "stored_xss": "xsser",
    "reflected_xss": "xsser",
    "dom_xss": "xsser",
    "mutation_xss": "xsser",
    "prototype_pollution": "prototype-pollution-scanner",  # Generic - may need custom implementation
    "dom_clobbering": "dom-clobbering-scanner",  # Generic - may need custom implementation
    "postmessage_vuln": "postmessage-scanner",  # Generic - may need custom implementation
    "webhook_test": "webhook-scanner",  # Generic - may need custom implementation
    "api_key_extraction": "api-key-scanner",  # Generic - may need custom implementation
    "session_hijack": "burpsuite",  # Commercial tool - needs manual install
    "payload_generator": "msfvenom",  # Part of metasploit-framework
    "threat_intel_lookup": "misp",  # Needs manual setup
    "malware_analysis": "cuckoo",  # Needs manual setup
    "cve_lookup": "cve-search",  # Needs manual setup
    "robots_txt_check": "robots-txt-checker",  # Generic - may need custom implementation
    "sitemap_analysis": "sitemap-parser",  # Generic - may need custom implementation
    "wappalyzer": "wappalyzer",  # Usually npm package
    "waybackpy": "waybackpy",  # Already in PYTHON_PACKAGES
}

# Tools that don't need installation (built-in or API-based)
NO_INSTALL_NEEDED = {
    "web_search",  # Uses SerpAPI
    "shodan_search",  # Uses Shodan API (needs API key)
    "virustotal_scan",  # Uses VirusTotal API (needs API key)
    "dns_enum",  # Uses built-in DNS libraries
    "whois_lookup",  # Uses built-in whois
    "ssl_cert_scan",  # Uses built-in OpenSSL
    "http_header_analysis",  # Uses requests library
    "subdomain_discovery",  # Uses DNS libraries
    "ip_geolocation",  # Uses API services
    "reverse_ip_lookup",  # Uses DNS libraries
    "breach_check",  # Uses API services
    "password_leak_check",  # Uses API services
    "web_archive_search",  # Uses API services
    "robots_txt_check",  # Uses requests
    "sitemap_analysis",  # Uses requests
    "technology_detection",  # Uses libraries
    "waf_detection",  # Uses libraries
    "cms_detection",  # Uses libraries
    "api_endpoint_discovery",  # Uses requests
    "graphql_introspection",  # Uses requests
    "jwt_analysis",  # Uses libraries
    "oauth_test",  # Uses requests
    "open_redirect_test",  # Uses requests
    "idor_test",  # Uses requests
    "rate_limit_test",  # Uses requests
    "clickjacking_test",  # Uses requests
    "host_header_injection",  # Uses requests
    "http_parameter_pollution",  # Uses requests
    "template_injection_test",  # Uses libraries
    "race_condition_test",  # Uses requests
    "business_logic_test",  # Uses requests
    "file_inclusion_test",  # Uses requests
    "code_injection_test",  # Uses requests
    "nosql_injection_test",  # Uses libraries
    "xpath_injection_test",  # Uses libraries
    "xxe_blind_test",  # Uses libraries
    "websocket_test",  # Uses libraries
    "dns_rebinding",  # Uses DNS libraries
    "subdomain_takeover",  # Uses libraries
    "cache_poisoning_test",  # Uses requests
    "http_smuggling_test",  # Uses requests
    "pipeline_test",  # Uses requests
    "desync_attack",  # Uses requests
    "stored_xss",  # Uses requests
    "reflected_xss",  # Uses requests
    "dom_xss",  # Uses requests
    "mutation_xss",  # Uses requests
    "prototype_pollution",  # Uses requests
    "dom_clobbering",  # Uses requests
    "postmessage_vuln",  # Uses requests
    "webhook_test",  # Uses requests
    "api_key_extraction",  # Uses requests
    "secret_scanning",  # Uses libraries
    "credential_stuffing",  # Uses libraries
}


def load_tools() -> List[Dict]:
    """Load tools from tools.json."""
    tools_file = Path(__file__).parent.parent / "tools" / "metadata" / "tools.json"
    with open(tools_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("tools", [])


def get_system_packages(tools: List[Dict]) -> Set[str]:
    """Extract system packages needed."""
    packages = set()
    for tool in tools:
        tool_name = tool.get("name")
        if tool_name in TOOL_PACKAGE_MAP:
            package = TOOL_PACKAGE_MAP[tool_name]
            if package:
                packages.add(package)
    return packages


def get_python_packages(tools: List[Dict]) -> Set[str]:
    """Extract Python packages needed."""
    packages = set()
    for tool in tools:
        tool_name = tool.get("name")
        if tool_name in PYTHON_PACKAGES:
            package = PYTHON_PACKAGES[tool_name]
            if package:
                packages.add(package)
    return packages


def check_package_exists(package: str) -> bool:
    """Check if a package exists in apt repositories."""
    try:
        result = subprocess.run(
            ["apt-cache", "search", "--names-only", f"^{package}$"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return len(result.stdout.strip()) > 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_system_packages(packages: Set[str], dry_run: bool = False, skip_missing: bool = True):
    """Install system packages using apt.
    
    Args:
        packages: Set of package names
        dry_run: If True, only show what would be installed
        skip_missing: If True, skip packages that don't exist in apt
    """
    if not packages:
        return
    
    print(f"\n📦 Checking {len(packages)} system package(s)...")
    
    # Filter packages that exist in apt
    existing_packages = []
    missing_packages = []
    
    for package in sorted(packages):
        if check_package_exists(package):
            existing_packages.append(package)
            print(f"  ✅ {package} (available)")
        else:
            missing_packages.append(package)
            if skip_missing:
                print(f"  ⚠️  {package} (not found in apt - skipping)")
            else:
                print(f"  ❌ {package} (not found in apt)")
    
    if missing_packages and not skip_missing:
        print(f"\n❌ {len(missing_packages)} package(s) not found in apt repositories")
        print("💡 Tip: Use --skip-missing to install only available packages")
        sys.exit(1)
    
    if not existing_packages:
        print("⚠️  No packages available in apt repositories")
        return
    
    print(f"\n📦 Installing {len(existing_packages)} available package(s)...")
    for package in existing_packages:
        print(f"  - {package}")
    
    if dry_run:
        print("\n[DRY RUN] Would run: sudo apt-get update && sudo apt-get install -y " + " ".join(existing_packages))
        return
    
    try:
        # Update package list
        print("\n🔄 Updating package list...")
        subprocess.run(["sudo", "apt-get", "update"], check=True)
        # Install packages
        print(f"📥 Installing packages...")
        subprocess.run(["sudo", "apt-get", "install", "-y"] + existing_packages, check=True)
        print(f"✅ Successfully installed {len(existing_packages)} package(s)")
        if missing_packages:
            print(f"⚠️  Skipped {len(missing_packages)} package(s) not found in apt (may need manual install)")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install system packages: {e}")
        if missing_packages:
            print(f"💡 Note: {len(missing_packages)} package(s) were skipped (not in apt)")
        sys.exit(1)


def check_pypi_package_exists(package: str) -> bool:
    """Check if a package exists on PyPI by trying to get its metadata."""
    try:
        # Try using pip show (fastest, works if package is installed)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True
        
        # Try using pip install --dry-run (simulates install without actually installing)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run", package],
            capture_output=True,
            text=True,
            timeout=10
        )
        # If dry-run succeeds, package exists
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # If check fails, assume package exists and let pip handle the error
        # This is safer than blocking valid packages
        return True


def install_python_packages(packages: Set[str], dry_run: bool = False, skip_missing: bool = True):
    """Install Python packages using pip.
    
    Args:
        packages: Set of package names
        dry_run: If True, only show what would be installed
        skip_missing: If True, skip packages that don't exist on PyPI
    """
    if not packages:
        return
    
    print(f"\n🐍 Checking {len(packages)} Python package(s)...")
    
    # Filter packages that exist on PyPI
    existing_packages = []
    missing_packages = []
    
    for package in sorted(packages):
        if check_pypi_package_exists(package):
            existing_packages.append(package)
            print(f"  ✅ {package} (available on PyPI)")
        else:
            missing_packages.append(package)
            if skip_missing:
                print(f"  ⚠️  {package} (not found on PyPI - skipping)")
            else:
                print(f"  ❌ {package} (not found on PyPI)")
    
    if missing_packages and not skip_missing:
        print(f"\n❌ {len(missing_packages)} package(s) not found on PyPI")
        print("💡 Tip: Use --skip-missing to install only available packages")
        sys.exit(1)
    
    if not existing_packages:
        print("⚠️  No packages available on PyPI")
        return
    
    print(f"\n🐍 Installing {len(existing_packages)} available package(s)...")
    for package in existing_packages:
        print(f"  - {package}")
    
    if dry_run:
        print("\n[DRY RUN] Would run: pip install " + " ".join(existing_packages))
        return
    
    try:
        print(f"📥 Installing packages...")
        subprocess.run([sys.executable, "-m", "pip", "install"] + existing_packages, check=True)
        print(f"✅ Successfully installed {len(existing_packages)} package(s)")
        if missing_packages:
            print(f"⚠️  Skipped {len(missing_packages)} package(s) not found on PyPI (may need git install)")
            print("💡 Tip: Some tools may need to be installed from GitHub:")
            for pkg in missing_packages[:5]:  # Show first 5
                print(f"     - {pkg}: May need 'pip install git+https://github.com/...'")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python packages: {e}")
        if missing_packages:
            print(f"💡 Note: {len(missing_packages)} package(s) were skipped (not on PyPI)")
        sys.exit(1)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Install Firestarter tools")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be installed without actually installing")
    parser.add_argument("--system-only", action="store_true", help="Only install system packages")
    parser.add_argument("--python-only", action="store_true", help="Only install Python packages")
    parser.add_argument("--skip-missing", action="store_true", default=True, help="Skip packages not found in repositories (default: True)")
    parser.add_argument("--no-skip-missing", dest="skip_missing", action="store_false", help="Fail if packages are not found")
    args = parser.parse_args()
    
    print("🔍 Loading tools from metadata...")
    tools = load_tools()
    print(f"✅ Loaded {len(tools)} tools")
    
    # Get packages
    system_packages = get_system_packages(tools)
    python_packages = get_python_packages(tools)
    
    print(f"\n📊 Summary:")
    print(f"  - System packages: {len(system_packages)}")
    print(f"  - Python packages: {len(python_packages)}")
    
    # Install packages
    if not args.python_only:
        install_system_packages(system_packages, dry_run=args.dry_run, skip_missing=args.skip_missing)
    
    if not args.system_only:
        install_python_packages(python_packages, dry_run=args.dry_run, skip_missing=args.skip_missing)
    
    print("\n✅ Installation complete!")


if __name__ == "__main__":
    main()
