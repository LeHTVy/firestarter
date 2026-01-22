"""DNS and domain reconnaissance tools with subprocess streaming.

Implements dns_enum, whois_lookup, subdomain_discovery using CLI tools.
"""

from typing import Dict, Any, Optional, Callable, List
import re
from tools.implementations.cli_executor import (
    run_cli_command, 
    check_tool_installed,
    parse_key_value_output
)


def dns_enum(domain: str,
            record_types: Optional[List[str]] = None,
            nameserver: Optional[str] = None,
            stream_callback: Optional[Callable[[str], None]] = None,
            timeout: int = 120) -> Dict[str, Any]:
    """Perform DNS enumeration using dig/host/nslookup.
    
    Args:
        domain: Target domain
        record_types: DNS record types to query (default: A, AAAA, MX, NS, TXT, SOA, CNAME)
        nameserver: Specific nameserver to query
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        DNS enumeration results
    """
    if not record_types:
        record_types = ["A", "AAAA", "MX", "NS", "TXT", "SOA", "CNAME"]
    
    results = {
        "domain": domain,
        "records": {},
        "nameservers": [],
        "mail_servers": []
    }
    
    all_output = []
    
    # Check for dig (preferred), then host, then nslookup
    if check_tool_installed("dig"):
        tool = "dig"
    elif check_tool_installed("host"):
        tool = "host"
    elif check_tool_installed("nslookup"):
        tool = "nslookup"
    else:
        return {
            "success": False,
            "error": "No DNS tools found. Install dig, host, or nslookup.",
            "results": None
        }
    
    if stream_callback:
        stream_callback(f"🔍 DNS Enumeration for {domain} using {tool}")
    
    for record_type in record_types:
        if tool == "dig":
            cmd = ["dig", "+short", record_type, domain]
            if nameserver:
                cmd.insert(1, f"@{nameserver}")
        elif tool == "host":
            cmd = ["host", "-t", record_type, domain]
            if nameserver:
                cmd.append(nameserver)
        else:  # nslookup
            cmd = ["nslookup", f"-type={record_type}", domain]
            if nameserver:
                cmd.append(nameserver)
        
        result = run_cli_command(cmd, timeout=30, stream_callback=stream_callback)
        
        if result.get("success"):
            output = result.get("raw_output", "")
            all_output.append(f"=== {record_type} Records ===\n{output}")
            
            # Parse results
            records = _parse_dns_output(output, record_type, tool)
            if records:
                results["records"][record_type] = records
                
                # Extract nameservers and mail servers
                if record_type == "NS":
                    results["nameservers"].extend(records)
                elif record_type == "MX":
                    results["mail_servers"].extend([r.split()[-1] if " " in r else r for r in records])
    
    return {
        "success": True,
        "results": results,
        "raw_output": "\n\n".join(all_output)
    }


def whois_lookup(target: str,
                stream_callback: Optional[Callable[[str], None]] = None,
                timeout: int = 60) -> Dict[str, Any]:
    """Perform WHOIS lookup.
    
    Args:
        target: Target domain or IP address
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        WHOIS lookup results
    """
    # Accept both 'target' and 'domain' for backward compatibility
    domain = target
    
    if not check_tool_installed("whois"):
        return {
            "success": False,
            "error": "whois command not found. Install with: apt install whois",
            "results": None
        }
    
    if stream_callback:
        stream_callback(f"WHOIS Lookup for {domain}")
    
    cmd = ["whois", domain]
    result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
    
    if not result.get("success"):
        return result
    
    raw_output = result.get("raw_output", "")
    
    # Parse WHOIS output
    parsed = _parse_whois_output(raw_output)
    
    return {
        "success": True,
        "results": {
            "domain": domain,
            "registrar": parsed.get("Registrar", parsed.get("registrar", "")),
            "creation_date": parsed.get("Creation Date", parsed.get("created", "")),
            "expiration_date": parsed.get("Registry Expiry Date", parsed.get("expires", "")),
            "updated_date": parsed.get("Updated Date", parsed.get("changed", "")),
            "name_servers": _extract_nameservers(raw_output),
            "status": parsed.get("Domain Status", ""),
            "registrant": parsed.get("Registrant Organization", parsed.get("Registrant Name", "")),
            "registrant_country": parsed.get("Registrant Country", ""),
            "admin_email": parsed.get("Admin Email", ""),
            "tech_email": parsed.get("Tech Email", ""),
            "raw_data": parsed
        },
        "raw_output": raw_output
    }


def subdomain_discovery(domain: str,
                       tool: str = "auto",
                       wordlist: Optional[str] = None,
                       stream_callback: Optional[Callable[[str], None]] = None,
                       timeout: int = 600) -> Dict[str, Any]:
    """Discover subdomains using subfinder, amass, or dnsrecon.
    
    Args:
        domain: Target domain
        tool: Tool to use (auto, subfinder, amass, dnsrecon)
        wordlist: Optional wordlist for brute forcing
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        Subdomain discovery results
    """
    # Auto-detect available tool
    if tool == "auto":
        if check_tool_installed("subfinder"):
            tool = "subfinder"
        elif check_tool_installed("amass"):
            tool = "amass"
        elif check_tool_installed("dnsrecon"):
            tool = "dnsrecon"
        elif check_tool_installed("sublist3r"):
            tool = "sublist3r"
        else:
            return {
                "success": False,
                "error": "No subdomain enumeration tools found. Install subfinder, amass, or dnsrecon.",
                "results": None
            }
    
    if stream_callback:
        stream_callback(f"🔍 Subdomain Discovery for {domain} using {tool}")
    
    # Build command based on tool
    if tool == "subfinder":
        cmd = ["subfinder", "-d", domain, "-silent"]
    elif tool == "amass":
        cmd = ["amass", "enum", "-passive", "-d", domain]
    elif tool == "dnsrecon":
        cmd = ["dnsrecon", "-d", domain, "-t", "std"]
        if wordlist:
            cmd.extend(["-D", wordlist, "-t", "brt"])
    elif tool == "sublist3r":
        cmd = ["sublist3r", "-d", domain, "-o", "/dev/stdout"]
    else:
        return {
            "success": False,
            "error": f"Unknown tool: {tool}",
            "results": None
        }
    
    result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
    
    if not result.get("success"):
        return result
    
    raw_output = result.get("raw_output", "")
    
    # Parse subdomains from output
    subdomains = _parse_subdomain_output(raw_output, domain, tool)
    
    # Deduplicate and sort
    subdomains = sorted(set(subdomains))
    
    if stream_callback:
        stream_callback(f"📊 Found {len(subdomains)} unique subdomains")
    
    return {
        "success": True,
        "results": {
            "domain": domain,
            "tool_used": tool,
            "subdomains": subdomains,
            "count": len(subdomains)
        },
        "raw_output": raw_output
    }


def _parse_dns_output(output: str, record_type: str, tool: str) -> List[str]:
    """Parse DNS tool output."""
    records = []
    
    for line in output.split("\n"):
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        
        if tool == "dig":
            # dig +short output is already clean
            if line:
                records.append(line)
        elif tool == "host":
            # host output: "domain has address 1.2.3.4"
            if " has " in line or " mail " in line:
                parts = line.split()
                if parts:
                    records.append(parts[-1])
        else:  # nslookup
            # nslookup output varies
            if "=" in line or "address" in line.lower():
                parts = line.split()
                if parts:
                    records.append(parts[-1])
    
    return records


def _parse_whois_output(output: str) -> Dict[str, str]:
    """Parse WHOIS output to key-value pairs."""
    result = {}
    
    for line in output.split("\n"):
        if ":" in line and not line.strip().startswith("%") and not line.strip().startswith("#"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                if key and value:
                    result[key] = value
    
    return result


def _extract_nameservers(whois_output: str) -> List[str]:
    """Extract nameservers from WHOIS output."""
    nameservers = []
    
    # Look for "Name Server:" or "nserver:" lines
    patterns = [
        r"Name Server[:\s]+([^\s]+)",
        r"nserver[:\s]+([^\s]+)",
        r"NS[:\s]+([^\s]+)"
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, whois_output, re.IGNORECASE)
        nameservers.extend(matches)
    
    return list(set(ns.lower().rstrip(".") for ns in nameservers if ns))


def _parse_subdomain_output(output: str, domain: str, tool: str) -> List[str]:
    """Parse subdomain enumeration output."""
    subdomains = []
    domain_lower = domain.lower()
    
    for line in output.split("\n"):
        line = line.strip().lower()
        
        # Skip empty lines and comments
        if not line or line.startswith("#") or line.startswith("["):
            continue
        
        # Extract subdomain - look for anything ending with target domain
        # Handle different tool output formats
        if domain_lower in line:
            # Extract the subdomain part
            match = re.search(rf'([a-z0-9][-a-z0-9.]*\.{re.escape(domain_lower)})', line)
            if match:
                subdomain = match.group(1)
                if subdomain.endswith(domain_lower):
                    subdomains.append(subdomain)
        elif tool == "subfinder" and "." in line:
            # subfinder outputs one subdomain per line
            if line.endswith(domain_lower) or f".{domain_lower}" in line:
                subdomains.append(line)
    
    return subdomains
