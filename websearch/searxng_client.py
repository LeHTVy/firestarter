"""SearxNG client for self-hosted web search."""

import requests
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

class SearxNGClient:
    """Client for communicating with a SearxNG instance."""
    
    def __init__(self, base_url: str, engines: List[str] = None):
        """Initialize SearxNG client.
        
        Args:
            base_url: Base URL of the SearxNG instance (e.g., 'http://localhost:8080')
            engines: List of engines to query (default: all active in SearxNG)
        """
        self.base_url = base_url.rstrip('/')
        if isinstance(engines, str):
            self.engines = [engines]
        else:
            self.engines = [str(e) for e in (engines or []) if e]
        self.logger = logging.getLogger(__name__)

    def search(self, query: str, num_results: int = 10, **kwargs) -> Dict[str, Any]:
        """Perform a search using SearxNG.
        
        Args:
            query: Search query
            num_results: Number of results to return
            **kwargs: Additional parameters for SearxNG
            
        Returns:
            Formatted search results
        """
        params = {
            'q': query,
            'format': 'json',
            'pageno': 1,
        }
        
        if self.engines:
            params['engines'] = ','.join(self.engines)
            
        # Add any other kwargs that SearxNG supports
        params.update(kwargs)
        
        try:
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get('results', [])[:num_results]:
                results.append({
                    'title': item.get('title'),
                    'link': item.get('url'),
                    'snippet': item.get('content') or item.get('snippet'),
                    'source': item.get('engines', ['searxng'])[0],
                    'score': item.get('score', 0)
                })
                
            return {
                'success': True,
                'results': {
                    'results': results,
                    'query': query,
                    'total_results': data.get('number_of_results', len(results))
                },
                'provider': 'searxng'
            }
            
        except Exception as e:
            self.logger.error(f"SearxNG search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }

if __name__ == "__main__":
    # Quick test if URL is provided
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else None
    if url:
        client = SearxNGClient(url)
        print(f"Searching for 'firestarter security' on {url}...")
        res = client.search("firestarter security")
        print(res)
    else:
        print("Usage: python searxng_client.py <SEARXNG_URL>")
