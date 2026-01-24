"""
Tool Specifications Package
===========================

Defines specifications for all security tools.
"""
from typing import List
from app.tools.registry import ToolSpec


def get_all_specs() -> List[ToolSpec]:
    """Get all tool specifications."""
    specs = []
    
    # Import all spec modules
    from app.tools.specs import (
        scanning,   # httpx, nmap, masscan
        recon,      # subfinder, amass, whois, dig, theHarvester
        vuln,       # nuclei, nikto, sqlmap, gobuster, ffuf
        exploit,    # msfconsole, msfvenom, searchsploit
        brute,      # hydra, medusa, john, hashcat, crackmapexec
        web,        # wfuzz, feroxbuster, wpscan, whatweb, wafw00f, arjun, dirsearch
        network,    # netcat, responder, tcpdump, enum4linux, nbtscan, smbclient
        osint,      # shodan, dnsrecon, fierce, spiderfoot, recon-ng, emailharvester
        cloud,      # trufflehog, gitleaks, trivy, prowler, scout, docker, kubectl
    )
    
    specs.extend(scanning.get_specs())
    specs.extend(recon.get_specs())
    specs.extend(vuln.get_specs())
    specs.extend(exploit.get_specs())
    specs.extend(brute.get_specs())
    specs.extend(web.get_specs())
    specs.extend(network.get_specs())
    specs.extend(osint.get_specs())
    specs.extend(cloud.get_specs())
    
    return specs
