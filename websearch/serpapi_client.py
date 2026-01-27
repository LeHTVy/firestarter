"""SerpApi client for web search."""

import requests
import logging
from typing import Dict, Any, List, Optional

class SerpAPIClient:
    """Client for communicating with SerpApi."""
    
    def __init__(self, api_key: str):
        """Initialize SerpApi client.
        
        Args:
            api_key: SerpApi API key
        """
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"
        self.logger = logging.getLogger(__name__)

    def search(self, query: str, num_results: int = 10, **kwargs) -> Dict[str, Any]:
        """Perform a search using SerpApi.
        
        Args:
            query: Search query
            num_results: Number of results to return
            **kwargs: Additional parameters for SerpApi
            
        Returns:
            Formatted search results
        """
        params = {
            'q': query,
            'api_key': self.api_key,
            'engine': 'google',
            'num': num_results
        }
        
        # Add any other kwargs that SerpApi supports
        params.update(kwargs)
        
        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data:
                return {
                    'success': False,
                    'error': data['error'],
                    'results': []
                }
            
            results = []
            for item in data.get('organic_results', [])[:num_results]:
                results.append({
                    'title': item.get('title'),
                    'link': item.get('link'),
                    'snippet': item.get('snippet'),
                    'source': 'google',
                    'score': item.get('position', 0)
                })
                
            return {
                'success': True,
                'results': {
                    'results': results,
                    'query': query,
                    'total_results': data.get('search_information', {}).get('total_results', len(results))
                },
                'provider': 'serpapi'
            }
            
        except Exception as e:
            self.logger.error(f"SerpApi search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
