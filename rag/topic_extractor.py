"""Topic extraction and retrieval for conversations."""

from typing import List, Dict, Any, Optional
import re
from collections import Counter
from rag.context_ranker import ContextRanker


class TopicExtractor:
    """Extract and manage topics from conversations."""
    
    def __init__(self):
        """Initialize topic extractor."""
        self.ranker = ContextRanker()  # Reuse entity extraction
    
    def extract_topics(self, 
                      messages: List[Dict[str, Any]],
                      max_topics: int = 10) -> List[str]:
        """Extract topics from conversation messages.
        
        Args:
            messages: List of conversation messages
            max_topics: Maximum number of topics to extract
            
        Returns:
            List of topic strings
        """
        # Combine all message content
        all_text = " ".join([
            msg.get("content", "") for msg in messages
            if msg.get("content")
        ])
        
        # Extract entities (domains, IPs, tools, CVEs)
        entities = self.ranker._extract_entities(all_text)
        
        # Extract keywords (security-related terms)
        keywords = self._extract_keywords(all_text)
        
        # Combine entities and keywords
        topics = entities + keywords
        
        # Count frequency
        topic_counts = Counter(topics)
        
        # Return top topics by frequency
        top_topics = [topic for topic, count in topic_counts.most_common(max_topics)]
        
        return top_topics
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract security-related keywords from text.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords
        """
        text_lower = text.lower()
        keywords = []
        
        # Security-related keywords
        security_keywords = [
            'vulnerability', 'exploit', 'scan', 'recon', 'pentest',
            'subdomain', 'port', 'service', 'cve', 'ioc',
            'attack', 'payload', 'shell', 'privilege', 'escalation',
            'sql injection', 'xss', 'csrf', 'rce', 'lfi', 'rfi',
            'authentication', 'authorization', 'bypass', 'crack',
            'hash', 'password', 'token', 'session', 'cookie'
        ]
        
        for keyword in security_keywords:
            if keyword in text_lower:
                keywords.append(keyword)
        
        # Extract tool names (common security tools)
        tool_patterns = [
            r'\bnmap\b', r'\bwhois\b', r'\bsubfinder\b', r'\bamass\b',
            r'\bmetasploit\b', r'\bsqlmap\b', r'\bburp\b', r'\bowasp\b',
            r'\bnikto\b', r'\bdirb\b', r'\bdirbuster\b', r'\bhydra\b'
        ]
        
        for pattern in tool_patterns:
            matches = re.findall(pattern, text_lower)
            keywords.extend(matches)
        
        return list(set(keywords))  # Deduplicate
    
    def extract_topics_from_context(self,
                                   contexts: List[Dict[str, Any]],
                                   max_topics: int = 10) -> List[str]:
        """Extract topics from retrieved contexts.
        
        Args:
            contexts: List of context documents
            max_topics: Maximum number of topics to extract
            
        Returns:
            List of topic strings
        """
        # Combine all context documents
        all_text = " ".join([
            ctx.get("document", "") for ctx in contexts
        ])
        
        return self.extract_topics_from_text(all_text, max_topics=max_topics)
    
    def extract_topics_from_text(self,
                                 text: str,
                                 max_topics: int = 10) -> List[str]:
        """Extract topics from text.
        
        Args:
            text: Text to extract topics from
            max_topics: Maximum number of topics to extract
            
        Returns:
            List of topic strings
        """
        # Extract entities
        entities = self.ranker._extract_entities(text)
        
        # Extract keywords
        keywords = self._extract_keywords(text)
        
        # Combine
        topics = entities + keywords
        
        # Count frequency
        topic_counts = Counter(topics)
        
        # Return top topics
        return [topic for topic, count in topic_counts.most_common(max_topics)]
    
    def match_topics(self,
                    query_topics: List[str],
                    context_topics: List[str]) -> float:
        """Calculate topic match score.
        
        Args:
            query_topics: Topics from query
            context_topics: Topics from context
            
        Returns:
            Match score (0.0 to 1.0)
        """
        if not query_topics or not context_topics:
            return 0.0
        
        # Normalize to lowercase
        query_topics_lower = [t.lower() for t in query_topics]
        context_topics_lower = [t.lower() for t in context_topics]
        
        # Count matches
        matches = sum(1 for qt in query_topics_lower if qt in context_topics_lower)
        
        # Score = matches / max(query_topics, context_topics)
        max_topics = max(len(query_topics_lower), len(context_topics_lower))
        if max_topics == 0:
            return 0.0
        
        return matches / max_topics
