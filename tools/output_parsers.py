"""Output parsers for security tools."""

from typing import Dict, Any, List, Optional
import re

class ToolOutputParser:
    """Parser for tool execution output."""
    
    @staticmethod
    def parse_subfinder(stdout: str) -> Dict[str, Any]:
        """Parse subfinder/amass output using robust FQDN regex."""
        # Strict FQDN regex: allows letters, numbers, hyphens in labels, requires at least one dot
        # and excludes common process log noise like "[DNS]" or brackets.
        fqdn_pattern = re.compile(
            r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b',
            re.IGNORECASE
        )
        
        # Also filter out binary blobs or very long lines that are clearly not domains
        subdomains = []
        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Find all matches in the line
            matches = fqdn_pattern.findall(line)
            for m in matches:
                # Basic validation: length and common stop words
                m_lower = m.lower()
                if 4 < len(m_lower) < 253:
                    # Filter out common false positives from logs
                    if not any(stop in m_lower for stop in [".exe", ".so", ".dll", "github.com", "owasp.org"]):
                        subdomains.append(m_lower)
                        
        return {"subdomains": list(set(subdomains))}

    @staticmethod
    def parse_nmap(stdout: str) -> Dict[str, Any]:
        """Parse nmap output with service/version detection."""
        open_ports = []
        current_host = None
        current_ip = None
        
        lines = stdout.split('\n')
        for line in lines:
            line = line.strip()
            # Detect Nmap scan report for <host> (<ip>)
            if "Nmap scan report for" in line:
                parts = line.split()
                # Format: Nmap scan report for host.com (1.2.3.4)
                # or: Nmap scan report for 1.2.3.4
                ip_match = re.search(r'\(([\d\.]+)\)', line)
                if ip_match:
                    current_ip = ip_match.group(1)
                    host_part = line.replace("Nmap scan report for ", "").split(" (")[0]
                    current_host = host_part if host_part != current_ip else current_ip
                else:
                    last = parts[-1]
                    if re.match(r'^[\d\.]+$', last):
                        current_ip = last
                        current_host = last
            
            # Detect open ports: 80/tcp open http Apache httpd 2.4.41
            # 80/tcp open  http    Apache httpd 2.4.41 ((Ubuntu))
            port_match = re.match(r'^(\d+)/(tcp|udp)\s+open\s+([^\s]+)(?:\s+(.*))?$', line)
            if port_match and current_ip:
                port = int(port_match.group(1))
                protocol = port_match.group(2)
                service = port_match.group(3)
                banner = port_match.group(4) or ""
                
                open_ports.append({
                    "host": current_host,
                    "ip": current_ip,
                    "port": port,
                    "protocol": protocol,
                    "service": service,
                    "version": banner.strip(),
                    "fingerprint": f"{service} {banner}".strip()
                })
        
        return {"open_ports": open_ports}

    @staticmethod
    def parse_whois(stdout: str) -> Dict[str, Any]:
        """Parse WHOIS output."""
        # WHOIS is unstructured, just return text but maybe extract emails
        if "Malformed request" in stdout or "No match" in stdout or "No WHOIS" in stdout:
             return {"error": "WHOIS lookup failed or no data found", "raw": stdout}
             
        emails = set(re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', stdout))
        return {
            "emails": list(emails),
            "raw": stdout
        }

    @staticmethod
    def parse_ssl(stdout: str) -> Dict[str, Any]:
        """Parse sslscan/openssl output."""
        # Extract vulnerabilities like "Heartbleed", "Weak cipher", etc.
        vulns = []
        if "Heartbleed" in stdout and "vulnerable" in stdout.lower():
            vulns.append({"type": "ssl_vuln", "target": "SSL/TLS", "severity": "high", "details": {"name": "Heartbleed"}})
        
        # Extract certificate info
        cert_info = {}
        if "Subject:" in stdout:
            cert_info["subject"] = re.search(r'Subject:\s*(.*)', stdout).group(1) if re.search(r'Subject:\s*(.*)', stdout) else ""
            
        return {
            "vulnerabilities": vulns,
            "technologies": ["SSL", "TLS"]
        }

    @staticmethod
    def parse_http(stdout: str) -> Dict[str, Any]:
        """Parse httpx/curl output."""
        technologies = []
        if "Server:" in stdout:
            server = re.search(r'Server:\s*(.*)', stdout)
            if server:
                technologies.append(server.group(1).strip())
        
        # Simple extraction of titles/status codes
        status_code = re.search(r'\[(\d{3})\]', stdout)
        title = re.search(r'\[(.*?)\]', stdout) # This might be fragile
        
        return {
            "technologies": list(set(technologies)),
            "metadata": {
                "status_code": status_code.group(1) if status_code else None,
                "title": title.group(1) if title else None
            }
        }

    @staticmethod
    def parse_dns(stdout: str) -> Dict[str, Any]:
        """Parse dig/dns output."""
        # Extract IPs
        ips = set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', stdout))
        
        # Extract domains/subdomains (basic regex for hostname-like patterns)
        # Matches patterns like ns1.cloudflare.com
        domains = set()
        for line in stdout.split('\n'):
            line = line.strip()
            # If line ends with a dot and looks like a hostname
            if line.endswith('.') and '.' in line[:-1]:
                domains.add(line[:-1].lower())
                
        return {
            "ips": list(ips),
            "subdomains": list(domains)
        }

    @staticmethod
    def parse_generic(stdout: str) -> Dict[str, Any]:
        """Generic backup parser."""
        return {}

def get_parser(tool_name: str):
    """Get parser function for tool."""
    tool_name = tool_name.lower()
    
    # Subdomain discovery tools
    if any(alias in tool_name for alias in ["subfinder", "assetfinder", "amass", "subdomain"]):
        return ToolOutputParser.parse_subfinder
        
    # Scanning tools
    elif any(alias in tool_name for alias in ["nmap", "masscan", "rustscan", "port_scan"]):
        return ToolOutputParser.parse_nmap
        
    # WHOIS
    elif "whois" in tool_name:
        return ToolOutputParser.parse_whois
        
    # SSL/TLS
    elif any(alias in tool_name for alias in ["ssl", "tls", "cert"]):
        return ToolOutputParser.parse_ssl
        
    # HTTP/Web
    elif any(alias in tool_name for alias in ["http", "curl", "web", "header"]):
        return ToolOutputParser.parse_http
        
    # DNS
    elif any(alias in tool_name for alias in ["dig", "dns", "lookup"]):
        return ToolOutputParser.parse_dns
        
    return ToolOutputParser.parse_generic
