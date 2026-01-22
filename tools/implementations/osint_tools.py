"""OSINT tools with subprocess streaming.

Implements email_harvesting, github_recon, social_media_recon.
"""

from typing import Dict, Any, Optional, Callable, List
import re
from tools.implementations.cli_executor import (
    run_cli_command,
    check_tool_installed
)


def email_harvesting(domain: str,
                    sources: Optional[List[str]] = None,
                    limit: int = 500,
                    stream_callback: Optional[Callable[[str], None]] = None,
                    timeout: int = 300) -> Dict[str, Any]:
    """Harvest emails and subdomains using theHarvester or similar tools.
    
    Args:
        domain: Target domain
        sources: Data sources to use (google, bing, linkedin, etc.)
        limit: Maximum results
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        Email harvesting results
    """
    if stream_callback:
        stream_callback(f"🔍 Email Harvesting for {domain}")
    
    results = {
        "domain": domain,
        "emails": [],
        "hosts": [],
        "ips": []
    }
    
    # Try theHarvester first
    if check_tool_installed("theHarvester"):
        source_str = ",".join(sources) if sources else "google,bing,duckduckgo"
        cmd = [
            "theHarvester",
            "-d", domain,
            "-b", source_str,
            "-l", str(limit)
        ]
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            parsed = _parse_harvester_output(raw_output, domain)
            results.update(parsed)
            
            if stream_callback:
                stream_callback(f"📊 Found {len(results['emails'])} emails, {len(results['hosts'])} hosts")
            
            return {
                "success": True,
                "results": results,
                "raw_output": raw_output
            }
    
    # Try hunter.io API with curl
    if check_tool_installed("curl"):
        import os
        api_key = os.getenv("HUNTER_API_KEY")
        if api_key:
            cmd = [
                "curl", "-s",
                f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={api_key}"
            ]
            
            result = run_cli_command(cmd, timeout=30, stream_callback=stream_callback)
            
            if result.get("success"):
                import json
                try:
                    data = json.loads(result.get("raw_output", "{}"))
                    emails = data.get("data", {}).get("emails", [])
                    results["emails"] = [e.get("value") for e in emails if e.get("value")]
                    
                    return {
                        "success": True,
                        "results": results,
                        "raw_output": result.get("raw_output", "")
                    }
                except json.JSONDecodeError:
                    pass
    
    # Fallback: Manual email pattern search
    if stream_callback:
        stream_callback("⚠️ Using manual email extraction (limited)")
    
    # Try to find emails on common pages
    pages = [
        f"https://{domain}/contact",
        f"https://{domain}/about",
        f"https://{domain}/team"
    ]
    
    for page in pages:
        if check_tool_installed("curl"):
            cmd = ["curl", "-s", "-L", page]
            result = run_cli_command(cmd, timeout=30)
            
            if result.get("success"):
                emails = _extract_emails(result.get("raw_output", ""))
                results["emails"].extend(emails)
    
    results["emails"] = list(set(results["emails"]))
    
    return {
        "success": True,
        "results": results,
        "raw_output": ""
    }


def github_recon(target: str,
                search_type: str = "all",
                stream_callback: Optional[Callable[[str], None]] = None,
                timeout: int = 300) -> Dict[str, Any]:
    """Search GitHub for leaked secrets, credentials, and sensitive information.
    
    Args:
        target: Target organization, domain, or keyword
        search_type: Type of search (secrets, code, repos, all)
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        GitHub recon results
    """
    if stream_callback:
        stream_callback(f"🔍 GitHub Recon for {target}")
    
    results = {
        "target": target,
        "secrets": [],
        "repositories": [],
        "code_matches": []
    }
    
    all_output = []
    
    # Try trufflehog first (secrets scanning)
    if check_tool_installed("trufflehog") and search_type in ["secrets", "all"]:
        cmd = ["trufflehog", "github", "--org", target, "--json"]
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            all_output.append(raw_output)
            secrets = _parse_trufflehog_output(raw_output)
            results["secrets"].extend(secrets)
    
    # Try gitleaks
    if check_tool_installed("gitleaks") and search_type in ["secrets", "all"]:
        # gitleaks requires a local repo, so this is limited
        if stream_callback:
            stream_callback("📋 gitleaks requires local repository")
    
    # Try github-search tool
    if check_tool_installed("github-search") and search_type in ["code", "all"]:
        cmd = ["github-search", "-q", target, "-t", "code"]
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            all_output.append(raw_output)
    
    # Manual GitHub API search with curl
    if check_tool_installed("curl"):
        import os
        github_token = os.getenv("GITHUB_TOKEN")
        
        search_queries = [
            f"{target} password",
            f"{target} api_key",
            f"{target} secret",
            f"{target} credentials"
        ]
        
        for query in search_queries:
            query_encoded = query.replace(" ", "+")
            cmd = [
                "curl", "-s",
                f"https://api.github.com/search/code?q={query_encoded}"
            ]
            
            if github_token:
                cmd.extend(["-H", f"Authorization: token {github_token}"])
            
            result = run_cli_command(cmd, timeout=30)
            
            if result.get("success"):
                try:
                    import json
                    data = json.loads(result.get("raw_output", "{}"))
                    items = data.get("items", [])
                    for item in items[:5]:  # Limit results
                        results["code_matches"].append({
                            "repo": item.get("repository", {}).get("full_name"),
                            "path": item.get("path"),
                            "url": item.get("html_url")
                        })
                except json.JSONDecodeError:
                    pass
    
    return {
        "success": True,
        "results": results,
        "raw_output": "\n".join(all_output)
    }


def social_media_recon(target: str,
                      platforms: Optional[List[str]] = None,
                      stream_callback: Optional[Callable[[str], None]] = None,
                      timeout: int = 300) -> Dict[str, Any]:
    """Search for social media profiles and information.
    
    Args:
        target: Username or name to search
        platforms: Social media platforms to search
        stream_callback: Callback for streaming output
        timeout: Timeout in seconds
        
    Returns:
        Social media recon results
    """
    if stream_callback:
        stream_callback(f"🔍 Social Media Recon for {target}")
    
    results = {
        "target": target,
        "profiles": [],
        "found_on": []
    }
    
    # Try sherlock
    if check_tool_installed("sherlock"):
        cmd = ["sherlock", target, "--print-found", "--timeout", "10"]
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            profiles = _parse_sherlock_output(raw_output)
            results["profiles"].extend(profiles)
            results["found_on"] = [p["platform"] for p in profiles]
            
            return {
                "success": True,
                "results": results,
                "raw_output": raw_output
            }
    
    # Try socialscan
    if check_tool_installed("socialscan"):
        cmd = ["socialscan", target]
        
        result = run_cli_command(cmd, timeout=timeout, stream_callback=stream_callback)
        
        if result.get("success"):
            raw_output = result.get("raw_output", "")
            
            return {
                "success": True,
                "results": results,
                "raw_output": raw_output
            }
    
    # Manual check with curl
    platforms_urls = {
        "twitter": f"https://twitter.com/{target}",
        "github": f"https://github.com/{target}",
        "instagram": f"https://instagram.com/{target}",
        "linkedin": f"https://linkedin.com/in/{target}",
        "facebook": f"https://facebook.com/{target}"
    }
    
    if check_tool_installed("curl"):
        check_platforms = platforms if platforms else list(platforms_urls.keys())
        
        for platform in check_platforms:
            if platform in platforms_urls:
                url = platforms_urls[platform]
                cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-L", url]
                
                result = run_cli_command(cmd, timeout=10)
                
                if result.get("success"):
                    status = result.get("raw_output", "").strip()
                    if status == "200":
                        results["profiles"].append({
                            "platform": platform,
                            "url": url,
                            "status": "found"
                        })
                        results["found_on"].append(platform)
                        if stream_callback:
                            stream_callback(f"  ✓ Found on {platform}")
    
    return {
        "success": True,
        "results": results,
        "raw_output": ""
    }


def _parse_harvester_output(output: str, domain: str) -> Dict[str, List[str]]:
    """Parse theHarvester output."""
    results = {
        "emails": [],
        "hosts": [],
        "ips": []
    }
    
    # Extract emails
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, output)
    results["emails"] = list(set(emails))
    
    # Extract hosts (subdomains)
    host_pattern = rf'([a-zA-Z0-9][-a-zA-Z0-9.]*\.{re.escape(domain)})'
    hosts = re.findall(host_pattern, output, re.IGNORECASE)
    results["hosts"] = list(set(hosts))
    
    # Extract IPs
    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    ips = re.findall(ip_pattern, output)
    results["ips"] = list(set(ips))
    
    return results


def _extract_emails(text: str) -> List[str]:
    """Extract email addresses from text."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(email_pattern, text)))


def _parse_trufflehog_output(output: str) -> List[Dict[str, Any]]:
    """Parse trufflehog JSON output."""
    secrets = []
    
    try:
        import json
        for line in output.split("\n"):
            if line.strip():
                try:
                    data = json.loads(line)
                    secrets.append({
                        "type": data.get("DetectorType", "unknown"),
                        "source": data.get("SourceMetadata", {}).get("Data", {}).get("Github", {}).get("Repository"),
                        "verified": data.get("Verified", False)
                    })
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    
    return secrets


def _parse_sherlock_output(output: str) -> List[Dict[str, str]]:
    """Parse sherlock output."""
    profiles = []
    
    for line in output.split("\n"):
        line = line.strip()
        # sherlock format: [+] Platform: url
        match = re.search(r'\[\+\]\s+(\w+):\s+(https?://\S+)', line)
        if match:
            profiles.append({
                "platform": match.group(1),
                "url": match.group(2)
            })
    
    return profiles
