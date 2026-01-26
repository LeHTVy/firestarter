"""Output parsers for security tools."""

from typing import Dict, Any, List, Optional
import re

class ToolOutputParser:
    """Parser for tool execution output."""
    
    @staticmethod
    def parse_subfinder(stdout: str) -> Dict[str, Any]:
        """Parse subfinder output."""
        subdomains = []
        for line in stdout.split('\n'):
            line = line.strip()
            if line and '.' in line:
                subdomains.append(line.lower())
        return {"subdomains": list(set(subdomains))}

    @staticmethod
    def parse_nmap(stdout: str) -> Dict[str, Any]:
        """Parse nmap output."""
        open_ports = {} # host -> list of ports
        current_ip = None
        
        lines = stdout.split('\n')
        for line in lines:
            # Detect Nmap scan report for <host>
            if "Nmap scan report for" in line:
                parts = line.split()
                # Format: Nmap scan report for example.com (1.2.3.4)
                # or: Nmap scan report for 1.2.3.4
                ip_match = re.search(r'\(([\d\.]+)\)', line)
                if ip_match:
                    current_ip = ip_match.group(1)
                else:
                    # try getting last part if it looks like IP
                    last = parts[-1]
                    if re.match(r'^[\d\.]+$', last):
                        current_ip = last
            
            # Detect open ports: 80/tcp open http
            if "/tcp" in line and "open" in line and current_ip:
                port_part = line.split('/')[0]
                if port_part.isdigit():
                    port = int(port_part)
                    if current_ip not in open_ports:
                        open_ports[current_ip] = []
                    open_ports[current_ip].append(port)
        
        # Flatten for firestarter schema (ip -> ports)
        # return {"open_ports": open_ports}
        
        # Current firestarter expects "open_ports": [{"host": "...", "port": ...}] or simple list
        # Let's standardize to:
        findings = []
        for host, ports in open_ports.items():
            for port in ports:
                findings.append({"host": host, "port": port})
                
        return {"open_ports": findings}

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
    def parse_dns(stdout: str) -> Dict[str, Any]:
        """Parse dig/dns output."""
        # Simple extraction of IPs
        ips = set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', stdout))
        return {"ips": list(ips)}

    @staticmethod
    def parse_generic(stdout: str) -> Dict[str, Any]:
        """Generic backup parser."""
        return {}

def get_parser(tool_name: str):
    """Get parser function for tool."""
    tool_name = tool_name.lower()
    
    if "subfinder" in tool_name or "assetfinder" in tool_name or "amass" in tool_name:
        return ToolOutputParser.parse_subfinder
    elif "nmap" in tool_name or "masscan" in tool_name or "rustscan" in tool_name:
        return ToolOutputParser.parse_nmap
    elif "whois" in tool_name:
        return ToolOutputParser.parse_whois
    elif "dig" in tool_name or "dns" in tool_name:
        return ToolOutputParser.parse_dns
        
    return ToolOutputParser.parse_generic
