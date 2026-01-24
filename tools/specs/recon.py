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
            aliases=["finder"],
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
            aliases=["mass"],
            commands={
                "passive": CommandTemplate(
                    args=["enum", "-passive", "-d", "{domain}"],
                    timeout=600,
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
                    args=["-u", "{url}", "-silent", "-status-code", "-title"],
                    timeout=60,
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
                    args=["-u", "{url}", "-silent", "-d", "3"],
                    timeout=300,
                    description="Deep crawl"
                ),
                "js": CommandTemplate(
                    args=["-u", "{url}", "-silent", "-jc", "-d", "2"],
                    timeout=300,
                    description="JavaScript discovery"
                ),
            }
        ),
    ]
