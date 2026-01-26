"""
OSINT Tool Handlers
===================

Handles: shodan, dnsrecon, fierce, theHarvester, securitytrails
"""
from typing import Dict, Any
from app.tools.handlers import register_handler
import subprocess
import requests
import json


@register_handler("shodan")
def handle_shodan(action_input: Dict[str, Any], state: Any) -> str:
    """Search Shodan for hosts/services."""
    query = action_input.get("query", "")
    host = action_input.get("host", action_input.get("ip", ""))
    
    if not query and not host:
        return """Error: query or host required. Examples:
  shodan with {"query": "apache country:us"}
  shodan with {"host": "8.8.8.8"}
  shodan with {"query": "port:22 ssh"}
  
Note: Requires SHODAN_API_KEY environment variable or shodan init <key>"""
    
    try:
        if host:
            print(f"  🔍 Shodan lookup: {host}...")
            result = subprocess.run(
                ["shodan", "host", host],
                capture_output=True,
                text=True,
                timeout=30
            )
        else:
            print(f"  🔍 Shodan search: {query}...")
            result = subprocess.run(
                ["shodan", "search", "--limit", "10", query],
                capture_output=True,
                text=True,
                timeout=30
            )
        
        if result.returncode != 0 and "API" in result.stderr:
            return "⚠️ Shodan API key required. Run: shodan init YOUR_API_KEY"
        
        return f"═══ SHODAN ═══\n{result.stdout}\n{result.stderr}"
        
    except FileNotFoundError:
        return "⚠️ shodan not installed. Install: pip install shodan"
    except Exception as e:
        return f"Shodan error: {e}"


@register_handler("dnsrecon")
def handle_dnsrecon(action_input: Dict[str, Any], state: Any) -> str:
    """DNS reconnaissance."""
    domain = action_input.get("domain", "")
    
    if not domain:
        return "Error: domain required. Example: dnsrecon with {\"domain\": \"example.com\"}"
    
    print(f"  🌐 DNSRecon on {domain}...")
    
    try:
        result = subprocess.run(
            ["dnsrecon", "-d", domain],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        return f"═══ DNSRECON: {domain} ═══\n{result.stdout[:4000]}"
        
    except FileNotFoundError:
        return "⚠️ dnsrecon not installed. Install: sudo apt install dnsrecon OR pip install dnsrecon"
    except subprocess.TimeoutExpired:
        return "dnsrecon timed out"
    except Exception as e:
        return f"dnsrecon error: {e}"


@register_handler("fierce")
def handle_fierce(action_input: Dict[str, Any], state: Any) -> str:
    """Fierce DNS brute-force."""
    domain = action_input.get("domain", "")
    
    if not domain:
        return "Error: domain required. Example: fierce with {\"domain\": \"example.com\"}"
    
    print(f"  🔥 Fierce on {domain}...")
    
    try:
        result = subprocess.run(
            ["fierce", "--domain", domain],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return f"═══ FIERCE: {domain} ═══\n{result.stdout[:4000]}"
        
    except FileNotFoundError:
        return "⚠️ fierce not installed. Install: pip install fierce"
    except subprocess.TimeoutExpired:
        return "fierce timed out"
    except Exception as e:
        return f"fierce error: {e}"


@register_handler("theharvester")
def handle_theharvester(action_input: Dict[str, Any], state: Any) -> str:
    """theHarvester email/domain OSINT."""
    domain = action_input.get("domain", "")
    source = action_input.get("source", "all")
    
    if not domain:
        return """Error: domain required. Examples:
  theharvester with {"domain": "example.com"}
  theharvester with {"domain": "example.com", "source": "google"}
  
Sources: all, google, bing, linkedin, twitter, duckduckgo"""
    
    print(f"  🌾 theHarvester on {domain} (source: {source})...")
    
    try:
        result = subprocess.run(
            ["theHarvester", "-d", domain, "-b", source],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return f"═══ THEHARVESTER: {domain} ═══\n{result.stdout[:4000]}"
        
    except FileNotFoundError:
        return "⚠️ theHarvester not installed. Install: sudo apt install theharvester OR pip install theHarvester"
    except subprocess.TimeoutExpired:
        return "theHarvester timed out"
    except Exception as e:
        return f"theHarvester error: {e}"


@register_handler("securitytrails")
def handle_securitytrails(action_input: Dict[str, Any], state: Any) -> str:
    """SecurityTrails API - Historical DNS, subdomains, associated domains.
    
    Best tool for finding origin IP behind Cloudflare/CDN.
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()
    SECURITYTRAILS_API_KEY = os.getenv("SECURITYTRAILS_API_KEY", "")
    
    domain = action_input.get("domain", "")
    command = action_input.get("command", "history")  # history, domain, subdomains, associated, whois
    
    if not domain:
        return """Error: domain required. Examples:
  securitytrails with {"domain": "example.com", "command": "history"}  # Find origin IP
  securitytrails with {"domain": "example.com", "command": "subdomains"}
  securitytrails with {"domain": "example.com", "command": "associated"}
  
Commands: history (DNS history), domain (current DNS), subdomains, associated, whois"""
    
    if not SECURITYTRAILS_API_KEY:
        return """⚠️ SecurityTrails API key not configured.

To set up:
1. Get free API key at https://securitytrails.com/app/signup
2. Add to config.py: SECURITYTRAILS_API_KEY = "your_key_here"

Free tier: 50 queries/month - perfect for CDN bypass recon"""
    
    headers = {
        "APIKEY": SECURITYTRAILS_API_KEY,
        "Content-Type": "application/json"
    }
    
    base_url = "https://api.securitytrails.com/v1"
    
    try:
        print(f"  🔐 SecurityTrails {command}: {domain}...")
        
        if command == "history":
            # Historical DNS - best for finding origin IP
            url = f"{base_url}/history/{domain}/dns/a"
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get("records", [])
                
                output = f"═══ SECURITYTRAILS DNS HISTORY: {domain} ═══\n"
                output += f"Total historical records: {len(records)}\n\n"
                
                # Extract unique IPs (potential origin servers)
                unique_ips = set()
                for record in records:
                    for value in record.get("values", []):
                        ip = value.get("ip", "")
                        if ip:
                            unique_ips.add(ip)
                            first_seen = record.get("first_seen", "unknown")
                            last_seen = record.get("last_seen", "unknown")
                            output += f"  IP: {ip}\n"
                            output += f"      First seen: {first_seen}\n"
                            output += f"      Last seen: {last_seen}\n\n"
                
                output += f"\n🎯 Unique IPs found: {len(unique_ips)}\n"
                output += "These may include pre-CDN origin IPs!\n"
                return output
            
        elif command == "subdomains":
            url = f"{base_url}/domain/{domain}/subdomains"
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                subdomains = data.get("subdomains", [])
                
                output = f"═══ SECURITYTRAILS SUBDOMAINS: {domain} ═══\n"
                output += f"Found {len(subdomains)} subdomains:\n\n"
                
                for sub in subdomains[:50]:  # Limit output
                    output += f"  • {sub}.{domain}\n"
                
                if len(subdomains) > 50:
                    output += f"\n  ... and {len(subdomains) - 50} more\n"
                
                return output
            
        elif command == "associated":
            url = f"{base_url}/domain/{domain}/associated"
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get("records", [])
                
                output = f"═══ SECURITYTRAILS ASSOCIATED: {domain} ═══\n"
                output += f"Found {len(records)} associated domains:\n\n"
                
                for record in records[:30]:
                    alexa = record.get("alexa_rank", "N/A")
                    hostname = record.get("hostname", "unknown")
                    output += f"  • {hostname} (Alexa: {alexa})\n"
                
                return output
            
        elif command == "domain":
            url = f"{base_url}/domain/{domain}"
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                output = f"═══ SECURITYTRAILS DOMAIN: {domain} ═══\n"
                output += f"Alexa Rank: {data.get('alexa_rank', 'N/A')}\n"
                
                current_dns = data.get("current_dns", {})
                
                # A records
                a_records = current_dns.get("a", {}).get("values", [])
                if a_records:
                    output += f"\nA Records:\n"
                    for r in a_records:
                        output += f"  • {r.get('ip', 'unknown')}\n"
                
                # MX records
                mx_records = current_dns.get("mx", {}).get("values", [])
                if mx_records:
                    output += f"\nMX Records:\n"
                    for r in mx_records:
                        output += f"  • {r.get('hostname', 'unknown')} (priority: {r.get('priority', 'N/A')})\n"
                
                # NS records
                ns_records = current_dns.get("ns", {}).get("values", [])
                if ns_records:
                    output += f"\nNS Records:\n"
                    for r in ns_records:
                        output += f"  • {r.get('nameserver', 'unknown')}\n"
                
                return output
            
        elif command == "whois":
            url = f"{base_url}/domain/{domain}/whois"
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                output = f"═══ SECURITYTRAILS WHOIS: {domain} ═══\n"
                output += json.dumps(data, indent=2)[:3000]
                return output
        
        # Handle API errors
        if response.status_code == 401:
            return "⚠️ SecurityTrails API key invalid. Check config.py"
        elif response.status_code == 429:
            return "⚠️ SecurityTrails rate limit exceeded. Free tier: 50 queries/month"
        else:
            return f"SecurityTrails API error: {response.status_code} - {response.text[:500]}"
            
    except requests.Timeout:
        return "SecurityTrails request timed out"
    except Exception as e:
        return f"SecurityTrails error: {e}"
