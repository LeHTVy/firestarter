#!/usr/bin/env python3
"""Install script for Firestarter tools.

This script parses tools.json and installs all required tools.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

# Tool name to package mapping
TOOL_PACKAGE_MAP = {
    # System packages (apt)
    "nmap_scan": "nmap",
    "metasploit_exploit": "metasploit-framework",
    "dns_enum": "dnsutils",
    "whois_lookup": "whois",
    "ssl_cert_scan": "openssl",
    "port_scan": "nmap",
    "service_detection": "nmap",
    "os_detection": "nmap",
    "banner_grabbing": "nmap",
    "subdomain_discovery": "dnsutils",
    "directory_bruteforce": "gobuster",
    "sql_injection_test": "sqlmap",
    "xss_test": "xsser",
    "command_injection_test": "commix",
    "file_upload_test": "upload-scanner",
    "csrf_test": "xsrfprobe",
    "ssrf_test": "ssrfmap",
    "xxe_test": "xxeinjector",
    "ldap_injection_test": "ldapsearch",
    "path_traversal_test": "dotdotpwn",
    "deserialization_test": "ysoserial",
    "api_fuzzing": "ffuf",
    "password_crack": "hashcat",
    "brute_force_login": "hydra",
    "session_hijack": "burpsuite",
    "privilege_escalation_check": "linpeas",
    "reverse_shell": "netcat",
    "payload_generator": "msfvenom",
    "log_analyzer": "logwatch",
    "ioc_checker": "yara",
    "threat_intel_lookup": "misp",
    "malware_analysis": "cuckoo",
    "network_traffic_analysis": "wireshark",
    "vulnerability_scanner": "openvas",
    "cve_lookup": "cve-search",
    "exploit_search": "searchsploit",
    "email_harvesting": "theharvester",
    "social_media_recon": "sherlock",
    "github_recon": "gitrob",
    "certificate_transparency": "ctfr",
    "ip_geolocation": "geoiplookup",
    "reverse_ip_lookup": "dnsrecon",
    "breach_check": "h8mail",
    "password_leak_check": "haveibeenpwned",
    "web_archive_search": "waybackpy",
    "robots_txt_check": "robots-txt-checker",
    "sitemap_analysis": "sitemap-parser",
    "technology_detection": "wappalyzer",
    "waf_detection": "wafw00f",
    "cms_detection": "cmseek",
    "api_endpoint_discovery": "arjun",
    "graphql_introspection": "graphqlmap",
    "jwt_analysis": "jwt-tool",
    "oauth_test": "oauth2test",
    "open_redirect_test": "open-redirect-scanner",
    "idor_test": "idor-scanner",
    "rate_limit_test": "rate-limit-test",
    "clickjacking_test": "clickjacking-tester",
    "host_header_injection": "host-header-injection",
    "http_parameter_pollution": "hpp",
    "template_injection_test": "tplmap",
    "race_condition_test": "race-condition-tester",
    "business_logic_test": "business-logic-scanner",
    "file_inclusion_test": "lfi-scanner",
    "code_injection_test": "code-injection-scanner",
    "nosql_injection_test": "nosqlmap",
    "xpath_injection_test": "xpath-scanner",
    "xxe_blind_test": "xxe-scanner",
    "websocket_test": "websocket-scanner",
    "dns_rebinding": "dns-rebinding-scanner",
    "subdomain_takeover": "subjack",
    "cache_poisoning_test": "cache-poisoning-scanner",
    "http_smuggling_test": "http-smuggling-scanner",
    "pipeline_test": "http-pipeline-scanner",
    "desync_attack": "http-desync-scanner",
    "time_based_blind_sqli": "sqlmap",
    "boolean_blind_sqli": "sqlmap",
    "union_based_sqli": "sqlmap",
    "error_based_sqli": "sqlmap",
    "stored_xss": "xsser",
    "reflected_xss": "xsser",
    "dom_xss": "xsser",
    "mutation_xss": "xsser",
    "prototype_pollution": "prototype-pollution-scanner",
    "dom_clobbering": "dom-clobbering-scanner",
    "postmessage_vuln": "postmessage-scanner",
    "webhook_test": "webhook-scanner",
    "api_key_extraction": "api-key-scanner",
    "secret_scanning": "trufflehog",
    "credential_stuffing": "hydra",
}

# Python packages (pip)
PYTHON_PACKAGES = {
    "shodan_search": "shodan",
    "virustotal_scan": "virustotal-api",
    "web_search": "google-search-results",
    "http_header_analysis": "requests",
    "dns_enum": "dnspython",
    "subdomain_discovery": "subfinder",
    "whois_lookup": "python-whois",
    "ssl_cert_scan": "sslscan",
    "email_harvesting": "theHarvester",
    "social_media_recon": "sherlock-project",
    "github_recon": "gitrob",
    "certificate_transparency": "ctfr",
    "ip_geolocation": "geoip2",
    "reverse_ip_lookup": "dnspython",
    "breach_check": "h8mail",
    "password_leak_check": "haveibeenpwned",
    "web_archive_search": "waybackpy",
    "robots_txt_check": "robotparser",
    "sitemap_analysis": "sitemap-parser",
    "technology_detection": "python-Wappalyzer",
    "waf_detection": "wafw00f",
    "cms_detection": "CMSeeK",
    "api_endpoint_discovery": "arjun",
    "graphql_introspection": "graphqlmap",
    "jwt_analysis": "pyjwt",
    "oauth_test": "requests-oauthlib",
    "open_redirect_test": "requests",
    "idor_test": "requests",
    "rate_limit_test": "requests",
    "clickjacking_test": "requests",
    "host_header_injection": "requests",
    "http_parameter_pollution": "requests",
    "template_injection_test": "tplmap",
    "race_condition_test": "requests",
    "business_logic_test": "requests",
    "file_inclusion_test": "requests",
    "code_injection_test": "requests",
    "nosql_injection_test": "pymongo",
    "xpath_injection_test": "lxml",
    "xxe_blind_test": "lxml",
    "websocket_test": "websocket-client",
    "dns_rebinding": "dnspython",
    "subdomain_takeover": "subjack",
    "cache_poisoning_test": "requests",
    "http_smuggling_test": "requests",
    "pipeline_test": "requests",
    "desync_attack": "requests",
    "time_based_blind_sqli": "sqlmap",
    "boolean_blind_sqli": "sqlmap",
    "union_based_sqli": "sqlmap",
    "error_based_sqli": "sqlmap",
    "stored_xss": "requests",
    "reflected_xss": "requests",
    "dom_xss": "requests",
    "mutation_xss": "requests",
    "prototype_pollution": "requests",
    "dom_clobbering": "requests",
    "postmessage_vuln": "requests",
    "webhook_test": "requests",
    "api_key_extraction": "requests",
    "secret_scanning": "truffleHog",
    "credential_stuffing": "hydra",
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


def install_system_packages(packages: Set[str], dry_run: bool = False):
    """Install system packages using apt."""
    if not packages:
        return
    
    print(f"\n📦 Installing {len(packages)} system package(s)...")
    for package in sorted(packages):
        print(f"  - {package}")
    
    if dry_run:
        print("\n[DRY RUN] Would run: sudo apt-get update && sudo apt-get install -y " + " ".join(sorted(packages)))
        return
    
    try:
        # Update package list
        subprocess.run(["sudo", "apt-get", "update"], check=True)
        # Install packages
        subprocess.run(["sudo", "apt-get", "install", "-y"] + sorted(packages), check=True)
        print("✅ System packages installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install system packages: {e}")
        sys.exit(1)


def install_python_packages(packages: Set[str], dry_run: bool = False):
    """Install Python packages using pip."""
    if not packages:
        return
    
    print(f"\n🐍 Installing {len(packages)} Python package(s)...")
    for package in sorted(packages):
        print(f"  - {package}")
    
    if dry_run:
        print("\n[DRY RUN] Would run: pip install " + " ".join(sorted(packages)))
        return
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install"] + sorted(packages), check=True)
        print("✅ Python packages installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python packages: {e}")
        sys.exit(1)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Install Firestarter tools")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be installed without actually installing")
    parser.add_argument("--system-only", action="store_true", help="Only install system packages")
    parser.add_argument("--python-only", action="store_true", help="Only install Python packages")
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
        install_system_packages(system_packages, dry_run=args.dry_run)
    
    if not args.system_only:
        install_python_packages(python_packages, dry_run=args.dry_run)
    
    print("\n✅ Installation complete!")


if __name__ == "__main__":
    main()
