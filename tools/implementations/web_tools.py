"""Web security tools implementation."""

import ssl
import socket
import json
from datetime import datetime
from urllib.parse import urlparse

def ssl_cert_scan(host: str, port: int = 443) -> dict:
    """Scan SSL certificate.
    
    Args:
        host: Hostname
        port: Port
        
    Returns:
        Certificate info
    """
    try:
        # Handle URL inputs
        if "://" in host:
            parsed = urlparse(host)
            host = parsed.netloc.split(':')[0]
            
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert(binary_form=True)
                version = ssock.version()
                cipher = ssock.cipher()
                
                return {
                    "success": True,
                    "host": host,
                    "port": port,
                    "version": version,
                    "cipher": cipher,
                    "output": f"Connected to {host}:{port} using {version}\nCipher: {cipher}"
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def technology_detection(url: str) -> dict:
    """Detect technologies used on a website.
    
    Args:
        url: Target URL
        
    Returns:
        Detected technologies
    """
    import requests
    from bs4 import BeautifulSoup
    import re
    
    try:
        if not url.startswith("http"):
            url = f"https://{url}"
            
        response = requests.get(url, timeout=10, verify=False)
        headers = response.headers
        html = response.text.lower()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        techs = []
        
        # 1. Header Analysis
        server = headers.get('Server', '')
        if server: techs.append(f"Server: {server}")
        
        x_powered_by = headers.get('X-Powered-By', '')
        if x_powered_by: techs.append(f"Powered By: {x_powered_by}")
        
        # 2. Meta Tags / Fingerprints
        generator = soup.find('meta', attrs={'name': 'generator'})
        if generator: techs.append(f"Generator: {generator.get('content')}")
        
        # 3. Simple Pattern Matching
        patterns = {
            "WordPress": r"/wp-content/|/wp-includes/",
            "Joomla": r"joomla",
            "Drupal": r"drupal",
            "React": r"react\.development\.js|react\.production\.min\.js",
            "Vue.js": r"vue\.js|vue\.min\.js",
            "jQuery": r"jquery\.js|jquery\.min\.js",
            "PHP": r"\.php",
            "Laravel": r"xsrf-token|laravel_session"
        }
        
        for name, pattern in patterns.items():
            if re.search(pattern, html):
                techs.append(name)
        
        # Also check cookies
        for cookie in response.cookies:
            if cookie.name.lower() == 'phpsessid': techs.append("PHP")
            if cookie.name.lower() == 'aspsessionid': techs.append("ASP.NET")
            
        return {
            "success": True,
            "url": url,
            "technologies": list(set(techs)),
            "raw_headers": dict(headers),
            "output": f"Detected: {', '.join(techs)}" if techs else "No specific technologies identified."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
