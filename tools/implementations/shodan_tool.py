"""Shodan OSINT tool implementation."""

import os
import json
import shodan
from typing import Dict, Any, Optional

def search(query: str, filters: Optional[Dict] = None) -> Dict[str, Any]:
    """Search Shodan for internet-connected devices and services.
    
    Args:
        query: Shodan search query
        filters: Additional search filters (optional)
        
    Returns:
        Dict with search results and metadata
    """
    api_key = os.getenv("SHODAN_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "Shodan API key not found. Please set SHODAN_API_KEY environment variable.",
            "results": {}
        }
        
    try:
        api = shodan.Shodan(api_key)
        
        # Build effective query
        full_query = query
        if filters:
            for key, value in filters.items():
                if value:
                    full_query += f" {key}:{value}"
        
        # Execute search
        results = api.search(full_query)
        
        # Standardize results for Firestarter findings
        ips = []
        open_ports = []
        vulnerabilities = []
        technologies = []
        
        for match in results.get('matches', []):
            ip = match.get('ip_str')
            if not ip:
                continue
                
            ips.append(ip)
            
            # Port and Service info
            port = match.get('port')
            if port:
                open_ports.append({
                    "ip": ip,
                    "port": port,
                    "protocol": match.get('transport', 'tcp'),
                    "service": match.get('product', ''),
                    "version": match.get('version', ''),
                    "host": match.get('hostnames', [ip])[0] if match.get('hostnames') else ip
                })
            
            # Extract technologies/products
            product = match.get('product')
            if product:
                technologies.append(product)
                
            # Extract vulnerabilities (CVEs)
            vulns = match.get('vulns', [])
            if vulns:
                for cve in vulns:
                    vulnerabilities.append({
                        "type": "cve",
                        "target": ip,
                        "severity": "unknown",
                        "cve": cve,
                        "details": {"product": product}
                    })
        
        return {
            "success": True,
            "results": {
                "ips": list(set(ips)),
                "open_ports": open_ports,
                "vulnerabilities": vulnerabilities,
                "technologies": list(set(technologies)),
                "total": results.get('total', 0)
            },
            "output": f"Shodan found {results.get('total', 0)} results for query: {full_query}"
        }
        
    except shodan.APIError as e:
        return {
            "success": False,
            "error": f"Shodan API Error: {str(e)}",
            "results": {}
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error during Shodan search: {str(e)}",
            "results": {}
        }
