"""
Web Tool Handlers
=================

Handles: httpx_probe, httpx_batch, dir_bruteforce, tech_analyze
"""
from typing import Dict, Any
from app.tools.handlers import register_handler


@register_handler("httpx_probe")
def handle_httpx_probe(action_input: Dict[str, Any], state: Any) -> str:
    """Probe a single URL with httpx."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target specified"
    
    # Add protocol if missing
    if not target.startswith("http"):
        target = f"https://{target}"
    
    print(f"  🌐 Probing {target}...")
    
    try:
        result = subprocess.run(
            ["/home/hellrazor/go/bin/httpx", "-u", target, "-silent", "-status-code", "-title"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.stdout.strip():
            return f"HTTPX probe result:\n{result.stdout}"
        else:
            return f"No response from {target}"
            
    except subprocess.TimeoutExpired:
        return f"HTTPX probe timed out for {target}"
    except Exception as e:
        return f"HTTPX error: {e}"


@register_handler("httpx_batch")
def handle_httpx_batch(action_input: Dict[str, Any], state: Any) -> str:
    """Batch probe subdomains with httpx."""
    from app.core.state import get_subdomain_file
    import subprocess
    
    subdomain_file = get_subdomain_file()
    if not subdomain_file:
        return "Error: No subdomain file found. Run subdomain_enum first."
    
    print(f"  📁 Using subdomain file: {subdomain_file}")
    
    # Count targets
    with open(subdomain_file, 'r') as f:
        target_count = sum(1 for _ in f)
    
    print(f"  🌐 Batch probing {target_count} hosts with httpx...")
    
    try:
        result = subprocess.run(
            ["/home/hellrazor/go/bin/httpx", "-l", str(subdomain_file), 
             "-silent", "-status-code", "-title", "-timeout", "10"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if not result.stdout.strip():
            return "No responsive hosts found."
        
        lines = result.stdout.strip().split('\n')
        
        # Categorize responses
        ok_hosts = []
        forbidden_hosts = []
        redirect_hosts = []
        other_hosts = []
        
        for line in lines:
            if "[200]" in line:
                host = line.split()[0].replace("https://", "").replace("http://", "")
                ok_hosts.append(host)
            elif "[403]" in line:
                host = line.split()[0].replace("https://", "").replace("http://", "")
                forbidden_hosts.append(host)
            elif "[301]" in line or "[302]" in line:
                host = line.split()[0].replace("https://", "").replace("http://", "")
                redirect_hosts.append(host)
            else:
                host = line.split()[0].replace("https://", "").replace("http://", "")
                other_hosts.append(host)
        
        # Store in context
        state.context["httpx_200_hosts"] = ok_hosts
        state.context["httpx_403_hosts"] = forbidden_hosts
        state.context["httpx_all_hosts"] = ok_hosts + forbidden_hosts + redirect_hosts + other_hosts
        
        output = f"Probed {target_count} hosts, {len(lines)} responded:\n"
        output += f"  ✓ 200 OK: {len(ok_hosts)} hosts\n"
        output += f"  ⚠ 403 Forbidden: {len(forbidden_hosts)} hosts\n"
        output += f"  ➡ 301/302 Redirect: {len(redirect_hosts)} hosts\n"
        output += f"  Other: {len(other_hosts)} hosts\n"
        
        if ok_hosts:
            output += f"\n200 OK hosts (BEST vuln scan targets):\n"
            for host in ok_hosts[:10]:
                output += f"  {host}\n"
        
        return output
        
    except subprocess.TimeoutExpired:
        return "HTTPX batch probe timed out (5 min limit)"
    except Exception as e:
        return f"HTTPX batch error: {e}"


@register_handler("dir_bruteforce")
def handle_dir_bruteforce(action_input: Dict[str, Any], state: Any) -> str:
    """Directory bruteforce with gobuster."""
    import subprocess
    import random
    
    target = action_input.get("target", "")
    mode = action_input.get("mode", "stealth").lower()
    
    if not target:
        ok_hosts = state.context.get("httpx_200_hosts", [])
        if ok_hosts:
            target = ok_hosts[0]
        else:
            return "Error: No target specified"
    
    if not target.startswith("http"):
        target = f"http://{target}"
    
    # User agents for stealth
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    ]
    
    if mode == "fast":
        print(f"  📂 Brute-forcing directories on {target} (mode: fast)...")
        threads = "20"
        delay = "0ms"
    else:
        print(f"  📂 Brute-forcing directories on {target} (mode: stealth)...")
        threads = "1"
        delay = "500ms"
    
    wordlist = "/usr/share/wordlists/dirb/common.txt"
    
    try:
        result = subprocess.run(
            ["/home/hellrazor/go/bin/gobuster", "dir",
             "-u", target,
             "-w", wordlist,
             "-t", threads,
             "--delay", delay,
             "-a", random.choice(user_agents),
             "-q"],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.stdout.strip():
            found = [l for l in result.stdout.split('\n') if '(Status:' in l]
            if found:
                output = f"Found {len(found)} directories on {target}:\n"
                for d in found[:20]:
                    output += f"  {d}\n"
                return output
        
        return f"No directories found on {target}"
        
    except subprocess.TimeoutExpired:
        return f"Directory bruteforce timed out for {target}"
    except Exception as e:
        return f"Gobuster error: {e}"


@register_handler("tech_analyze")
def handle_tech_analyze(action_input: Dict[str, Any], state: Any) -> str:
    """Deep technology analysis with LLM."""
    import requests
    from langchain_ollama import ChatOllama
    
    target = action_input.get("target", "")
    if not target:
        ok_hosts = state.context.get("httpx_200_hosts", [])
        if ok_hosts:
            target = f"https://{ok_hosts[0]}"
        else:
            return "Error: No target specified"
    
    if not target.startswith("http"):
        target = f"https://{target}"
    
    print(f"  🔬 Deep analyzing {target}...")
    
    try:
        response = requests.get(target, timeout=30, verify=False)
        
        output = f"═══ TECH ANALYSIS: {target} ═══\n\n"
        output += f"Status: {response.status_code}\n"
        output += f"Server: {response.headers.get('Server', 'Unknown')}\n"
        output += f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}\n"
        
        # Get LLM to analyze
        content = f"""
Headers:
{dict(response.headers)}

HTML (first 5000 chars):
{response.text[:5000]}
"""
        
        llm = ChatOllama(model="deepseek-r1:latest", temperature=0)
        analysis_prompt = f"""Analyze this web response for security issues:
1. Technologies detected (CMS, frameworks, libraries)
2. Security headers (CSP, HSTS, XSS protection)
3. Potential vulnerabilities (outdated versions, misconfigs)
4. Attack vectors to try

{content}

Be specific and actionable. Format as markdown."""

        result = llm.invoke(analysis_prompt)
        output += f"\n=== LLM SECURITY ANALYSIS ===\n{result.content[:2000]}"
        
        return output
        
    except requests.Timeout:
        return f"Request timed out for {target}"
    except Exception as e:
        return f"Tech analysis error: {e}"


@register_handler("ffuf")
def handle_ffuf(action_input: Dict[str, Any], state: Any) -> str:
    """Fast web fuzzer for directories/parameters."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target specified. Example: ffuf with {\"target\": \"http://example.com/FUZZ\"}"
    
    if not target.startswith("http"):
        target = f"http://{target}"
    
    # Add FUZZ placeholder if not present
    if "FUZZ" not in target:
        target = target.rstrip("/") + "/FUZZ"
    
    wordlist = action_input.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
    
    print(f"  🔥 Fuzzing {target}...")
    
    try:
        result = subprocess.run(
            ["/home/hellrazor/go/bin/ffuf",
             "-u", target,
             "-w", wordlist,
             "-mc", "200,204,301,302,307,401,403",
             "-t", "10",
             "-timeout", "10",
             "-s"],  # Silent mode
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            output = f"Found {len(lines)} URLs:\n"
            for line in lines[:20]:
                output += f"  {line}\n"
            return output
        
        return f"No results found for {target}"
        
    except subprocess.TimeoutExpired:
        return f"FFUF timed out for {target}"
    except Exception as e:
        return f"FFUF error: {e}"


@register_handler("feroxbuster")
def handle_feroxbuster(action_input: Dict[str, Any], state: Any) -> str:
    """Fast content discovery with feroxbuster."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target specified"
    
    if not target.startswith("http"):
        target = f"http://{target}"
    
    print(f"  🦀 Feroxbuster scanning {target}...")
    
    try:
        result = subprocess.run(
            ["/snap/bin/feroxbuster",
             "-u", target,
             "-w", "/usr/share/wordlists/dirb/common.txt",
             "-t", "10",
             "--timeout", "10",
             "-q",
             "--no-state"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.stdout.strip():
            lines = [l for l in result.stdout.split('\n') if l.strip() and 'http' in l]
            output = f"Feroxbuster found {len(lines)} URLs:\n"
            for line in lines[:20]:
                output += f"  {line}\n"
            return output
        
        return f"No results found for {target}"
        
    except subprocess.TimeoutExpired:
        return f"Feroxbuster timed out for {target}"
    except Exception as e:
        return f"Feroxbuster error: {e}"


@register_handler("waybackurls")
def handle_waybackurls(action_input: Dict[str, Any], state: Any) -> str:
    """Fetch URLs from Wayback Machine."""
    import subprocess
    
    domain = action_input.get("domain", "")
    if not domain:
        domain = state.context.get("last_domain", "")
    if not domain:
        return "Error: No domain specified"
    
    print(f"  📜 Fetching Wayback URLs for {domain}...")
    
    try:
        result = subprocess.run(
            ["/home/hellrazor/go/bin/waybackurls", domain],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.stdout.strip():
            urls = result.stdout.strip().split('\n')
            unique_urls = list(set(urls))
            
            # Store in context
            state.context["wayback_urls"] = unique_urls
            
            output = f"Found {len(unique_urls)} unique URLs from Wayback Machine:\n"
            for url in unique_urls[:20]:
                output += f"  {url}\n"
            if len(unique_urls) > 20:
                output += f"  ... and {len(unique_urls) - 20} more\n"
            return output
        
        return f"No Wayback URLs found for {domain}"
        
    except subprocess.TimeoutExpired:
        return f"Waybackurls timed out for {domain}"
    except Exception as e:
        return f"Waybackurls error: {e}"


@register_handler("gau")
def handle_gau(action_input: Dict[str, Any], state: Any) -> str:
    """Get All URLs from multiple sources."""
    import subprocess
    
    domain = action_input.get("domain", "")
    if not domain:
        domain = state.context.get("last_domain", "")
    if not domain:
        return "Error: No domain specified"
    
    print(f"  🔗 Fetching all URLs for {domain}...")
    
    try:
        result = subprocess.run(
            ["/home/hellrazor/go/bin/gau", "--threads", "5", "--timeout", "60", domain],
            capture_output=True,
            text=True,
            timeout=180
        )
        
        if result.stdout.strip():
            urls = result.stdout.strip().split('\n')
            unique_urls = list(set(urls))
            
            # Store in context
            state.context["gau_urls"] = unique_urls
            
            output = f"GAU found {len(unique_urls)} unique URLs:\n"
            for url in unique_urls[:20]:
                output += f"  {url}\n"
            if len(unique_urls) > 20:
                output += f"  ... and {len(unique_urls) - 20} more\n"
            return output
        
        return f"No URLs found for {domain}"
        
    except subprocess.TimeoutExpired:
        return f"GAU timed out for {domain}"
    except Exception as e:
        return f"GAU error: {e}"


@register_handler("katana")
def handle_katana(action_input: Dict[str, Any], state: Any) -> str:
    """Web crawler for endpoint discovery."""
    import subprocess
    
    target = action_input.get("target", "")
    if not target:
        return "Error: No target specified"
    
    if not target.startswith("http"):
        target = f"https://{target}"
    
    depth = action_input.get("depth", "2")
    
    print(f"  🕷️ Katana crawling {target}...")
    
    try:
        result = subprocess.run(
            ["/home/hellrazor/go/bin/katana",
             "-u", target,
             "-d", str(depth),
             "-jc",  # JavaScript parsing
             "-silent",
             "-timeout", "5"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.stdout.strip():
            urls = result.stdout.strip().split('\n')
            unique_urls = list(set(urls))
            
            # Store in context
            state.context["katana_urls"] = unique_urls
            
            output = f"Katana discovered {len(unique_urls)} URLs:\n"
            for url in unique_urls[:20]:
                output += f"  {url}\n"
            if len(unique_urls) > 20:
                output += f"  ... and {len(unique_urls) - 20} more\n"
            return output
        
        return f"No URLs discovered for {target}"
        
    except subprocess.TimeoutExpired:
        return f"Katana timed out for {target}"
    except Exception as e:
        return f"Katana error: {e}"

