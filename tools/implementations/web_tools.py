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
