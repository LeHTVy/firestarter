"""VirusTotal tool implementation."""

from typing import Dict, Any
import os

# Try to import virustotal_python, fallback to requests if not available
try:
    from virustotal_python import Virustotal
    VIRUSTOTAL_AVAILABLE = True
except ImportError:
    try:
        import requests
        VIRUSTOTAL_AVAILABLE = True
        VIRUSTOTAL_USE_REQUESTS = True
    except ImportError:
        VIRUSTOTAL_AVAILABLE = False
        VIRUSTOTAL_USE_REQUESTS = False


def scan(resource: str, resource_type: str) -> Dict[str, Any]:
    """Scan file, URL, or hash with VirusTotal.
    
    Args:
        resource: File hash, URL, or IP address
        resource_type: Type of resource (hash, url, ip)
        
    Returns:
        Scan results as dictionary
    """
    try:
        if not VIRUSTOTAL_AVAILABLE:
            return {
                "success": False,
                "error": "VirusTotal library not installed. Install with: pip install virustotal-api",
                "results": None
            }
        
        api_key = os.getenv('VIRUSTOTAL_API_KEY')
        if not api_key:
            return {
                "success": False,
                "error": "VIRUSTOTAL_API_KEY not set in environment",
                "results": None
            }
        
        if VIRUSTOTAL_USE_REQUESTS:
            # Use requests-based implementation
            import requests
            base_url = "https://www.virustotal.com/api/v3"
            headers = {"x-apikey": api_key}
            
            if resource_type == "hash":
                resp = requests.get(f"{base_url}/files/{resource}", headers=headers)
            elif resource_type == "url":
                # Submit URL first
                submit_resp = requests.post(f"{base_url}/urls", 
                                          data={"url": resource}, 
                                          headers=headers)
                url_id = submit_resp.json()["data"]["id"]
                resp = requests.get(f"{base_url}/urls/{url_id}", headers=headers)
            elif resource_type == "ip":
                resp = requests.get(f"{base_url}/ip_addresses/{resource}", headers=headers)
            else:
                return {
                    "success": False,
                    "error": f"Invalid resource_type: {resource_type}",
                    "results": None
                }
            
            results = resp.json()
        else:
            # Use virustotal_python library
            vtotal = Virustotal(API_KEY=api_key)
        
            if resource_type == "hash":
                # Get file report
                resp = vtotal.request(f"files/{resource}")
            elif resource_type == "url":
                # Scan URL
                url_id = vtotal.request("urls", data={"url": resource}).json()["data"]["id"]
                resp = vtotal.request(f"urls/{url_id}")
            elif resource_type == "ip":
                # Get IP report
                resp = vtotal.request(f"ip_addresses/{resource}")
            
            results = resp.json()
        
        # Format results
        formatted_results = {
            "resource": resource,
            "resource_type": resource_type,
            "data": results.get("data", {})
        }
        
        return {
            "success": True,
            "results": formatted_results,
            "raw_output": str(results)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": None
        }
