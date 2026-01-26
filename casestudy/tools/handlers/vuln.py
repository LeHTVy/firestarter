"""
Vulnerability Scanning Tool Handlers
=====================================

Handles: vuln_scan, vuln_scan_batch, nikto_batch, nikto_scan, search_cves
"""
from typing import Dict, Any
from app.tools.handlers import register_handler


@register_handler("vuln_scan")
def handle_vuln_scan(action_input: Dict[str, Any], state: Any) -> str:
    """Vulnerability scan on a single host."""
    from app.core.state import get_subdomain_file
    import subprocess
    
    target = action_input.get("target", "")
    mode = action_input.get("mode", "fast").lower()
    
    # Track scanned hosts
    if "scanned_hosts" not in state.context:
        state.context["scanned_hosts"] = set()
    
    if not target:
        # Priority 1: Use 200 OK hosts
        ok_hosts = state.context.get("httpx_200_hosts", [])
        if ok_hosts:
            for t in ok_hosts:
                if t not in state.context["scanned_hosts"]:
                    target = t
                    break
            if not target:
                return f"All {len(ok_hosts)} 200 OK hosts have been scanned."
        
        # Priority 2: Subdomain file
        if not target:
            subdomain_file = get_subdomain_file()
            if subdomain_file:
                with open(subdomain_file, 'r') as f:
                    all_targets = [l.strip() for l in f if l.strip()]
                for t in all_targets[:20]:
                    if t not in state.context["scanned_hosts"]:
                        target = t
                        break
                if not target:
                    return "All available hosts have been scanned."
    
    if not target:
        return "Error: No target specified and no subdomain file available."
    
    state.context["scanned_hosts"].add(target)
    output = ""
    
    # Nuclei scan
    print(f"  🔴 [NUCLEI] Scanning {target}...")
    
    from app.tools.registry import get_registry
    registry = get_registry()
    scan_result = registry.execute("nuclei", "scan_json", {"target": f"https://{target}"})
    
    output += f"═══ NUCLEI SCAN: {target} ═══\n"
    
    if not scan_result.success:
        output += f"  Error: {scan_result.error}\n"
    else:
        # Parse JSON output from nuclei
        vulnerabilities = []
        for line in scan_result.output.strip().split('\n'):
            if not line.strip():
                continue
            try:
                import json
                data = json.loads(line)
                vulnerabilities.append({
                    "template": data.get("template-id", "unknown"),
                    "name": data.get("info", {}).get("name", "Unknown"),
                    "severity": data.get("info", {}).get("severity", "unknown"),
                    "matched": data.get("matched-at", ""),
                    "description": data.get("info", {}).get("description", ""),
                })
            except (json.JSONDecodeError, AttributeError):
                continue
        
        output += f"Vulnerabilities found: {len(vulnerabilities)}\n"
        if vulnerabilities:
            for v in vulnerabilities[:5]:
                output += f"  [{v['severity'].upper()}] {v['name']}\n"
        else:
            output += "  No critical/high/medium vulnerabilities detected.\n"
    
    # Nikto for thorough mode
    if mode == "thorough":
        print(f"  🔴 [NIKTO] Deep scanning {target}...")
        output += f"\n═══ NIKTO SCAN: {target} ═══\n"
        
        try:
            nikto_result = subprocess.run(
                ["/usr/bin/nikto", "-h", f"https://{target}", "-ssl", "-timeout", "20"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if nikto_result.stdout.strip():
                findings = [l for l in nikto_result.stdout.split('\n') if l.startswith('+ ')]
                if findings:
                    output += f"Nikto findings: {len(findings)}\n"
                    for f in findings[:10]:
                        output += f"  {f}\n"
                else:
                    output += "  No significant findings from Nikto.\n"
            else:
                output += "  Nikto scan completed, no output.\n"
                
        except subprocess.TimeoutExpired:
            output += "  ⚠️ Nikto scan timed out (5 min limit).\n"
        except Exception as e:
            output += f"  ⚠️ Nikto error: {e}\n"
    else:
        output += "\n💡 Tip: Use mode='thorough' for deeper scan with Nikto.\n"
    
    return output


@register_handler("vuln_scan_batch")
def handle_vuln_scan_batch(action_input: Dict[str, Any], state: Any) -> str:
    """Batch vulnerability scan on multiple hosts."""
    from app.core.state import get_subdomain_file
    from pathlib import Path
    import subprocess
    import tempfile
    
    max_hosts = int(action_input.get("max_hosts", 10))
    mode = action_input.get("mode", "normal").lower()
    
    # Get targets
    targets = []
    ok_hosts = state.context.get("httpx_200_hosts", [])
    if ok_hosts:
        targets = ok_hosts[:max_hosts]
    else:
        subdomain_file = get_subdomain_file()
        if subdomain_file:
            with open(subdomain_file, 'r') as f:
                targets = [l.strip() for l in f if l.strip()][:max_hosts]
    
    if not targets:
        return "No targets available. Run httpx_batch first to identify live hosts."
    
    if mode == "fast":
        print(f"  ⚡ FAST scanning {len(targets)} hosts (critical only, optimized)...")
        severity = "critical,high"
        timeout = 240
    else:
        print(f"  🔴 Batch scanning {len(targets)} hosts with Nuclei...")
        severity = "critical,high,medium"
        timeout = 480
    
    # Write targets to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
        for t in targets:
            if not t.startswith("http"):
                t = f"https://{t}"
            tmp.write(f"{t}\n")
        tmp_path = tmp.name
    
    try:
        cmd = [
            "/home/hellrazor/go/bin/nuclei",
            "-l", tmp_path,
            "-severity", severity,
            "-silent",
            "-rl", "100",
            "-bs", "10",
            "-timeout", "5",
            "-retries", "0",
            "-c", "15",
        ]
        
        if mode == "fast":
            cmd.extend(["-rl", "150", "-bs", "15", "-nt"])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        Path(tmp_path).unlink(missing_ok=True)
        
        output = f"═══ BATCH NUCLEI SCAN: {len(targets)} hosts ═══\n"
        
        if result.stdout.strip():
            vulns = result.stdout.strip().split('\n')
            output += f"🚨 VULNERABILITIES FOUND: {len(vulns)}\n\n"
            for v in vulns[:20]:
                output += f"  {v}\n"
            if len(vulns) > 20:
                output += f"\n  ... and {len(vulns) - 20} more\n"
            state.context["nuclei_findings"] = vulns
        else:
            output += "No critical/high/medium vulnerabilities found.\n"
            output += f"Scanned hosts: {', '.join(targets[:5])}"
            if len(targets) > 5:
                output += f" and {len(targets) - 5} more"
        
        return output
        
    except subprocess.TimeoutExpired:
        Path(tmp_path).unlink(missing_ok=True)
        return f"Batch scan timed out ({timeout//60} min limit)"
    except FileNotFoundError:
        Path(tmp_path).unlink(missing_ok=True)
        return "⚠️ TOOL NOT INSTALLED: 'nuclei' not found"


@register_handler("nikto_batch")
def handle_nikto_batch(action_input: Dict[str, Any], state: Any) -> str:
    """Nikto batch scan - alternative to Nuclei."""
    from app.core.state import get_subdomain_file
    import subprocess
    
    max_hosts = int(action_input.get("max_hosts", 5))
    
    # Get targets
    targets = []
    ok_hosts = state.context.get("httpx_200_hosts", [])
    if ok_hosts:
        targets = ok_hosts[:max_hosts]
    else:
        subdomain_file = get_subdomain_file()
        if subdomain_file:
            with open(subdomain_file, 'r') as f:
                targets = [l.strip() for l in f if l.strip()][:max_hosts]
    
    if not targets:
        return "No targets available. Run httpx_batch first to identify live hosts."
    
    print(f"  🔍 Nikto scanning {len(targets)} hosts (this may take a while)...")
    
    results = []
    
    for target in targets:
        host = target.replace("https://", "").replace("http://", "").split("/")[0]
        print(f"    → Scanning {host}...")
        
        try:
            result = subprocess.run(
                ["/usr/bin/nikto", "-h", f"https://{host}", "-ssl", "-timeout", "30", "-maxtime", "120"],
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.stdout:
                findings = [l for l in result.stdout.split('\n') if l.startswith('+ ')]
                if findings:
                    results.append(f"\n{host}: {len(findings)} findings")
                    for f in findings[:5]:
                        results.append(f"  {f}")
                else:
                    results.append(f"\n{host}: No significant findings")
            
        except subprocess.TimeoutExpired:
            results.append(f"\n{host}: Timed out (3 min limit)")
        except Exception as e:
            results.append(f"\n{host}: Error - {e}")
    
    output = f"═══ NIKTO BATCH SCAN: {len(targets)} hosts ═══\n"
    output += "\n".join(results)
    
    return output


@register_handler("search_cves")
def handle_search_cves(action_input: Dict[str, Any], state: Any) -> str:
    """Search CVE database."""
    query = action_input.get("query", state.query)
    
    print(f"  📚 Searching CVEs for: {query}...")
    
    try:
        from app.rag.cve_rag import search_cves
        result = search_cves(query, n_results=5)
        
        cves = result.get("cves", result.get("results", []))
        
        if not cves:
            return f"No CVEs found for query: {query}"
        
        output = f"═══ CVE SEARCH: {query} ═══\n\n"
        for cve in cves:
            output += f"[{cve.get('id', 'Unknown')}] {cve.get('description', '')[:200]}...\n\n"
        
        return output
        
    except ImportError:
        return "CVE search module not available. Use: pip install chromadb"
    except Exception as e:
        return f"CVE search error: {e}"


@register_handler("nikto_scan")
def handle_nikto_scan(action_input: Dict[str, Any], state: Any) -> str:
    """Web server vulnerability scan with Nikto."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        ok_hosts = state.context.get("httpx_200_hosts", [])
        if ok_hosts:
            target = ok_hosts[0]
        else:
            return "Error: No target specified"
    
    # Clean target
    if not target.startswith("http"):
        target = f"https://{target}"
    
    print(f"  🔍 Nikto scanning {target}...")
    
    try:
        result = subprocess.run(
            ["/usr/bin/nikto",
             "-h", target,
             "-ssl",
             "-timeout", "30",
             "-maxtime", "300"],
            capture_output=True,
            text=True,
            timeout=360
        )
        
        output = f"═══ NIKTO SCAN: {target} ═══\n"
        
        if result.stdout:
            findings = [l for l in result.stdout.split('\n') if l.startswith('+ ')]
            if findings:
                output += f"Findings: {len(findings)}\n\n"
                for f in findings[:15]:
                    output += f"  {f}\n"
                if len(findings) > 15:
                    output += f"\n  ... and {len(findings) - 15} more\n"
            else:
                output += "No significant findings detected.\n"
        else:
            output += "Scan completed, no output.\n"
        
        return output
        
    except subprocess.TimeoutExpired:
        return f"Nikto scan timed out for {target} (6 min limit)"
    except Exception as e:
        return f"Nikto error: {e}"


@register_handler("sql_injection")
def handle_sql_injection(action_input: Dict[str, Any], state: Any) -> str:
    """SQL injection testing with sqlmap."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target URL specified. Example: sql_injection with {\"target\": \"http://example.com/page.php?id=1\"}"
    
    if not target.startswith("http"):
        target = f"http://{target}"
    
    level = action_input.get("level", "1")
    risk = action_input.get("risk", "1")
    
    print(f"  💉 SQLMap testing {target}...")
    
    try:
        result = subprocess.run(
            ["/usr/bin/sqlmap",
             "-u", target,
             "--batch",
             "--level", str(level),
             "--risk", str(risk),
             "--timeout", "30",
             "--retries", "1",
             "--smart"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        output_text = result.stdout + result.stderr
        
        output = f"═══ SQLMAP TEST: {target} ═══\n"
        
        # Check for vulnerabilities
        if "is vulnerable" in output_text.lower():
            output += "🚨 SQL INJECTION VULNERABILITY FOUND!\n\n"
            # Extract vulnerability details
            for line in output_text.split('\n'):
                if any(x in line.lower() for x in ['injectable', 'vulnerable', 'payload:', 'type:']):
                    output += f"  {line}\n"
            state.context["sqli_vulnerable"] = target
        elif "not injectable" in output_text.lower():
            output += "No SQL injection vulnerabilities found.\n"
        else:
            output += "Scan completed. Check results:\n"
            output += output_text[-500:]  # Last 500 chars
        
        return output
        
    except subprocess.TimeoutExpired:
        return f"SQLMap timed out for {target} (5 min limit)"
    except Exception as e:
        return f"SQLMap error: {e}"


@register_handler("searchsploit")
def handle_searchsploit(action_input: Dict[str, Any], state: Any) -> str:
    """Search ExploitDB for exploits."""
    import subprocess
    
    query = action_input.get("query", "")
    if not query:
        return "Error: No query specified. Example: searchsploit with {\"query\": \"Apache 2.4\"}"
    
    print(f"  🔎 Searching ExploitDB for: {query}...")
    
    try:
        result = subprocess.run(
            ["searchsploit", query, "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = f"═══ EXPLOITDB SEARCH: {query} ═══\n"
        
        if result.stdout:
            import json
            try:
                data = json.loads(result.stdout)
                exploits = data.get("RESULTS_EXPLOIT", [])
                
                if exploits:
                    output += f"Found {len(exploits)} exploits:\n\n"
                    for e in exploits[:10]:
                        output += f"  [{e.get('Type', 'N/A')}] {e.get('Title', 'Unknown')}\n"
                        output += f"       Path: {e.get('Path', 'N/A')}\n\n"
                else:
                    output += "No exploits found.\n"
            except json.JSONDecodeError:
                # Fallback to text output
                output += result.stdout[:1000]
        else:
            output += "No results found.\n"
        
        return output
        
    except subprocess.TimeoutExpired:
        return f"Searchsploit timed out for {query}"
    except FileNotFoundError:
        return "⚠️ searchsploit not installed. Use: sudo apt install exploitdb"
    except Exception as e:
        return f"Searchsploit error: {e}"

