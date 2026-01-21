"""Nmap tool implementation."""

import nmap
from typing import Dict, Any, Optional
import json


def execute(target: str, ports: Optional[str] = None, options: Optional[str] = None) -> Dict[str, Any]:
    """Execute Nmap scan.
    
    Args:
        target: IP address or hostname to scan
        ports: Port range or specific ports (e.g., "1-1000", "80,443")
        options: Additional nmap options
        
    Returns:
        Scan results as dictionary
    """
    try:
        nm = nmap.PortScanner()
        
        # Build scan arguments
        scan_args = ""
        if ports:
            scan_args += f"-p {ports} "
        if options:
            scan_args += options
        
        # Perform scan
        nm.scan(hosts=target, arguments=scan_args.strip())
        
        # Extract results
        results = {
            "target": target,
            "scan_info": {},
            "hosts": {}
        }
        
        for host in nm.all_hosts():
            host_info = {
                "hostname": nm[host].hostname(),
                "state": nm[host].state(),
                "protocols": {}
            }
            
            for proto in nm[host].all_protocols():
                ports_info = {}
                for port in nm[host][proto].keys():
                    port_info = nm[host][proto][port]
                    ports_info[str(port)] = {
                        "state": port_info['state'],
                        "name": port_info.get('name', ''),
                        "product": port_info.get('product', ''),
                        "version": port_info.get('version', ''),
                        "extrainfo": port_info.get('extrainfo', '')
                    }
                host_info["protocols"][proto] = ports_info
            
            results["hosts"][host] = host_info
        
        results["scan_info"] = {
            "scanstats": nm.scanstats(),
            "command_line": nm.command_line()
        }
        
        return {
            "success": True,
            "results": results,
            "raw_output": json.dumps(results, indent=2)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": None
        }
