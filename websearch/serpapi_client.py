"""SerpAPI client for web search."""

import os
from typing import Dict, Any, List, Optional
from serpapi import GoogleSearch


class SerpAPIClient:
    """Client for SerpAPI search."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize SerpAPI client.
        
        Args:
            api_key: SerpAPI API key. Defaults to SERPAPI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv('SERPAPI_API_KEY')
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY not set")
    
    def search(self, query: str, num_results: int = 10, **kwargs) -> Dict[str, Any]:
        """Perform web search.
        
        Args:
            query: Search query
            num_results: Number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            Search results
        """
        try:
            params = {
                "q": query,
                "api_key": self.api_key,
                "num": num_results,
                **kwargs
            }
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            # Format results
            formatted_results = {
                "query": query,
                "total_results": results.get("search_information", {}).get("total_results", 0),
                "results": []
            }
            
            # Extract organic results
            organic_results = results.get("organic_results", [])
            for result in organic_results:
                formatted_results["results"].append({
                    "title": result.get("title", ""),
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", ""),
                    "position": result.get("position", 0),
                    "date": result.get("date", "")
                })
            
            # Extract knowledge graph if available
            if "knowledge_graph" in results:
                formatted_results["knowledge_graph"] = results["knowledge_graph"]
            
            return {
                "success": True,
                "results": formatted_results,
                "raw": results
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "results": None
            }
    
    def search_multiple_queries(self, queries: List[str], num_results: int = 10) -> Dict[str, Any]:
        """Search multiple queries and aggregate results.
        
        Args:
            queries: List of search queries
            num_results: Number of results per query
            
        Returns:
            Aggregated search results
        """
        all_results = []
        
        for query in queries:
            result = self.search(query, num_results=num_results)
            if result.get("success"):
                all_results.extend(result["results"]["results"])
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            url = result.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        return {
            "success": True,
            "results": unique_results,
            "total_queries": len(queries),
            "total_results": len(unique_results)
        }
