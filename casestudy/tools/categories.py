"""
Tool Category Registry
=======================

Maps user intent keywords to tool categories based on spec file organization.

Usage:
    from app.tools.categories import get_tools_for_intent
    
    tools = get_tools_for_intent("brute force")  # Returns hydra, john, hashcat, etc.
    tools = get_tools_for_intent("port scan")    # Returns port_scan, nmap_deep, etc.
"""
from typing import List, Dict, Set, Optional


# Category definitions - maps spec file name to keywords and tools
# IMPORTANT: Order matters! More specific action keywords should come first
TOOL_CATEGORIES = {
    # ACTION-based categories first (what they want to DO)
    "scanning": {
        "keywords": ["port scan", "scan port", "open port", "nmap", "masscan", "service detection"],
        "tools": ["port_scan", "nmap_deep", "quick_scan", "masscan"],
        "description": "Port scanning and service detection",
    },
    "brute": {
        "keywords": ["brute force", "brute-force", "crack", "password", "login attack", "credential"],
        "tools": ["hydra", "john", "hashcat", "crackmapexec", "medusa"],
        "description": "Password cracking and brute-force attacks",
    },
    "vuln": {
        "keywords": ["vuln", "vulnerability", "nuclei", "nikto", "cve", "security scan"],
        "tools": ["vuln_scan", "vuln_scan_batch", "nikto_batch", "search_cves"],
        "description": "Vulnerability scanning",
    },
    "exploit": {
        "keywords": ["exploit", "payload", "metasploit", "msf", "shell", "reverse shell"],
        "tools": ["searchsploit", "msfvenom", "msfconsole"],
        "description": "Exploitation and payload generation",
    },
    "web": {
        "keywords": ["web", "http probe", "directory", "fuzz", "gobuster", "ffuf", "httpx"],
        "tools": ["httpx_probe", "httpx_batch", "dir_bruteforce", "web_fuzz", "tech_analyze"],
        "description": "Web application testing",
    },
    # SUBJECT-based categories (what they're targeting)
    "recon": {
        "keywords": ["recon", "subdomain", "enumerate domain", "domain enum", "find subdomain"],
        "tools": ["subdomain_enum", "whois", "dns_lookup"],
        "description": "Reconnaissance and subdomain enumeration",
    },
    "osint": {
        "keywords": ["osint", "intelligence", "harvest", "shodan", "dns recon", "fierce"],
        "tools": ["shodan", "dnsrecon", "fierce", "theharvester"],
        "description": "Open source intelligence gathering",
    },
    "network": {
        "keywords": ["network", "smb", "netbios", "enum4linux", "samba", "windows", "tcpdump"],
        "tools": ["netcat", "enum4linux", "nbtscan", "smbclient", "tcpdump"],
        "description": "Network enumeration and SMB testing",
    },
    "cloud": {
        "keywords": ["cloud", "secret", "api key", "git", "container", "docker", "trivy"],
        "tools": ["trufflehog", "gitleaks", "trivy", "docker_scan"],
        "description": "Cloud and container security",
    },
}


def get_category_for_intent(user_input: str) -> Optional[str]:
    """
    Detect which tool category matches the user's intent.
    
    Args:
        user_input: The user's query
        
    Returns:
        Category name (e.g., "brute", "scanning") or None
    """
    text_lower = user_input.lower()
    
    for category, config in TOOL_CATEGORIES.items():
        for keyword in config["keywords"]:
            if keyword in text_lower:
                return category
    
    return None


def get_tools_for_category(category: str) -> List[str]:
    """Get all tools in a category."""
    if category in TOOL_CATEGORIES:
        return TOOL_CATEGORIES[category]["tools"]
    return []


def get_tools_for_intent(user_input: str) -> List[str]:
    """
    Get appropriate tools based on user intent.
    
    Args:
        user_input: The user's query
        
    Returns:
        List of tool names appropriate for this intent
    """
    category = get_category_for_intent(user_input)
    if category:
        return get_tools_for_category(category)
    return []


def get_suggested_tool(user_input: str) -> Optional[str]:
    """
    Get the best suggested tool for a user's intent.
    
    Returns the first (primary) tool from the matching category.
    """
    tools = get_tools_for_intent(user_input)
    return tools[0] if tools else None


def get_all_categories() -> Dict[str, dict]:
    """Get all category definitions."""
    return TOOL_CATEGORIES.copy()


def describe_categories() -> str:
    """Get human-readable description of all categories."""
    lines = ["## Tool Categories\n"]
    for name, config in TOOL_CATEGORIES.items():
        lines.append(f"### {name.upper()}")
        lines.append(f"*{config['description']}*")
        lines.append(f"**Keywords**: {', '.join(config['keywords'][:3])}")
        lines.append(f"**Tools**: {', '.join(config['tools'])}")
        lines.append("")
    return "\n".join(lines)
