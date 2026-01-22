"""Nmap tool implementation with subprocess streaming.

Inspired by rutx approach for reliable tool execution.
Supports both python-nmap library and native subprocess execution.
"""

import subprocess
import shutil
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime
import tempfile
import os


# Scan profiles (like rutx)
SCAN_PROFILES = {
    "quick": "-F -T4",                           # Fast top 100 ports
    "default": "-sV -sC",                        # Service/version + scripts
    "aggressive": "-A -T4",                      # Full OS/version detection
    "vuln": "-sV --script=vuln",                 # Vulnerability scripts
    "stealth": "-sS -T2",                        # SYN stealth scan
    "comprehensive": "-sS -sV -sC -O -A -T4",   # Everything (requires root)
    "top1000": "-sV -sC --top-ports 1000",      # Top 1000 ports
    "allports": "-sV -p-",                       # All 65535 ports
}


def execute(target: str, 
           ports: Optional[str] = None, 
           options: Optional[str] = None,
           profile: Optional[str] = None,
           stream_callback: Optional[Callable[[str], None]] = None,
           timeout: int = 1200) -> Dict[str, Any]:
    """Execute Nmap scan with streaming output.
    
    Args:
        target: IP address or hostname to scan
        ports: Port range or specific ports (e.g., "1-1000", "80,443")
        options: Additional nmap options
        profile: Scan profile name (quick, aggressive, vuln, etc.)
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds (default: 20 minutes)
        
    Returns:
        Scan results as dictionary
    """
    # Check if nmap is installed
    nmap_path = shutil.which("nmap")
    if not nmap_path:
        error_msg = "Nmap is not installed. Please install nmap first."
        if stream_callback:
            stream_callback(f"❌ Error: {error_msg}")
        return {"success": False, "error": error_msg, "results": None}
    
    # Build command
    cmd = [nmap_path]
    
    # Add profile options if specified
    if profile and profile in SCAN_PROFILES:
        cmd.extend(SCAN_PROFILES[profile].split())
        if stream_callback:
            stream_callback(f"📋 Using scan profile: {profile}")
    
    # Add port specification
    if ports:
        cmd.extend(["-p", ports])
    
    # Add custom options
    if options:
        cmd.extend(options.split())
    
    # Add XML output for parsing
    xml_file = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
    xml_path = xml_file.name
    xml_file.close()
    cmd.extend(["-oX", xml_path])
    
    # Add target
    cmd.append(target)
    
    if stream_callback:
        stream_callback(f"🚀 Starting Nmap scan on {target}")
        stream_callback(f"📝 Command: {' '.join(cmd)}")
    
    # Execute with subprocess streaming
    start_time = datetime.utcnow()
    raw_output_lines = []
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
        
        # Stream output in real-time
        for line in iter(process.stdout.readline, ''):
            line = line.rstrip()
            if line:
                raw_output_lines.append(line)
                if stream_callback:
                    stream_callback(line)
        
        # Wait for completion with timeout
        return_code = process.wait(timeout=timeout)
        
        end_time = datetime.utcnow()
        elapsed = (end_time - start_time).total_seconds()
        
        if stream_callback:
            stream_callback(f"✅ Scan completed in {elapsed:.2f}s (exit code: {return_code})")
        
        # Parse XML results
        results = _parse_nmap_xml(xml_path)
        
        # Add metadata
        results["scan_info"] = {
            "command_line": " ".join(cmd),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "elapsed_seconds": elapsed,
            "return_code": return_code,
            "profile": profile
        }
        
        # Cleanup XML file
        try:
            os.unlink(xml_path)
        except Exception:
            pass
        
        return {
            "success": return_code == 0,
            "results": results,
            "raw_output": "\n".join(raw_output_lines),
            "error": None if return_code == 0 else f"Nmap exited with code {return_code}"
        }
        
    except subprocess.TimeoutExpired:
        process.kill()
        error_msg = f"Scan timed out after {timeout} seconds"
        if stream_callback:
            stream_callback(f"⏰ {error_msg}")
        
        # Try to cleanup
        try:
            os.unlink(xml_path)
        except Exception:
            pass
        
        return {
            "success": False,
            "error": error_msg,
            "results": None,
            "raw_output": "\n".join(raw_output_lines)
        }
        
    except Exception as e:
        error_msg = str(e)
        if stream_callback:
            stream_callback(f"❌ Error: {error_msg}")
        
        # Try to cleanup
        try:
            os.unlink(xml_path)
        except Exception:
            pass
        
        return {
            "success": False,
            "error": error_msg,
            "results": None,
            "raw_output": "\n".join(raw_output_lines)
        }


def _parse_nmap_xml(xml_path: str) -> Dict[str, Any]:
    """Parse Nmap XML output file.
    
    Args:
        xml_path: Path to XML output file
        
    Returns:
        Parsed results dictionary
    """
    results = {
        "hosts": [],
        "summary": {
            "hosts_up": 0,
            "hosts_down": 0,
            "total_ports": 0,
            "open_ports": 0
        }
    }
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Parse each host
        for host in root.findall('.//host'):
            host_info = _parse_host(host)
            if host_info:
                results["hosts"].append(host_info)
                
                if host_info.get("status") == "up":
                    results["summary"]["hosts_up"] += 1
                    results["summary"]["open_ports"] += len(host_info.get("open_ports", []))
                else:
                    results["summary"]["hosts_down"] += 1
        
        # Parse runstats
        runstats = root.find('.//runstats')
        if runstats is not None:
            finished = runstats.find('finished')
            if finished is not None:
                results["summary"]["elapsed"] = finished.get("elapsed")
                results["summary"]["exit"] = finished.get("exit")
            
            hosts_elem = runstats.find('hosts')
            if hosts_elem is not None:
                results["summary"]["hosts_total"] = int(hosts_elem.get("total", 0))
                
    except ET.ParseError as e:
        results["parse_error"] = str(e)
    except Exception as e:
        results["parse_error"] = str(e)
    
    return results


def _parse_host(host_elem: ET.Element) -> Dict[str, Any]:
    """Parse a single host element.
    
    Args:
        host_elem: XML host element
        
    Returns:
        Host information dictionary
    """
    host_info = {
        "status": "unknown",
        "addresses": [],
        "hostnames": [],
        "open_ports": [],
        "services": [],
        "os": None
    }
    
    # Status
    status = host_elem.find('status')
    if status is not None:
        host_info["status"] = status.get("state", "unknown")
    
    # Addresses
    for addr in host_elem.findall('address'):
        addr_type = addr.get("addrtype")
        addr_value = addr.get("addr")
        if addr_value:
            host_info["addresses"].append({
                "type": addr_type,
                "addr": addr_value
            })
            if addr_type == "ipv4":
                host_info["ip"] = addr_value
    
    # Hostnames
    hostnames = host_elem.find('hostnames')
    if hostnames is not None:
        for hostname in hostnames.findall('hostname'):
            name = hostname.get("name")
            if name:
                host_info["hostnames"].append(name)
    
    # Ports
    ports = host_elem.find('ports')
    if ports is not None:
        for port in ports.findall('port'):
            port_info = _parse_port(port)
            if port_info:
                if port_info.get("state") == "open":
                    host_info["open_ports"].append(port_info["port"])
                host_info["services"].append(port_info)
    
    # OS detection
    os_elem = host_elem.find('os')
    if os_elem is not None:
        osmatch = os_elem.find('osmatch')
        if osmatch is not None:
            host_info["os"] = {
                "name": osmatch.get("name"),
                "accuracy": osmatch.get("accuracy")
            }
    
    return host_info


def _parse_port(port_elem: ET.Element) -> Dict[str, Any]:
    """Parse a single port element.
    
    Args:
        port_elem: XML port element
        
    Returns:
        Port information dictionary
    """
    port_info = {
        "port": int(port_elem.get("portid", 0)),
        "protocol": port_elem.get("protocol", "tcp"),
        "state": "unknown",
        "service": None
    }
    
    # State
    state = port_elem.find('state')
    if state is not None:
        port_info["state"] = state.get("state", "unknown")
        port_info["reason"] = state.get("reason")
    
    # Service
    service = port_elem.find('service')
    if service is not None:
        port_info["service"] = {
            "name": service.get("name"),
            "product": service.get("product"),
            "version": service.get("version"),
            "extrainfo": service.get("extrainfo"),
            "tunnel": service.get("tunnel"),
            "method": service.get("method")
        }
    
    # Scripts
    scripts = port_elem.findall('script')
    if scripts:
        port_info["scripts"] = []
        for script in scripts:
            port_info["scripts"].append({
                "id": script.get("id"),
                "output": script.get("output")
            })
    
    return port_info


# Fallback to python-nmap if subprocess fails
def execute_with_python_nmap(target: str, 
                            ports: Optional[str] = None,
                            options: Optional[str] = None) -> Dict[str, Any]:
    """Fallback execution using python-nmap library.
    
    Args:
        target: IP address or hostname to scan
        ports: Port range or specific ports
        options: Additional nmap options
        
    Returns:
        Scan results as dictionary
    """
    try:
        import nmap
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
            "hosts": []
        }
        
        for host in nm.all_hosts():
            host_info = {
                "ip": host,
                "hostname": nm[host].hostname(),
                "status": nm[host].state(),
                "open_ports": [],
                "services": []
            }
            
            for proto in nm[host].all_protocols():
                for port in nm[host][proto].keys():
                    port_data = nm[host][proto][port]
                    service_info = {
                        "port": port,
                        "protocol": proto,
                        "state": port_data['state'],
                        "service": {
                            "name": port_data.get('name', ''),
                            "product": port_data.get('product', ''),
                            "version": port_data.get('version', ''),
                            "extrainfo": port_data.get('extrainfo', '')
                        }
                    }
                    host_info["services"].append(service_info)
                    if port_data['state'] == 'open':
                        host_info["open_ports"].append(port)
            
            results["hosts"].append(host_info)
        
        results["scan_info"] = {
            "scanstats": nm.scanstats(),
            "command_line": nm.command_line()
        }
        
        return {
            "success": True,
            "results": results,
            "raw_output": json.dumps(results, indent=2)
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "python-nmap library not installed",
            "results": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": None
        }
