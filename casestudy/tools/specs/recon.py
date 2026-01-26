"""
Reconnaissance Tools Specifications
====================================

Subdomain enumeration, OSINT, DNS lookup.
"""
from typing import List
from app.tools.registry import ToolSpec, ToolCategory, CommandTemplate


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
            commands={
                "enum": CommandTemplate(
                    args=["-d", "{domain}", "-silent"],
                    timeout=120,
                    success_codes=[0]
                ),
                "enum_all": CommandTemplate(
                    args=["-d", "{domain}", "-all", "-silent"],
                    timeout=300,
                    success_codes=[0]
                ),
                "to_file": CommandTemplate(
                    args=["-d", "{domain}", "-silent", "-o", "{output}"],
                    timeout=120,
                    success_codes=[0]
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
            install_hint="snap install amass",
            commands={
                "passive": CommandTemplate(
                    args=["enum", "-passive", "-d", "{domain}"],
                    timeout=600,  # 10 min - amass is slow
                    success_codes=[0]
                ),
                "active": CommandTemplate(
                    args=["enum", "-d", "{domain}"],
                    timeout=1800,  # 30 min for active
                    success_codes=[0]
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
                    success_codes=[0, 1]  # whois can return 1 for some queries
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
                "any": CommandTemplate(
                    args=["+short", "ANY", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "mx": CommandTemplate(
                    args=["+short", "MX", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "ns": CommandTemplate(
                    args=["+short", "NS", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "txt": CommandTemplate(
                    args=["+short", "TXT", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # THEHARVESTER - OSINT (installed via pip)
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="theHarvester",
            category=ToolCategory.OSINT,
            description="Email and subdomain harvesting",
            executable_names=["theHarvester", "theharvester"],
            install_hint="pip install git+https://github.com/laramies/theHarvester.git",
            commands={
                "quick": CommandTemplate(
                    # Fast sources that don't require API keys
                    args=["-d", "{domain}", "-b", "all"],
                    timeout=180,
                    success_codes=[0]
                ),
                "all": CommandTemplate(
                    args=["-d", "{domain}", "-b", "all"],
                    timeout=600,  # 10 min for all sources
                    success_codes=[0]
                ),
                "subdomains": CommandTemplate(
                    # Focus on subdomains
                    args=["-d", "{domain}", "-b", "all"],
                    timeout=180,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # BBOT - All-in-one Reconnaissance
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="bbot",
            category=ToolCategory.RECON,
            description="Recursive internet scanner with subdomain enum",
            executable_names=["bbot"],
            install_hint="pipx install bbot",
            commands={
                "subdomains": CommandTemplate(
                    args=["-t", "{domain}", "-f", "subdomain-enum", "-y", "--silent"],
                    timeout=600,
                    success_codes=[0]
                ),
                "web": CommandTemplate(
                    args=["-t", "{domain}", "-f", "web-basic", "-y", "--silent"],
                    timeout=600,
                    success_codes=[0]
                ),
                "full": CommandTemplate(
                    args=["-t", "{domain}", "-p", "subdomain-enum", "web-basic", "-y"],
                    timeout=1200,
                    success_codes=[0]
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
                    success_codes=[0]
                ),
                "js": CommandTemplate(
                    args=["-u", "{url}", "-silent", "-jc", "-d", "2"],
                    timeout=300,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # CLOUDFLARED - Cloudflare Tunnel
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="cloudflared",
            category=ToolCategory.RECON,
            description="Cloudflare tunnel and DNS utilities",
            executable_names=["cloudflared"],
            install_hint="apt install cloudflared",
            commands={
                "trace": CommandTemplate(
                    args=["access", "trace", "{url}"],
                    timeout=60,
                    success_codes=[0, 1]
                ),
            }
        ),
    ]
