"""
Web Research Module for SNODE
=============================

Searches the internet for security bypass techniques and vulnerability info.
Uses DuckDuckGo Instant Answers (free, no API key required).
"""

import requests
from typing import List, Dict, Optional


class WebResearcher:
    """Research security topics online."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
    
    def search_bypass_techniques(self, technology: str) -> Dict:
        """
        Search for bypass techniques for a security technology.
        
        Args:
            technology: e.g., "Cloudflare", "BitNinja", "ModSecurity"
        
        Returns:
            Dict with search results and techniques
        """
        queries = [
            f"{technology} WAF bypass techniques",
            f"{technology} security bypass",
            f"how to bypass {technology}",
        ]
        
        results = {
            "technology": technology,
            "techniques": [],
            "sources": [],
            "success": False
        }
        
        for query in queries:
            try:
                data = self._duckduckgo_search(query)
                if data:
                    results["techniques"].extend(data.get("techniques", []))
                    results["sources"].extend(data.get("sources", []))
                    results["success"] = True
            except Exception:
                continue
        
        # Deduplicate
        results["techniques"] = list(set(results["techniques"]))[:5]
        results["sources"] = results["sources"][:5]
        
        return results
    
    def search_origin_discovery(self, cdn: str) -> Dict:
        """
        Search for ways to find origin IP behind a CDN.
        
        Args:
            cdn: e.g., "Cloudflare", "Akamai"
        """
        query = f"find real IP behind {cdn} origin discovery"
        
        try:
            data = self._duckduckgo_search(query)
            return {
                "cdn": cdn,
                "methods": data.get("techniques", []),
                "sources": data.get("sources", []),
                "success": True
            }
        except Exception as e:
            return {"cdn": cdn, "error": str(e), "success": False}
    
    def search_vulnerability(self, technology: str, version: str = None) -> Dict:
        """
        Search for known vulnerabilities in a technology.
        
        Args:
            technology: e.g., "Apache", "WordPress"
            version: Optional version number
        """
        query = f"{technology} {version or ''} vulnerability exploit CVE"
        
        try:
            data = self._duckduckgo_search(query)
            return {
                "technology": technology,
                "version": version,
                "vulnerabilities": data.get("techniques", []),
                "sources": data.get("sources", []),
                "success": True
            }
        except Exception as e:
            return {"technology": technology, "error": str(e), "success": False}
    
    def _duckduckgo_search(self, query: str) -> Dict:
        """
        Search using DuckDuckGo HTML (no API key needed).
        """
        url = "https://html.duckduckgo.com/html/"
        
        try:
            response = self.session.post(
                url,
                data={"q": query},
                timeout=15
            )
            
            if response.status_code != 200:
                return {}
            
            # Parse results from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            
            techniques = []
            sources = []
            
            # Extract result snippets
            for result in soup.select(".result__body")[:5]:
                snippet = result.select_one(".result__snippet")
                link = result.select_one(".result__a")
                
                if snippet:
                    text = snippet.get_text(strip=True)
                    # Extract actionable techniques from snippet
                    if any(kw in text.lower() for kw in ["bypass", "trick", "method", "technique", "exploit", "vulnerability"]):
                        techniques.append(text[:200])
                
                if link:
                    href = link.get("href", "")
                    title = link.get_text(strip=True)
                    if href and title:
                        sources.append({"title": title[:60], "url": href})
            
            return {"techniques": techniques, "sources": sources}
            
        except Exception as e:
            return {"error": str(e)}
    
    def research_security_tech(self, tech_name: str) -> str:
        """
        Comprehensive research on a security technology.
        Returns formatted string for display.
        """
        results = []
        
        # Search for bypass techniques
        bypass = self.search_bypass_techniques(tech_name)
        if bypass.get("techniques"):
            results.append(f"🔍 **Bypass Techniques for {tech_name}:**")
            for i, tech in enumerate(bypass["techniques"][:3], 1):
                results.append(f"   {i}. {tech}")
        
        # Search for origin discovery if CDN
        if any(cdn in tech_name.lower() for cdn in ["cloudflare", "akamai", "fastly", "incapsula"]):
            origin = self.search_origin_discovery(tech_name)
            if origin.get("methods"):
                results.append(f"\n🎯 **Origin IP Discovery:**")
                for method in origin["methods"][:2]:
                    results.append(f"   • {method}")
        
        # Add sources
        if bypass.get("sources"):
            results.append(f"\n📚 **Sources:**")
            for src in bypass["sources"][:3]:
                results.append(f"   • [{src['title']}]({src['url']})")
        
        return "\n".join(results) if results else f"No research results for {tech_name}"


# Singleton instance
_researcher = None

def get_researcher() -> WebResearcher:
    """Get or create WebResearcher instance."""
    global _researcher
    if _researcher is None:
        _researcher = WebResearcher()
    return _researcher


def research_bypass(technology: str) -> str:
    """Quick function to research bypass techniques."""
    researcher = get_researcher()
    return researcher.research_security_tech(technology)


def web_search(query: str, max_results: int = 5) -> dict:
    """
    General web search for any query.
    
    Args:
        query: The search query (any question)
        max_results: Maximum number of results
    
    Returns:
        Dict with snippets and sources
    """
    try:
        from app.websearch.aggregator import get_search_aggregator

        agg = get_search_aggregator()
        res = agg.search(query=query, num_results=max_results, timeout=15)

        if not res.get("success"):
            return {"success": False, "error": res.get("error", "Search failed")}

        snippets = []
        sources = []
        for r in res.get("results", [])[:max_results]:
            snippet = (r.get("snippet") or "").strip()
            title = (r.get("title") or "").strip()
            url = (r.get("url") or "").strip()

            if snippet:
                snippets.append(snippet[:300])
            if title and url:
                sources.append({"title": title[:80], "url": url})

        return {"success": True, "query": query, "snippets": snippets, "sources": sources}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_and_format(query: str) -> str:
    """
    Search and return formatted results for LLM context.
    
    Args:
        query: The search query
    
    Returns:
        Formatted string with search results
    """
    result = web_search(query)
    
    if not result.get("success"):
        return ""
    
    output = []
    output.append(f"🌐 **Web Search Results for: {query}**\n")
    
    for i, snippet in enumerate(result.get("snippets", [])[:3], 1):
        output.append(f"{i}. {snippet}\n")
    
    if result.get("sources"):
        output.append("\n📚 **Sources:**")
        for src in result["sources"][:3]:
            output.append(f"  • {src['title']}")
    
    return "\n".join(output)

