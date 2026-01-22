"""Vulnerability testing tools with subprocess streaming.

Implements sql_injection_test, xss_test, vulnerability_scanner.
"""

from typing import Dict, Any, Optional, Callable, List
import re
from tools.implementations.cli_executor import (
    run_cli_command,
    check_tool_installed
)


def sql_injection_test(url: str,
                      parameter: Optional[str] = None,
                      data: Optional[str] = None,
                      method: str = "GET",
                      level: int = 1,
                      risk: int = 1,
                      stream_callback: Optional[Callable[[str], None]] = None,
                      timeout: int = 600) -> Dict[str, Any]:
    """Test for SQL injection vulnerabilities using sqlmap.
    
    Args:
        url: Target URL
        parameter: Specific parameter to test (optional, sqlmap auto-detects if not provided)
        data: POST data (for POST requests)
        method: HTTP method (GET/POST)
        level: Testing level (1-5)
        risk: Risk level (1-3)
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        SQL injection test results
    """
    if not check_tool_installed("sqlmap"):
        return {
            "success": False,
            "error": "sqlmap not found. Install with: apt install sqlmap",
            "results": None
        }
    
    if stream_callback:
        stream_callback(f"SQL Injection Testing on {url}")
    
    # Build sqlmap command
    cmd = [
        "sqlmap",
        "-u", url,
        "--batch",  # Non-interactive mode
        "--level", str(level),
        "--risk", str(risk),
        "--output-dir=/tmp/sqlmap"
    ]
    
    # Add specific parameter to test
    if parameter:
        cmd.extend(["-p", parameter])
    
    if data:
        cmd.extend(["--data", data])
        cmd.extend(["--method", "POST"])
    
    result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
    
    raw_output = result.get("raw_output", "")
    
    # Parse sqlmap output
    vulnerabilities = _parse_sqlmap_output(raw_output)
    
    is_vulnerable = len(vulnerabilities) > 0 or "is vulnerable" in raw_output.lower()
    
    return {
        "success": True,
        "results": {
            "url": url,
            "method": method,
            "is_vulnerable": is_vulnerable,
            "vulnerabilities": vulnerabilities,
            "injection_types": _extract_injection_types(raw_output)
        },
        "raw_output": raw_output
    }


def xss_test(url: str,
            parameter: Optional[str] = None,
            data: Optional[str] = None,
            stream_callback: Optional[Callable[[str], None]] = None,
            timeout: int = 300) -> Dict[str, Any]:
    """Test for XSS vulnerabilities using dalfox or xsstrike.
    
    Args:
        url: Target URL
        parameter: Specific parameter to test
        data: POST data
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        XSS test results
    """
    if stream_callback:
        stream_callback(f"XSS Testing on {url}")
    
    # Try dalfox first
    if check_tool_installed("dalfox"):
        cmd = ["dalfox", "url", url, "--silence", "--no-color"]
        if parameter:
            cmd.extend(["--param", parameter])
        if data:
            cmd.extend(["--data", data])
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            vulnerabilities = _parse_dalfox_output(raw_output)
            
            return {
                "success": True,
                "results": {
                    "url": url,
                    "tool": "dalfox",
                    "is_vulnerable": len(vulnerabilities) > 0,
                    "vulnerabilities": vulnerabilities
                },
                "raw_output": raw_output
            }
    
    # Try xsstrike
    if check_tool_installed("xsstrike"):
        cmd = ["xsstrike", "-u", url, "--skip"]
        if data:
            cmd.extend(["--data", data])
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            is_vulnerable = "vulnerable" in raw_output.lower()
            
            return {
                "success": True,
                "results": {
                    "url": url,
                    "tool": "xsstrike",
                    "is_vulnerable": is_vulnerable,
                    "vulnerabilities": []
                },
                "raw_output": raw_output
            }
    
    # Fallback: manual testing with curl
    if check_tool_installed("curl"):
        test_payloads = [
            "<script>alert(1)</script>",
            "'\"><script>alert(1)</script>",
            "<img src=x onerror=alert(1)>"
        ]
        
        results = []
        for payload in test_payloads:
            test_url = f"{url}{payload}" if "?" in url else f"{url}?test={payload}"
            cmd = ["curl", "-s", "-i", test_url]
            result = run_cli_command(cmd, timeout=30, stream_callback=stream_callback)
            
            if result.get("success"):
                response = result.get("raw_output", "")
                # Check if payload is reflected
                if payload in response:
                    results.append({
                        "payload": payload,
                        "reflected": True
                    })
        
        return {
            "success": True,
            "results": {
                "url": url,
                "tool": "curl (manual)",
                "is_vulnerable": len(results) > 0,
                "vulnerabilities": results
            },
            "raw_output": ""
        }
    
    return {
        "success": False,
        "error": "No XSS testing tools found. Install dalfox or xsstrike.",
        "results": None
    }


def vulnerability_scanner(target: str,
                         scan_type: str = "basic",
                         stream_callback: Optional[Callable[[str], None]] = None,
                         timeout: int = 1200) -> Dict[str, Any]:
    """Perform vulnerability scanning using nikto, nuclei, or nmap scripts.
    
    Args:
        target: Target URL or host
        scan_type: Scan type (basic, full, web)
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        Vulnerability scan results
    """
    if stream_callback:
        stream_callback(f"🔍 Vulnerability Scanning on {target}")
    
    results = {
        "target": target,
        "scan_type": scan_type,
        "vulnerabilities": [],
        "findings": []
    }
    
    all_output = []
    
    # Try nuclei first (modern, fast)
    if check_tool_installed("nuclei"):
        cmd = ["nuclei", "-u", target, "-silent", "-nc"]
        if scan_type == "basic":
            cmd.extend(["-severity", "critical,high"])
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            all_output.append(raw_output)
            vulns = _parse_nuclei_output(raw_output)
            results["vulnerabilities"].extend(vulns)
            results["tool_used"] = "nuclei"
    
    # Try nikto for web scanning
    if scan_type in ["web", "full"] and check_tool_installed("nikto"):
        url = target if target.startswith(("http://", "https://")) else f"https://{target}"
        cmd = ["nikto", "-h", url, "-nointeractive"]
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            all_output.append(raw_output)
            findings = _parse_nikto_output(raw_output)
            results["findings"].extend(findings)
            results["tool_used"] = results.get("tool_used", "") + ",nikto"
    
    # Try nmap vuln scripts
    if check_tool_installed("nmap") and not results["vulnerabilities"]:
        # Extract host from URL if needed
        host = target
        if target.startswith(("http://", "https://")):
            host = target.split("//")[1].split("/")[0].split(":")[0]
        
        cmd = ["nmap", "-sV", "--script", "vuln", host]
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            all_output.append(raw_output)
            vulns = _parse_nmap_vuln_output(raw_output)
            results["vulnerabilities"].extend(vulns)
            results["tool_used"] = results.get("tool_used", "") + ",nmap"
    
    if not results["vulnerabilities"] and not results["findings"]:
        if not any([check_tool_installed(t) for t in ["nuclei", "nikto", "nmap"]]):
            return {
                "success": False,
                "error": "No vulnerability scanners found. Install nuclei, nikto, or nmap.",
                "results": None
            }
    
    return {
        "success": True,
        "results": results,
        "raw_output": "\n\n".join(all_output)
    }


def _parse_sqlmap_output(output: str) -> List[Dict[str, Any]]:
    """Parse sqlmap output for vulnerabilities."""
    vulnerabilities = []
    
    # Look for vulnerability indicators
    patterns = [
        r"Parameter: (.+?) \((.+?)\)",  # Parameter and type
        r"Type: (.+)",  # Injection type
        r"Title: (.+)",  # Vulnerability title
        r"Payload: (.+)"  # Payload used
    ]
    
    current_vuln = {}
    for line in output.split("\n"):
        line = line.strip()
        
        if "is vulnerable" in line.lower():
            if current_vuln:
                vulnerabilities.append(current_vuln)
            current_vuln = {"description": line}
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                if "Parameter" in pattern:
                    current_vuln["parameter"] = match.group(1)
                    current_vuln["location"] = match.group(2)
                elif "Type" in pattern:
                    current_vuln["type"] = match.group(1)
                elif "Title" in pattern:
                    current_vuln["title"] = match.group(1)
                elif "Payload" in pattern:
                    current_vuln["payload"] = match.group(1)
    
    if current_vuln:
        vulnerabilities.append(current_vuln)
    
    return vulnerabilities


def _extract_injection_types(output: str) -> List[str]:
    """Extract SQL injection types from sqlmap output."""
    types = []
    
    injection_types = [
        "boolean-based blind",
        "time-based blind",
        "error-based",
        "UNION query",
        "stacked queries"
    ]
    
    for inj_type in injection_types:
        if inj_type.lower() in output.lower():
            types.append(inj_type)
    
    return types


def _parse_dalfox_output(output: str) -> List[Dict[str, Any]]:
    """Parse dalfox output for XSS vulnerabilities."""
    vulnerabilities = []
    
    for line in output.split("\n"):
        line = line.strip()
        if "[POC]" in line or "[V]" in line:
            vulnerabilities.append({
                "type": "XSS",
                "details": line
            })
    
    return vulnerabilities


def _parse_nuclei_output(output: str) -> List[Dict[str, Any]]:
    """Parse nuclei output for vulnerabilities."""
    vulnerabilities = []
    
    for line in output.split("\n"):
        line = line.strip()
        if line and not line.startswith("["):
            continue
        
        # nuclei format: [severity] [template-id] [protocol] target
        match = re.search(r'\[(\w+)\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s+(.+)', line)
        if match:
            vulnerabilities.append({
                "severity": match.group(1),
                "template": match.group(2),
                "protocol": match.group(3),
                "target": match.group(4)
            })
    
    return vulnerabilities


def _parse_nikto_output(output: str) -> List[Dict[str, Any]]:
    """Parse nikto output for findings."""
    findings = []
    
    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("+"):
            # nikto format: + OSVDB-xxxx: description
            match = re.search(r'\+\s+(OSVDB-\d+)?:?\s*(.+)', line)
            if match:
                findings.append({
                    "osvdb": match.group(1) if match.group(1) else None,
                    "description": match.group(2)
                })
    
    return findings


def _parse_nmap_vuln_output(output: str) -> List[Dict[str, Any]]:
    """Parse nmap vuln script output."""
    vulnerabilities = []
    
    # Look for CVE references
    cve_pattern = r'(CVE-\d{4}-\d+)'
    cves = re.findall(cve_pattern, output)
    
    for cve in set(cves):
        vulnerabilities.append({
            "type": "CVE",
            "id": cve,
            "source": "nmap"
        })
    
    # Look for VULNERABLE markers
    if "VULNERABLE" in output:
        vuln_sections = output.split("VULNERABLE")
        for section in vuln_sections[1:]:
            lines = section.split("\n")[:5]
            vulnerabilities.append({
                "type": "nmap_vuln",
                "details": " ".join(lines).strip()
            })
    
    return vulnerabilities
