"""
OSINT Tools Specifications
==========================

Open Source Intelligence gathering.
"""
from typing import List
from app.tools.registry import ToolSpec, ToolCategory, CommandTemplate


def get_specs() -> List[ToolSpec]:
    """Get OSINT tool specifications."""
    return [
        # ─────────────────────────────────────────────────────────
        # SHODAN - Internet Search Engine
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="shodan",
            category=ToolCategory.OSINT,
            description="Search engine for Internet-connected devices",
            executable_names=["/home/hellrazor/rutx/venv/bin/shodan", "shodan"],
            install_hint="pip install shodan && shodan init YOUR_API_KEY",
            commands={
                "host": CommandTemplate(
                    args=["host", "{target}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "search": CommandTemplate(
                    args=["search", "--limit", "50", "{query}"],
                    timeout=60,
                    success_codes=[0]
                ),
                "domain": CommandTemplate(
                    args=["domain", "{domain}"],
                    timeout=60,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # SECURITYTRAILS - Threat Intelligence & Historical DNS (Python API)
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="securitytrails",
            category=ToolCategory.OSINT,
            description="SecurityTrails API: Historical DNS records, origin IP discovery (BEST for CDN/WAF bypass). Find pre-Cloudflare IPs.",
            executable_names=["python"],  # Python-based via handler, not CLI
            install_hint="Set SECURITYTRAILS_API_KEY in .env (Get free key: https://securitytrails.com/app/signup - 50 queries/month)",
            commands={
                # history: Get historical DNS records - find origin IP before CDN
                "history": CommandTemplate(
                    args=["securitytrails", "history", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                # domain: Get current DNS data for domain
                "domain": CommandTemplate(
                    args=["securitytrails", "domain", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                # subdomains: Enumerate subdomains
                "subdomains": CommandTemplate(
                    args=["securitytrails", "subdomains", "{domain}"],
                    timeout=60,
                    success_codes=[0]
                ),
                # associated: Find associated/related domains
                "associated": CommandTemplate(
                    args=["securitytrails", "associated", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                # whois: WHOIS history
                "whois": CommandTemplate(
                    args=["securitytrails", "whois", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # DNSRECON - DNS Enumeration
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="dnsrecon",
            category=ToolCategory.RECON,
            description="DNS enumeration and reconnaissance",
            executable_names=["dnsrecon"],
            install_hint="apt install dnsrecon",
            commands={
                "std": CommandTemplate(
                    args=["-d", "{domain}", "-t", "std"],
                    timeout=120,
                    success_codes=[0]
                ),
                "zone": CommandTemplate(
                    args=["-d", "{domain}", "-t", "axfr"],
                    timeout=60,
                    success_codes=[0]
                ),
                "brute": CommandTemplate(
                    args=["-d", "{domain}", "-t", "brt", "-D", "{wordlist}"],
                    timeout=300,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # RECON-NG - OSINT Framework (interactive, runs via bash)
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="recon-ng",
            category=ToolCategory.OSINT,
            description="Full-featured OSINT reconnaissance framework",
            executable_names=["bash"],  # Execute via bash since recon-ng is interactive
            install_hint="apt install recon-ng",
            commands={
                # Auto-install module first, then load and run
                "hosts": CommandTemplate(
                    args=["-c", "echo -e 'marketplace install recon/domains-hosts/hackertarget\\nmodules load recon/domains-hosts/hackertarget\\noptions set SOURCE {domain}\\nrun\\nexit' | recon-ng --no-analytics 2>/dev/null"],
                    timeout=180,
                    success_codes=[0, 1]
                ),
                "whois": CommandTemplate(
                    args=["-c", "echo -e 'marketplace install recon/domains-contacts/whois_pocs\\nmodules load recon/domains-contacts/whois_pocs\\noptions set SOURCE {domain}\\nrun\\nexit' | recon-ng --no-analytics 2>/dev/null"],
                    timeout=180,
                    success_codes=[0, 1]
                ),
                "subdomains": CommandTemplate(
                    args=["-c", "echo -e 'marketplace install recon/domains-hosts/hackertarget\\nmodules load recon/domains-hosts/hackertarget\\noptions set SOURCE {domain}\\nrun\\nexit' | recon-ng --no-analytics 2>/dev/null"],
                    timeout=180,
                    success_codes=[0, 1]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # FIERCE - DNS Reconnaissance
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="fierce",
            category=ToolCategory.RECON,
            description="DNS reconnaissance tool",
            executable_names=["fierce"],
            install_hint="pip install fierce",
            commands={
                "scan": CommandTemplate(
                    args=["--domain", "{domain}"],
                    timeout=300,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # SPIDERFOOT - OSINT Automation
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="spiderfoot",
            category=ToolCategory.OSINT,
            description="OSINT automation tool",
            executable_names=["spiderfoot", "sf.py"],
            install_hint="pip install spiderfoot",
            commands={
                "scan": CommandTemplate(
                    args=["-s", "{target}", "-t", "all", "-q"],
                    timeout=1800,  # 30 min
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # EMAILHARVESTER - Email Discovery
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="emailharvester",
            category=ToolCategory.OSINT,
            description="Email address harvesting tool",
            executable_names=["emailharvester"],
            install_hint="pip install emailharvester",
            commands={
                "harvest": CommandTemplate(
                    args=["-d", "{domain}", "-s", "google"],
                    timeout=120,
                    success_codes=[0]
                ),
            }
        ),
        
        # ─────────────────────────────────────────────────────────
        # CLATSCOPE - Intelligent OSINT (Python-based)
        # ─────────────────────────────────────────────────────────
        ToolSpec(
            name="clatscope",
            category=ToolCategory.OSINT,
            description="ClatScope OSINT: IP lookup, WHOIS, DNS, subdomains, SSL certs, email breach, phone lookup, origin IP discovery (CDN bypass via historical DNS + wayback)",
            executable_names=["python"],  # Python-based, not CLI
            install_hint="Already integrated via app.osint.clatscope",
            commands={
                "ip": CommandTemplate(
                    args=["osint", "ip", "{target}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "dns": CommandTemplate(
                    args=["osint", "dns", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "whois": CommandTemplate(
                    args=["osint", "whois", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "subdomain": CommandTemplate(
                    args=["osint", "subdomain", "{domain}"],
                    timeout=60,
                    success_codes=[0]
                ),
                "ssl": CommandTemplate(
                    args=["osint", "ssl", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "metadata": CommandTemplate(
                    args=["osint", "metadata", "{url}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "robots": CommandTemplate(
                    args=["osint", "robots", "{domain}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "phone": CommandTemplate(
                    args=["osint", "phone", "{phone}"],
                    timeout=15,
                    success_codes=[0]
                ),
                "email": CommandTemplate(
                    args=["osint", "email", "{email}"],
                    timeout=15,
                    success_codes=[0]
                ),
                "breach": CommandTemplate(
                    args=["osint", "breach", "{email}"],
                    timeout=30,
                    success_codes=[0]
                ),
                "reverse_dns": CommandTemplate(
                    args=["osint", "reverse_dns", "{ip}"],
                    timeout=15,
                    success_codes=[0]
                ),
                # find_origin: Combined lookup to find origin IP (bypass CDN)
                "find_origin": CommandTemplate(
                    args=["osint", "find_origin", "{domain}"],
                    timeout=60,
                    success_codes=[0]
                ),
                # full: Combined OSINT (IP + DNS + WHOIS + SSL)
                "full": CommandTemplate(
                    args=["osint", "full", "{domain}"],
                    timeout=90,
                    success_codes=[0]
                ),
            }
        ),
    ]


# ============================================================
# ClatScope Execution Functions (Python-based, not CLI)
# ============================================================

def execute_clatscope(command: str, params: dict) -> dict:
    """
    Execute Native OSINT command.
    
    Uses app.osint native modules (no external dependencies).
    
    Args:
        command: Command name (ip, dns, whois, etc.)
        params: Command parameters
    
    Returns:
        dict with results
    """
    # Import native OSINT modules
    from app.osint import lookup_ip, dns_lookup, whois_lookup, reverse_dns, resolve_domain
    from app.osint.subdomain import enumerate_subdomains
    from app.osint.web import check_ssl_cert, check_robots_txt, wayback_lookup, scrape_contacts
    from app.osint.phone import phone_info
    from app.osint.email import email_lookup, haveibeenpwned_check
    
    # Get target from params
    target = params.get("target") or params.get("domain") or params.get("ip") or ""
    
    # Map commands to native functions
    command_map = {
        "ip": lambda: lookup_ip(params.get("target") or params.get("ip") or resolve_domain(target)[0] if resolve_domain(target) else target),
        "dns": lambda: dns_lookup(target),
        "whois": lambda: whois_lookup(target),
        "subdomain": lambda: {"domain": target, "subdomains": enumerate_subdomains(target), "count": len(enumerate_subdomains(target))},
        "ssl": lambda: check_ssl_cert(target),
        "robots": lambda: check_robots_txt(target),
        "wayback": lambda: wayback_lookup(target),
        "contacts": lambda: scrape_contacts(f"https://{target}"),
        "phone": lambda: phone_info(params.get("phone", "")),
        "email": lambda: email_lookup(params.get("email", "")),
        "breach": lambda: haveibeenpwned_check(params.get("email", ""), params.get("api_key")),
        "reverse_dns": lambda: reverse_dns(params.get("ip", target)),
        "find_origin": lambda: {
            "domain": target,
            "resolved_ips": resolve_domain(target),
            "ip_info": lookup_ip(resolve_domain(target)[0]) if resolve_domain(target) else {},
            "wayback": wayback_lookup(target)
        },
        # Full recon combines multiple lookups
        "full": lambda: {
            "ip_info": lookup_ip(resolve_domain(target)[0]) if resolve_domain(target) else {},
            "dns": dns_lookup(target),
            "whois": whois_lookup(target),
            "ssl": check_ssl_cert(target),
        },
    }
    
    if command not in command_map:
        return {"error": f"Unknown OSINT command: {command}. Available: {list(command_map.keys())}"}
    
    try:
        result = command_map[command]()
        return {"success": True, "data": result, "command": command}
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_clatscope_result(command: str, result: dict) -> str:
    """Format ClatScope result for display."""
    if not result.get("success"):
        return f"❌ OSINT Error: {result.get('error')}"
    
    data = result.get("data", {})
    
    if data.get("error"):
        return f"⚠️ {data['error']}"
    
    lines = []
    
    if command == "ip":
        lines.append(f"📍 **IP Info:** {data.get('ip')}")
        lines.append(f"   Country: {data.get('country')}")
        lines.append(f"   City: {data.get('city')}, {data.get('region')}")
        lines.append(f"   ISP: {data.get('isp')}")
        lines.append(f"   Org: {data.get('org')}")
        if data.get('lat') and data.get('lon'):
            lines.append(f"   📍 Maps: https://maps.google.com/?q={data.get('lat')},{data.get('lon')}")
    
    elif command == "dns":
        lines.append(f"🔍 **DNS Records:** {data.get('domain')}")
        for rtype, records in data.get("records", {}).items():
            lines.append(f"   {rtype}: {', '.join(str(r) for r in records[:5])}")
    
    elif command == "whois":
        lines.append(f"📋 **WHOIS:** {data.get('domain')}")
        lines.append(f"   Registrar: {data.get('registrar')}")
        lines.append(f"   Created: {data.get('creation_date')}")
        lines.append(f"   Expires: {data.get('expiration_date')}")
        lines.append(f"   Org: {data.get('org')}")
        lines.append(f"   Country: {data.get('country')}")
    
    elif command == "subdomain":
        count = data.get("count", 0)
        lines.append(f"🌐 **Subdomains:** {count} found for {data.get('domain')}")
        for sub in data.get("subdomains", [])[:20]:
            lines.append(f"   • {sub}")
        if count > 20:
            lines.append(f"   ... and {count - 20} more")
    
    elif command == "ssl":
        lines.append(f"🔒 **SSL Certificate:** {data.get('domain')}")
        subject = data.get("subject", {})
        lines.append(f"   Subject: {subject.get('commonName')}")
        issuer = data.get("issuer", {})
        lines.append(f"   Issuer: {issuer.get('organizationName')}")
        lines.append(f"   Valid Until: {data.get('not_after')}")
    
    elif command == "phone":
        lines.append(f"📱 **Phone:** {data.get('formatted')}")
        lines.append(f"   Valid: {'✅' if data.get('valid') else '❌'}")
        lines.append(f"   Country: {data.get('country')}")
        lines.append(f"   Carrier: {data.get('carrier')}")
        tz = data.get('timezone', [])
        if tz:
            lines.append(f"   Timezone: {', '.join(tz)}")
    
    elif command == "breach":
        if data.get("breached"):
            lines.append(f"🚨 **EMAIL BREACHED:** {data.get('email')}")
            lines.append(f"   Found in: {data.get('breach_count')} breaches")
            for breach in data.get("breaches", []):
                lines.append(f"   • {breach}")
        else:
            lines.append(f"✅ No breaches found for: {data.get('email')}")
    
    elif command == "metadata":
        lines.append(f"📄 **Web Metadata:** {data.get('url')}")
        lines.append(f"   Title: {data.get('title')}")
        lines.append(f"   Server: {data.get('server')}")
        lines.append(f"   Status: {data.get('status_code')}")
        meta = data.get("meta", {})
        if meta.get("description"):
            lines.append(f"   Description: {meta.get('description')[:100]}...")
    
    elif command == "robots":
        lines.append(f"🤖 **Robots/Sitemap:** {data.get('domain')}")
        if data.get("robots_txt"):
            lines.append(f"   robots.txt: Found ({len(data.get('robots_txt', ''))} chars)")
        if data.get("sitemap"):
            lines.append(f"   sitemap.xml: {data.get('sitemap')} ({data.get('sitemap_size')} bytes)")
    
    else:
        # Generic formatting
        lines.append(f"📊 **OSINT Result** ({command}):")
        for key, value in data.items():
            if value and not isinstance(value, (dict, list)):
                lines.append(f"   {key}: {value}")
    
    return "\n".join(lines)

