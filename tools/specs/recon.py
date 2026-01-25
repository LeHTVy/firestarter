"""Reconnaissance Tools Specifications.

Subdomain enumeration, OSINT, DNS lookup.
"""
from typing import List
from tools.specs import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get reconnaissance tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # SUBFINDER - Subdomain Enumeration
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="subfinder",
            category=ToolCategory.RECON,
            description="Fast subdomain discovery tool",
            executable_names=["subfinder"],
            install_hint="go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
            aliases=["finder", "subdomain_discovery", "subdomain_enum", "subdomains"],
            commands={
                "enum": CommandTemplate(
                    args=["-d", "{domain}", "-silent"],
                    timeout=120,
                    description="Basic subdomain enumeration"
                ),
                "enum_all": CommandTemplate(
                    args=["-d", "{domain}", "-all", "-silent"],
                    timeout=300,
                    description="All sources enumeration"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # AMASS - Advanced Subdomain Enumeration
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="amass",
            category=ToolCategory.RECON,
            description="In-depth subdomain enumeration",
            executable_names=["amass"],
            install_hint="go install github.com/owasp-amass/amass/v4/...@master",
            aliases=["mass", "subdomain_bruteforce"],
            commands={
                "passive": CommandTemplate(
                    args=["enum", "-passive", "-d", "{domain}"],
                    timeout=1200,  # Increased timeout
                    description="Passive subdomain enumeration"
                ),
                "active": CommandTemplate(
                    args=["enum", "-d", "{domain}"],
                    timeout=1800,
                    description="Active subdomain enumeration"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # WHOIS - Domain Registration Lookup
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="whois",
            category=ToolCategory.RECON,
            description="Domain/IP registration lookup",
            executable_names=["whois"],
            install_hint="apt install whois",
            aliases=["whois_lookup", "domain_whois", "domain_info"],
            commands={
                "lookup": CommandTemplate(
                    args=["{target}"],
                    timeout=30,
                    success_codes=[0, 1],
                    description="WHOIS lookup"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # DIG - DNS Lookup
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="dig",
            category=ToolCategory.RECON,
            description="DNS query tool",
            executable_names=["dig"],
            install_hint="apt install dnsutils",
            aliases=["dns_enum", "dns_lookup", "dns_query", "dns_recon"],
            commands={
                "any": CommandTemplate(args=["+short", "ANY", "{domain}"], timeout=30),
                "mx": CommandTemplate(args=["+short", "MX", "{domain}"], timeout=30),
                "ns": CommandTemplate(args=["+short", "NS", "{domain}"], timeout=30),
                "txt": CommandTemplate(args=["+short", "TXT", "{domain}"], timeout=30),
                "a": CommandTemplate(args=["+short", "A", "{domain}"], timeout=30),
            }
        ),
        
        
        # ─────────────────────────────────────────────────────────
        # HTTPX - HTTP Probing
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="httpx",
            category=ToolCategory.RECON,
            description="Fast HTTP toolkit",
            executable_names=["httpx"],
            install_hint="go install github.com/projectdiscovery/httpx/cmd/httpx@latest",
            commands={
                "probe": CommandTemplate(
                    args=["-u", "{url}", "-status-code", "-title"], 
                    timeout=120,
                    description="HTTP probe with status and title"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # KATANA - Web Crawler
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="katana",
            category=ToolCategory.RECON,
            description="Fast web crawler for endpoint discovery",
            executable_names=["katana"],
            install_hint="go install github.com/projectdiscovery/katana/cmd/katana@latest",
            commands={
                "crawl": CommandTemplate(
                    args=["-u", "{url}", "-d", "3"],
                    timeout=300,
                    description="Deep crawl"
                ),
                "js": CommandTemplate(
                    args=["-u", "{url}", "-jc", "-d", "2"],
                    timeout=300,
                    description="JavaScript discovery"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # THEHARVESTER - OSINT Email/Subdomain Harvesting
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="theHarvester",
            category=ToolCategory.RECON,
            description="OSINT tool for email and subdomain harvesting",
            executable_names=["theHarvester", "theharvester", "python3 -m theHarvester"], 
            install_hint="pip install theHarvester",
            aliases=["harvester", "email_harvester", "theharvester", "email_harvesting"],
            commands={
                "enum": CommandTemplate(
                    args=["-d", "{domain}", "-b", "all"],
                    timeout=300,
                    description="Harvest emails and subdomains from all sources"
                ),
                "quick": CommandTemplate(
                    args=["-d", "{domain}", "-b", "google,bing,duckduckgo"],
                    timeout=120,
                    description="Quick harvest from search engines"
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # BBOT - OSINT Automation Framework
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="bbot",
            category=ToolCategory.RECON,
            description="OSINT automation framework for subdomain discovery and scanning",
            executable_names=["bbot"],
            install_hint="pip install bbot",
            aliases=["bbot_scanner", "osint_scanner"],
            commands={
                "subdomain": CommandTemplate(
                    args=["-t", "{target}", "-f", "subdomain-enum", "-y"],
                    timeout=600,
                    description="Subdomain enumeration"
                ),
                "web": CommandTemplate(
                    args=["-t", "{target}", "-f", "web-basic", "-y"],
                    timeout=600,
                    description="Basic web scanning"
                ),
                "quick": CommandTemplate(
                    args=["-t", "{target}", "-m", "nmap", "httpx", "-y"],
                    timeout=300,
                    description="Quick scan with nmap and httpx"
                ),
            }
        ),
    ]
