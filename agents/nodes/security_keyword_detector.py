"""Security Keyword Detector - Fallback detection for security/pentest requests.

Loads keywords from cyber_pentest_keywords.md and provides detection utilities.
"""

from typing import Set, Dict, List, Optional
from pathlib import Path
import re


class SecurityKeywordDetector:
    """Detects security/pentest keywords in user prompts.
    
    Used as fallback when model fails to classify or generate subtasks.
    """
    
    def __init__(self, keywords_file: Optional[Path] = None):
        """Initialize detector.
        
        Args:
            keywords_file: Path to keywords markdown file. 
                          Defaults to cyber_pentest_keywords.md
        """
        if keywords_file is None:
            keywords_file = Path(__file__).parent / "cyber_pentest_keywords.md"
        
        self.keywords_file = keywords_file
        self.keywords: Set[str] = set()
        self.category_keywords: Dict[str, Set[str]] = {}
        
        self._load_keywords()
    
    def _load_keywords(self) -> None:
        """Load keywords from markdown file."""
        if not self.keywords_file.exists():
            # Fallback to hardcoded keywords if file not found
            self._load_default_keywords()
            return
        
        try:
            content = self.keywords_file.read_text(encoding='utf-8')
            self._parse_markdown_keywords(content)
        except Exception:
            self._load_default_keywords()
    
    def _parse_markdown_keywords(self, content: str) -> None:
        """Parse keywords from markdown content.
        
        Extracts keywords from backtick-enclosed text (`) in the markdown.
        """
        current_category = "general"
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Detect category headers (## or ###)
            if line.startswith('##'):
                # Extract category name
                category_match = re.search(r'##\s*[\w\s]*\s+([\w\s&]+)', line)
                if category_match:
                    current_category = category_match.group(1).strip().lower().replace(' ', '_')
                    if current_category not in self.category_keywords:
                        self.category_keywords[current_category] = set()
            
            # Extract keywords from backticks
            keywords = re.findall(r'`([^`]+)`', line)
            for kw in keywords:
                kw_lower = kw.lower().strip()
                self.keywords.add(kw_lower)
                
                if current_category not in self.category_keywords:
                    self.category_keywords[current_category] = set()
                self.category_keywords[current_category].add(kw_lower)
    
    def _load_default_keywords(self) -> None:
        """Load minimal fallback keywords (only used when md file is missing)."""
        # Minimal set - main keywords should come from cyber_pentest_keywords.md
        self.keywords = {"scan", "pentest", "recon", "attack", "exploit", "vuln", "assess"}
        self.category_keywords = {"general": self.keywords.copy()}
    
    def is_security_request(self, prompt: str) -> bool:
        """Check if prompt contains security/pentest keywords.
        
        Args:
            prompt: User prompt to check
            
        Returns:
            True if security keywords detected
        """
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in self.keywords)
    
    def detect_categories(self, prompt: str) -> List[str]:
        """Detect which security categories are mentioned in prompt.
        
        Args:
            prompt: User prompt to analyze
            
        Returns:
            List of detected category names
        """
        prompt_lower = prompt.lower()
        detected = []
        
        for category, keywords in self.category_keywords.items():
            if any(kw in prompt_lower for kw in keywords):
                detected.append(category)
        
        return detected
    
    def get_matched_keywords(self, prompt: str) -> List[str]:
        """Get all matched keywords in prompt.
        
        Args:
            prompt: User prompt to analyze
            
        Returns:
            List of matched keywords
        """
        prompt_lower = prompt.lower()
        return [kw for kw in self.keywords if kw in prompt_lower]
    
    def suggest_task_type(self, prompt: str) -> str:
        categories = self.detect_categories(prompt)
        
        if not categories:
            return "recon"  # Default
        
        # Priority-based suggestion
        if "attack" in categories or "exploitation" in categories:
            return "exploitation"
        if "vulnerability" in categories:
            return "analysis"
        if "recon" in categories or "scanning" in categories or "web" in categories:
            return "recon"
        
        return "mixed" if len(categories) > 1 else "recon"


# Singleton instance
_detector: Optional[SecurityKeywordDetector] = None


def get_keyword_detector() -> SecurityKeywordDetector:
    """Get singleton keyword detector instance."""
    global _detector
    if _detector is None:
        _detector = SecurityKeywordDetector()
    return _detector
