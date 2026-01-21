"""Shodan tool implementation."""

import shodan
from typing import Dict, Any, Optional
import os


def search(query: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Search Shodan for internet-connected devices.
    
    Args:
        query: Shodan search query
        filters: Additional search filters
        
    Returns:
        Search results as dictionary
    """
    try:
        api_key = os.getenv('SHODAN_API_KEY')
        if not api_key:
            return {
                "success": False,
                "error": "SHODAN_API_KEY not set in environment",
                "results": None
            }
        
        api = shodan.Shodan(api_key)
        
        # Build query with filters
        search_query = query
        if filters:
            filter_str = " ".join([f"{k}:{v}" for k, v in filters.items()])
            search_query = f"{query} {filter_str}"
        
        # Perform search
        results = api.search(search_query)
        
        # Format results
        formatted_results = {
            "total": results['total'],
            "matches": []
        }
        
        for match in results['matches']:
            formatted_results["matches"].append({
                "ip": match.get('ip_str', ''),
                "port": match.get('port', ''),
                "hostnames": match.get('hostnames', []),
                "org": match.get('org', ''),
                "os": match.get('os', ''),
                "product": match.get('product', ''),
                "version": match.get('version', ''),
                "data": match.get('data', '')[:500]  # Limit data length
            })
        
        return {
            "success": True,
            "results": formatted_results,
            "raw_output": str(results)
        }
        
    except shodan.APIError as e:
        return {
            "success": False,
            "error": f"Shodan API error: {str(e)}",
            "results": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": None
        }
