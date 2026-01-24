"""
Recon Tool Handlers
===================

Handles: subdomain_enum, port_scan, port_scan_file, quick_scan, whois, dns_lookup
"""
from typing import Dict, Any
from app.tools.handlers import register_handler


@register_handler("subdomain_enum")
def handle_subdomain_enum(action_input: Dict[str, Any], state: Any) -> str:
    """Enumerate subdomains for a domain."""
    from app.tools.registry import get_registry
    from app.core.state import save_subdomains
    
    domain = action_input.get("domain", state.context.get("last_domain", ""))
    if not domain:
        return "Error: No domain specified"
    
    print(f"  🔍 Enumerating subdomains for {domain}...")
    
    registry = get_registry()
    all_subs = set()
    
    # Use Subfinder - faster and more reliable
    try:
        print("    Running subfinder...")
        result = registry.execute("subfinder", "enum", {"domain": domain})
        if result.success:
            # Parse subdomains from output (one per line)
            subdomains = [
                line.strip().lower()
                for line in result.output.split('\n')
                if line.strip() and '.' in line and domain in line.lower()
            ]
            all_subs.update(subdomains)
            print(f"    Subfinder found {len(subdomains)} subdomains")
        else:
            print(f"    Subfinder error: {result.error}")
    except Exception as e:
        print(f"    Subfinder error: {e}")
    
    # Only run BBOT if subfinder found < 10
    if len(all_subs) < 10:
        try:
            print("    Running bbot (subfinder found few results)...")
            result = registry.execute("bbot", "subdomains", {"domain": domain})
            if result.success:
                # Parse subdomains from output
                subdomains = [
                    line.strip().lower()
                    for line in result.output.split('\n')
                    if line.strip() and '.' in line and domain in line.lower()
                ]
                all_subs.update(subdomains)
                print(f"    BBOT found {len(subdomains)} additional subdomains")
            else:
                print(f"    BBOT error: {result.error}")
        except Exception as e:
            print(f"    BBOT error: {e}")
    
    if all_subs:
        save_subdomains(list(all_subs), domain)
        state.context["last_domain"] = domain
        state.context["has_subdomains"] = True
    
    return f"Found {len(all_subs)} subdomains for {domain}. Top 10: {', '.join(list(all_subs)[:10])}"


@register_handler("port_scan")
def handle_port_scan(action_input: Dict[str, Any], state: Any) -> str:
    """Port scan discovered subdomains."""
    from app.tools.registry import get_registry
    from app.core.state import get_subdomain_file
    
    subdomain_file = get_subdomain_file()
    if not subdomain_file:
        return "Error: No subdomain file found. Run subdomain_enum first."
    
    with open(subdomain_file, 'r') as f:
        all_targets = [l.strip() for l in f if l.strip()]
    
    MAX_TARGETS = 200
    if len(all_targets) > MAX_TARGETS:
        print(f"  ⚠️ {len(all_targets)} targets too many, limiting to first {MAX_TARGETS}")
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        temp_file.write('\n'.join(all_targets[:MAX_TARGETS]))
        temp_file.close()
        scan_file = temp_file.name
        target_count = MAX_TARGETS
    else:
        scan_file = str(subdomain_file)
        target_count = len(all_targets)
    
    print(f"  🔌 Port scanning {target_count} targets...")
    
    registry = get_registry()
    ports = action_input.get("ports", "22,80,443,8080,8443")
    result = registry.execute("nmap", "from_file", {"file": scan_file, "ports": ports})
    
    if not result.success:
        return f"Error: {result.error}"
    
    # Parse nmap output to extract open ports per host
    open_ports = {}
    for line in result.output.split('\n'):
        if 'Ports:' in line and 'Host:' in line:
            parts = line.split('Ports:')
            if len(parts) >= 2:
                host = parts[0].replace('Host:', '').strip().split()[0]
                ports_str = parts[1].strip()
                
                port_list = []
                for port_info in ports_str.split(','):
                    if '/open/' in port_info:
                        p = int(port_info.split('/')[0].strip())
                        port_list.append(p)
                
                if port_list:
                    open_ports[host] = port_list
    
    state.context["has_ports"] = True
    state.context["port_scan_results"] = open_ports
    
    output = f"Scanned targets, {len(open_ports)} hosts have open ports.\n"
    for host, ports_list in list(open_ports.items())[:10]:
        output += f"  {host}: {', '.join(map(str, ports_list))}\n"
    if len(open_ports) > 10:
        output += f"  ... and {len(open_ports) - 10} more hosts\n"
    
    return output


@register_handler("quick_scan")
def handle_quick_scan(action_input: Dict[str, Any], state: Any) -> str:
    """Quick port scan on a single target."""
    from app.tools.registry import get_registry
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target specified"
    
    print(f"  🔌 Quick scanning {target}...")
    
    registry = get_registry()
    result = registry.execute("nmap", "quick_scan", {"target": target})
    
    if not result.success:
        return f"Error: {result.error}"
    
    # Parse nmap output to extract open ports
    open_ports = []
    for line in result.output.split('\n'):
        if 'Ports:' in line:
            parts_str = line.split('Ports:')[1].strip()
            for port_str in parts_str.split(','):
                parts = port_str.strip().split('/')
                if len(parts) >= 5 and parts[1] == 'open':
                    open_ports.append({
                        "port": int(parts[0]),
                        "protocol": parts[2],
                        "service": parts[4] if parts[4] else "unknown"
                    })
    
    output = f"Target: {target}\n"
    for port in open_ports:
        output += f"  {port['port']}/{port['protocol']}: {port.get('service', 'unknown')}\n"
    
    return output


@register_handler("whois")
def handle_whois(action_input: Dict[str, Any], state: Any) -> str:
    """WHOIS lookup for domain."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target specified"
    
    print(f"  📋 WHOIS lookup for {target}...")
    
    try:
        result = subprocess.run(
            ["whois", target],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout[:2000] if result.stdout else "No WHOIS data found"
        return f"WHOIS for {target}:\n{output}"
    except subprocess.TimeoutExpired:
        return f"WHOIS lookup timed out for {target}"
    except Exception as e:
        return f"WHOIS error: {e}"


@register_handler("dns_lookup")
def handle_dns_lookup(action_input: Dict[str, Any], state: Any) -> str:
    """DNS record lookup."""
    import subprocess
    
    domain = action_input.get("domain", "")
    if not domain:
        return "Error: No domain specified"
    
    print(f"  🌐 DNS lookup for {domain}...")
    
    try:
        result = subprocess.run(
            ["dig", "+short", domain, "ANY"],
            capture_output=True,
            text=True,
            timeout=30
        )
        records = result.stdout.strip() if result.stdout else "No records found"
        return f"DNS records for {domain}:\n{records}"
    except subprocess.TimeoutExpired:
        return f"DNS lookup timed out for {domain}"
    except Exception as e:
        return f"DNS error: {e}"


@register_handler("nmap_deep")
def handle_nmap_deep(action_input: Dict[str, Any], state: Any) -> str:
    """Deep nmap scan with service detection."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target specified. Example: nmap_deep with {\"target\": \"192.168.1.1\"}"
    
    ports = action_input.get("ports", "")
    
    print(f"  🔬 Deep scanning {target} with service detection...")
    
    # Build nmap command
    cmd = ["nmap", "-sV", "-sC", "-O", "--top-ports", "1000", target]
    
    if ports == "all":
        cmd = ["nmap", "-sV", "-sC", "-p-", target]
        print(f"  ⚠️ Scanning ALL 65535 ports (this may take a while)...")
    elif ports:
        cmd = ["nmap", "-sV", "-sC", "-p", ports, target]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        output = f"═══ DEEP NMAP SCAN: {target} ═══\n\n"
        
        if result.stdout:
            lines = result.stdout.split('\n')
            for line in lines:
                if any(x in line for x in ['PORT', '/tcp', '/udp', 'open', 'Service', 'OS:', 'Running:']):
                    output += line + "\n"
            
            state.context["nmap_deep_results"] = {
                "target": target,
                "raw_output": result.stdout[:5000]
            }
        else:
            output += "No ports found or scan failed.\n"
            if result.stderr:
                output += f"Stderr: {result.stderr[:500]}\n"
        
        return output
        
    except subprocess.TimeoutExpired:
        return f"Deep scan timed out for {target} (10 min limit). Try scanning specific ports."
    except Exception as e:
        return f"Nmap error: {e}"


@register_handler("masscan")
def handle_masscan(action_input: Dict[str, Any], state: Any) -> str:
    """Ultra-fast port scanner for large ranges."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target specified"
    
    ports = action_input.get("ports", "80,443,8080,8443")
    rate = action_input.get("rate", "1000")
    
    print(f"  ⚡ Masscan scanning {target} (rate: {rate}/s)...")
    
    try:
        result = subprocess.run(
            ["masscan", target, "-p", ports, "--rate", str(rate), "--wait", "2"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.stdout.strip():
            # Parse masscan output
            lines = result.stdout.strip().split('\n')
            open_ports = {}
            
            for line in lines:
                if 'open' in line and 'tcp' in line:
                    parts = line.split()
                    # Format: Discovered open port 80/tcp on 192.168.1.1
                    for i, p in enumerate(parts):
                        if '/' in p and 'tcp' in p:
                            port = p.split('/')[0]
                            ip = parts[-1] if i < len(parts) - 1 else target
                            if ip not in open_ports:
                                open_ports[ip] = []
                            open_ports[ip].append(port)
            
            output = f"Masscan found {len(open_ports)} hosts with open ports:\n"
            for ip, ports in list(open_ports.items())[:10]:
                output += f"  {ip}: {', '.join(ports)}\n"
            
            state.context["masscan_results"] = open_ports
            return output
        
        return f"No open ports found on {target}"
        
    except subprocess.TimeoutExpired:
        return f"Masscan timed out for {target}"
    except Exception as e:
        return f"Masscan error: {e}"


@register_handler("rustscan")
def handle_rustscan(action_input: Dict[str, Any], state: Any) -> str:
    """Fast Rust-based port scanner."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target specified"
    
    print(f"  🦀 Rustscan scanning {target}...")
    
    try:
        result = subprocess.run(
            ["/snap/bin/rustscan", "-a", target, "--ulimit", "5000", "-b", "1000", "--"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        output_text = result.stdout + result.stderr
        
        # Parse open ports from rustscan output
        open_ports = []
        for line in output_text.split('\n'):
            if 'Open' in line:
                # Extract port number
                import re
                ports_found = re.findall(r'Open (\d+)', line)
                open_ports.extend(ports_found)
        
        if open_ports:
            output = f"Rustscan found {len(open_ports)} open ports on {target}:\n"
            output += f"  Ports: {', '.join(open_ports[:30])}\n"
            
            state.context["rustscan_results"] = {target: open_ports}
            return output
        
        return f"No open ports found on {target}"
        
    except subprocess.TimeoutExpired:
        return f"Rustscan timed out for {target}"
    except Exception as e:
        return f"Rustscan error: {e}"


@register_handler("amass")
def handle_amass(action_input: Dict[str, Any], state: Any) -> str:
    """Advanced subdomain enumeration with OSINT."""
    from app.core.state import save_subdomains
    import subprocess
    
    domain = action_input.get("domain", "")
    if not domain:
        if state and hasattr(state, "context") and state.context is not None:
            domain = state.context.get("last_domain", "")
        else:
            pass
    if not domain:
        return "Error: No domain specified"
    
    mode = action_input.get("mode", "passive")  # passive or active
    
    print(f"  🔍 Amass {mode} enumeration for {domain}...")
    
    try:
        if mode == "active":
            cmd = ["/snap/bin/amass", "enum", "-active", "-d", domain, "-timeout", "10"]
        else:
            cmd = ["/snap/bin/amass", "enum", "-passive", "-d", domain, "-timeout", "10"]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.stdout.strip():
            subdomains = [s.strip() for s in result.stdout.strip().split('\n') if s.strip()]
            
            save_subdomains(subdomains, domain)
            if state and hasattr(state, "context") and state.context is not None:
                state.context["last_domain"] = domain
                state.context["has_subdomains"] = True
                state.context["subdomain_count"] = len(subdomains)
            else:
                pass
            
            output = f"Amass found {len(subdomains)} subdomains:\n"
            for sub in subdomains[:15]:
                output += f"  {sub}\n"
            if len(subdomains) > 15:
                output += f"  ... and {len(subdomains) - 15} more\n"
            return output
        
        return f"No subdomains found for {domain}"
        
    except subprocess.TimeoutExpired:
        return f"Amass timed out for {domain} (10 min limit)"
    except Exception as e:
        return f"Amass error: {e}"

