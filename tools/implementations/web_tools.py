"""Web security tools with subprocess streaming.

Implements ssl_cert_scan, http_header_analysis, directory_bruteforce.
"""

from typing import Dict, Any, Optional, Callable, List
import re
import json
from tools.implementations.cli_executor import (
    run_cli_command,
    check_tool_installed
)


def ssl_cert_scan(host: str,
                 port: int = 443,
                 stream_callback: Optional[Callable[[str], None]] = None,
                 timeout: int = 120) -> Dict[str, Any]:
    """Perform SSL/TLS certificate analysis.
    
    Args:
        host: Target hostname or IP
        port: Port number (default: 443)
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        SSL certificate scan results
    """
    target = host  # For internal use
    if stream_callback:
        stream_callback(f"SSL/TLS Analysis for {target}:{port}")
    
    results = {
        "target": target,
        "port": port,
        "certificate": {},
        "protocols": [],
        "ciphers": [],
        "vulnerabilities": []
    }
    
    all_output = []
    
    # Method 1: Use sslyze if available (preferred)
    if check_tool_installed("sslyze"):
        cmd = ["sslyze", "--regular", f"{target}:{port}"]
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            all_output.append(raw_output)
            parsed = _parse_sslyze_output(raw_output)
            results.update(parsed)
            
            return {
                "success": True,
                "results": results,
                "raw_output": raw_output
            }
    
    # Method 2: Use openssl s_client
    if check_tool_installed("openssl"):
        # Get certificate info
        cmd = f"echo | openssl s_client -connect {target}:{port} -servername {target} 2>/dev/null | openssl x509 -noout -text"
        result = run_cli_command(cmd, timeout=60, stream_callback=stream_callback, shell=True)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            all_output.append(raw_output)
            cert_info = _parse_openssl_cert(raw_output)
            results["certificate"] = cert_info
        
        # Check supported protocols
        protocols = ["ssl3", "tls1", "tls1_1", "tls1_2", "tls1_3"]
        for proto in protocols:
            cmd = f"echo | openssl s_client -connect {target}:{port} -{proto} 2>&1"
            proto_result = run_cli_command(cmd, timeout=10, shell=True)
            
            if proto_result.get("success") and "CONNECTED" in proto_result.get("raw_output", ""):
                results["protocols"].append(proto.upper().replace("_", "."))
                if stream_callback:
                    stream_callback(f"  ✓ {proto.upper().replace('_', '.')} supported")
            elif proto in ["ssl3", "tls1", "tls1_1"]:
                # Old protocols not supported is good
                if stream_callback:
                    stream_callback(f"  ✗ {proto.upper().replace('_', '.')} not supported (good)")
        
        return {
            "success": True,
            "results": results,
            "raw_output": "\n".join(all_output)
        }
    
    # Method 3: Use nmap ssl scripts
    if check_tool_installed("nmap"):
        cmd = ["nmap", "-p", str(port), "--script", "ssl-cert,ssl-enum-ciphers", target]
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            return {
                "success": True,
                "results": results,
                "raw_output": raw_output
            }
    
    return {
        "success": False,
        "error": "No SSL tools found. Install sslyze, openssl, or nmap.",
        "results": None
    }


def http_header_analysis(url: str,
                        follow_redirects: bool = True,
                        stream_callback: Optional[Callable[[str], None]] = None,
                        timeout: int = 30) -> Dict[str, Any]:
    """Analyze HTTP headers for security issues.
    
    Args:
        url: Target URL
        follow_redirects: Follow redirects
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        HTTP header analysis results
    """
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
    if stream_callback:
        stream_callback(f"🔍 HTTP Header Analysis for {url}")
    
    if not check_tool_installed("curl"):
        return {
            "success": False,
            "error": "curl not found. Install with: apt install curl",
            "results": None
        }
    
    # Build curl command
    cmd = ["curl", "-I", "-s", "--max-time", str(timeout)]
    if follow_redirects:
        cmd.append("-L")
    cmd.append(url)
    
    result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
    
    if not result.get("success"):
        return result
    
    raw_output = result.get("raw_output", "")
    
    # Parse headers
    headers = _parse_http_headers(raw_output)
    
    # Security analysis
    security_issues = []
    security_headers = {
        "Strict-Transport-Security": "HSTS not set - vulnerable to downgrade attacks",
        "X-Content-Type-Options": "X-Content-Type-Options not set - MIME sniffing possible",
        "X-Frame-Options": "X-Frame-Options not set - clickjacking possible",
        "X-XSS-Protection": "X-XSS-Protection not set",
        "Content-Security-Policy": "CSP not set - XSS mitigation missing",
        "Referrer-Policy": "Referrer-Policy not set"
    }
    
    present_headers = []
    missing_headers = []
    
    for header, issue in security_headers.items():
        if header.lower() in [h.lower() for h in headers.keys()]:
            present_headers.append(header)
        else:
            missing_headers.append(header)
            security_issues.append(issue)
    
    # Check for dangerous headers
    if "Server" in headers:
        security_issues.append(f"Server header exposes version: {headers['Server']}")
    if "X-Powered-By" in headers:
        security_issues.append(f"X-Powered-By header exposes technology: {headers['X-Powered-By']}")
    
    if stream_callback:
        stream_callback(f"📊 Found {len(present_headers)} security headers, {len(missing_headers)} missing")
    
    return {
        "success": True,
        "results": {
            "url": url,
            "headers": headers,
            "security_headers_present": present_headers,
            "security_headers_missing": missing_headers,
            "security_issues": security_issues,
            "score": len(present_headers) / len(security_headers) * 100
        },
        "raw_output": raw_output
    }


def directory_bruteforce(url: str,
                        wordlist: Optional[str] = None,
                        extensions: Optional[List[str]] = None,
                        threads: int = 10,
                        stream_callback: Optional[Callable[[str], None]] = None,
                        timeout: int = 600) -> Dict[str, Any]:
    """Perform directory brute forcing.
    
    Args:
        url: Target URL
        wordlist: Path to wordlist file
        extensions: File extensions to check
        threads: Number of threads
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        Directory brute force results
    """
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
    if stream_callback:
        stream_callback(f"🔍 Directory Brute Force on {url}")
    
    # Default wordlist locations
    default_wordlists = [
        "/usr/share/wordlists/dirb/common.txt",
        "/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt",
        "/usr/share/seclists/Discovery/Web-Content/common.txt",
        "/opt/wordlists/common.txt"
    ]
    
    if not wordlist:
        import os
        for wl in default_wordlists:
            if os.path.exists(wl):
                wordlist = wl
                break
    
    # Try gobuster first
    if check_tool_installed("gobuster"):
        cmd = ["gobuster", "dir", "-u", url, "-t", str(threads), "-q"]
        if wordlist:
            cmd.extend(["-w", wordlist])
        else:
            return {
                "success": False,
                "error": "No wordlist found. Please specify a wordlist.",
                "results": None
            }
        
        if extensions:
            cmd.extend(["-x", ",".join(extensions)])
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            found_paths = _parse_gobuster_output(result.get("raw_output", ""))
            return {
                "success": True,
                "results": {
                    "url": url,
                    "tool": "gobuster",
                    "wordlist": wordlist,
                    "found_paths": found_paths,
                    "count": len(found_paths)
                },
                "raw_output": result.get("raw_output", "")
            }
    
    # Try dirb
    if check_tool_installed("dirb"):
        cmd = ["dirb", url]
        if wordlist:
            cmd.append(wordlist)
        cmd.extend(["-S", "-r"])  # Silent, no recursion
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            found_paths = _parse_dirb_output(result.get("raw_output", ""))
            return {
                "success": True,
                "results": {
                    "url": url,
                    "tool": "dirb",
                    "wordlist": wordlist,
                    "found_paths": found_paths,
                    "count": len(found_paths)
                },
                "raw_output": result.get("raw_output", "")
            }
    
    # Try ffuf
    if check_tool_installed("ffuf"):
        if not wordlist:
            return {
                "success": False,
                "error": "No wordlist found. Please specify a wordlist.",
                "results": None
            }
        
        cmd = ["ffuf", "-u", f"{url}/FUZZ", "-w", wordlist, "-t", str(threads), "-s"]
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            found_paths = [line.strip() for line in result.get("raw_output", "").split("\n") if line.strip()]
            return {
                "success": True,
                "results": {
                    "url": url,
                    "tool": "ffuf",
                    "wordlist": wordlist,
                    "found_paths": found_paths,
                    "count": len(found_paths)
                },
                "raw_output": result.get("raw_output", "")
            }
    
    return {
        "success": False,
        "error": "No directory brute force tools found. Install gobuster, dirb, or ffuf.",
        "results": None
    }


def _parse_sslyze_output(output: str) -> Dict[str, Any]:
    """Parse sslyze output."""
    result = {
        "protocols": [],
        "ciphers": [],
        "vulnerabilities": []
    }
    
    # Extract protocols
    if "TLSv1.3" in output:
        result["protocols"].append("TLSv1.3")
    if "TLSv1.2" in output:
        result["protocols"].append("TLSv1.2")
    if "TLSv1.1" in output:
        result["protocols"].append("TLSv1.1")
    if "TLSv1.0" in output:
        result["protocols"].append("TLSv1.0")
    if "SSLv3" in output:
        result["protocols"].append("SSLv3")
        result["vulnerabilities"].append("SSLv3 supported - POODLE vulnerable")
    
    # Check for vulnerabilities
    if "VULNERABLE" in output:
        if "heartbleed" in output.lower():
            result["vulnerabilities"].append("Heartbleed")
        if "robot" in output.lower():
            result["vulnerabilities"].append("ROBOT")
        if "crime" in output.lower():
            result["vulnerabilities"].append("CRIME")
    
    return result


def _parse_openssl_cert(output: str) -> Dict[str, str]:
    """Parse openssl x509 output."""
    cert_info = {}
    
    # Extract common fields
    patterns = {
        "subject": r"Subject:\s*(.+)",
        "issuer": r"Issuer:\s*(.+)",
        "not_before": r"Not Before:\s*(.+)",
        "not_after": r"Not After\s*:\s*(.+)",
        "serial": r"Serial Number:\s*\n?\s*(.+)",
        "signature_algorithm": r"Signature Algorithm:\s*(.+)"
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            cert_info[key] = match.group(1).strip()
    
    # Extract SANs
    san_match = re.search(r"Subject Alternative Name:\s*\n\s*(.+)", output)
    if san_match:
        cert_info["san"] = san_match.group(1).strip()
    
    return cert_info


def _parse_http_headers(output: str) -> Dict[str, str]:
    """Parse HTTP headers from curl output."""
    headers = {}
    
    for line in output.split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("HTTP/"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                headers[parts[0].strip()] = parts[1].strip()
    
    return headers


def _parse_gobuster_output(output: str) -> List[Dict[str, Any]]:
    """Parse gobuster output."""
    results = []
    
    for line in output.split("\n"):
        line = line.strip()
        if line and not line.startswith("="):
            # gobuster format: /path (Status: 200) [Size: 1234]
            match = re.search(r'(/\S+)\s+\(Status:\s*(\d+)\)', line)
            if match:
                results.append({
                    "path": match.group(1),
                    "status": int(match.group(2))
                })
    
    return results


def _parse_dirb_output(output: str) -> List[Dict[str, Any]]:
    """Parse dirb output."""
    results = []
    
    for line in output.split("\n"):
        line = line.strip()
        # dirb format: + http://example.com/path (CODE:200|SIZE:1234)
        match = re.search(r'\+\s+(https?://\S+)\s+\(CODE:(\d+)', line)
        if match:
            results.append({
                "path": match.group(1),
                "status": int(match.group(2))
            })
    
    return results
