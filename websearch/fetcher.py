"""Web content fetcher."""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List
from newspaper import Article
import time


class WebFetcher:
    """Fetcher for web content."""
    
    def __init__(self, timeout: int = 10, max_retries: int = 3):
        """Initialize web fetcher.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_url(self, url: str) -> Dict[str, Any]:
        """Fetch content from URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            Fetched content with metadata
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract text content
                text_content = soup.get_text(separator=' ', strip=True)
                
                # Extract metadata
                title = soup.find('title')
                title_text = title.get_text() if title else ""
                
                meta_description = soup.find('meta', attrs={'name': 'description'})
                description = meta_description.get('content', '') if meta_description else ""
                
                # Try using newspaper3k for better article extraction
                try:
                    article = Article(url)
                    article.download()
                    article.parse()
                    
                    return {
                        "success": True,
                        "url": url,
                        "title": article.title or title_text,
                        "text": article.text or text_content,
                        "authors": article.authors,
                        "publish_date": str(article.publish_date) if article.publish_date else None,
                        "description": article.meta_description or description,
                        "images": article.images,
                        "html": response.text[:10000]  # Limit HTML size
                    }
                except:
                    # Fallback to BeautifulSoup extraction
                    return {
                        "success": True,
                        "url": url,
                        "title": title_text,
                        "text": text_content[:50000],  # Limit text size
                        "authors": [],
                        "publish_date": None,
                        "description": description,
                        "images": [],
                        "html": response.text[:10000]
                    }
                    
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    return {
                        "success": False,
                        "error": str(e),
                        "url": url
                    }
                time.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "url": url
                }
        
        return {
            "success": False,
            "error": "Max retries exceeded",
            "url": url
        }
    
    def fetch_multiple_urls(self, urls: List[str]) -> Dict[str, Any]:
        """Fetch content from multiple URLs.
        
        Args:
            urls: List of URLs to fetch
            
        Returns:
            Dictionary of fetched content
        """
        results = {}
        
        for url in urls:
            results[url] = self.fetch_url(url)
            time.sleep(0.5)  # Rate limiting
        
        return {
            "success": True,
            "results": results,
            "total_urls": len(urls),
            "successful": sum(1 for r in results.values() if r.get("success"))
        }
