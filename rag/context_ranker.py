"""Context Ranker with Multi-Factor Scoring Algorithm.

Implements weighted scoring for context retrieval:
final_score = α * semantic_similarity + β * recency + γ * entity_match + δ * task_relevance
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import re
import math


class ContextRanker:
    """Rank context documents using multi-factor scoring algorithm."""
    
    def __init__(self,
                 alpha: float = 0.4,  # Semantic similarity weight
                 beta: float = 0.3,   # Recency weight
                 gamma: float = 0.2,  # Entity match weight
                 delta: float = 0.1):  # Task relevance weight
        """Initialize context ranker.
        
        Args:
            alpha: Weight for semantic similarity (default: 0.4)
            beta: Weight for recency (default: 0.3)
            gamma: Weight for entity match (default: 0.2)
            delta: Weight for task relevance (default: 0.1)
        """
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.delta = delta
        
        # Normalize weights to sum to 1.0
        total = alpha + beta + gamma + delta
        if total > 0:
            self.alpha = alpha / total
            self.beta = beta / total
            self.gamma = gamma / total
            self.delta = delta / total
    
    def rank_contexts(self,
                     query: str,
                     contexts: List[Dict[str, Any]],
                     query_entities: Optional[List[str]] = None,
                     task_type: Optional[str] = None,
                     current_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Rank contexts using multi-factor scoring.
        
        Args:
            query: User query
            contexts: List of context documents with:
                - document: str (text content)
                - metadata: dict (with timestamp, entities, type, etc.)
                - distance: float (semantic similarity distance from vector search)
            query_entities: Optional list of entities extracted from query
            task_type: Optional task type (recon, exploitation, analysis, mixed)
            current_time: Optional current time for recency calculation (default: now)
            
        Returns:
            Ranked list of contexts with final_score added
        """
        if not contexts:
            return []
        
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        # Extract entities from query if not provided
        if query_entities is None:
            query_entities = self._extract_entities(query)
        
        # Calculate scores for each context
        scored_contexts = []
        for context in contexts:
            # Get semantic similarity (from vector search distance)
            # Distance is 1 - similarity, so similarity = 1 - distance
            distance = context.get('distance', 1.0)
            semantic_similarity = max(0.0, min(1.0, 1.0 - distance))
            
            # Calculate recency score
            recency_score = self._calculate_recency_score(
                context.get('metadata', {}),
                current_time
            )
            
            # Calculate entity match score
            entity_score = self._calculate_entity_match_score(
                query_entities,
                context.get('document', ''),
                context.get('metadata', {})
            )
            
            # Calculate task relevance score
            task_score = self._calculate_task_relevance_score(
                task_type,
                context.get('metadata', {})
            )
            
            # Calculate final weighted score
            final_score = (
                self.alpha * semantic_similarity +
                self.beta * recency_score +
                self.gamma * entity_score +
                self.delta * task_score
            )
            
            # Add scores to context
            scored_context = context.copy()
            scored_context['final_score'] = final_score
            scored_context['scores'] = {
                'semantic_similarity': semantic_similarity,
                'recency': recency_score,
                'entity_match': entity_score,
                'task_relevance': task_score
            }
            scored_contexts.append(scored_context)
        
        # Sort by final score (descending)
        scored_contexts.sort(key=lambda x: x.get('final_score', 0.0), reverse=True)
        
        return scored_contexts
    
    def _calculate_recency_score(self,
                                metadata: Dict[str, Any],
                                current_time: datetime) -> float:
        """Calculate recency score based on timestamp.
        
        Args:
            metadata: Context metadata with timestamp
            current_time: Current time for comparison
            
        Returns:
            Recency score (0.0 to 1.0, where 1.0 is most recent)
        """
        # Try to get timestamp from metadata
        timestamp_str = metadata.get('timestamp') or metadata.get('created_at')
        if not timestamp_str:
            # No timestamp - return neutral score (0.5)
            return 0.5
        
        try:
            # Parse timestamp (support ISO format)
            if isinstance(timestamp_str, str):
                # Try parsing ISO format
                if 'T' in timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    # Try other formats
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            else:
                timestamp = timestamp_str
            
            # Ensure timezone-aware
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            # Calculate time difference in hours
            time_diff = (current_time - timestamp).total_seconds() / 3600.0
            
            # Exponential decay: score = e^(-time_diff / half_life)
            # half_life = 24 hours (score halves every 24 hours)
            half_life = 24.0
            recency_score = math.exp(-time_diff / half_life)
            
            # Normalize to 0.0-1.0 range
            return max(0.0, min(1.0, recency_score))
        except Exception:
            # Error parsing timestamp - return neutral score
            return 0.5
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract entities from text (domains, IPs, tools, etc.).
        
        Args:
            text: Text to extract entities from
            
        Returns:
            List of extracted entities
        """
        entities = []
        text_lower = text.lower()
        
        # Extract domains
        domain_pattern = r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+'
        domains = re.findall(domain_pattern, text)
        entities.extend([d.lower() for d in domains])
        
        # Extract IPs
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        ips = re.findall(ip_pattern, text)
        entities.extend(ips)
        
        # Extract common tool names (from context)
        tool_keywords = ['nmap', 'whois', 'subfinder', 'amass', 'masscan', 'ps', 'finder', 'mass']
        for tool in tool_keywords:
            if tool in text_lower:
                entities.append(tool)
        
        # Extract CVE numbers
        cve_pattern = r'CVE-\d{4}-\d{4,}'
        cves = re.findall(cve_pattern, text, re.IGNORECASE)
        entities.extend([cve.upper() for cve in cves])
        
        # Deduplicate
        return list(set(entities))
    
    def _calculate_entity_match_score(self,
                                     query_entities: List[str],
                                     document_text: str,
                                     metadata: Dict[str, Any]) -> float:
        """Calculate entity match score.
        
        Args:
            query_entities: Entities extracted from query
            document_text: Document text content
            metadata: Document metadata (may contain entities)
            
        Returns:
            Entity match score (0.0 to 1.0)
        """
        if not query_entities:
            return 0.5  # Neutral score if no entities in query
        
        # Extract entities from document
        doc_entities = self._extract_entities(document_text)
        
        # Also check metadata for entities
        if 'entities' in metadata:
            if isinstance(metadata['entities'], list):
                doc_entities.extend([e.lower() if isinstance(e, str) else str(e).lower() for e in metadata['entities']])
            elif isinstance(metadata['entities'], str):
                doc_entities.extend(self._extract_entities(metadata['entities']))
        
        # Check for tool_name in metadata (tool results)
        if 'tool_name' in metadata:
            doc_entities.append(metadata['tool_name'].lower())
        
        # Check for domain/IP in metadata
        if 'domain' in metadata:
            doc_entities.append(str(metadata['domain']).lower())
        if 'target' in metadata:
            doc_entities.append(str(metadata['target']).lower())
        
        # Normalize entities (lowercase)
        query_entities_lower = [e.lower() for e in query_entities]
        doc_entities_lower = [e.lower() for e in doc_entities]
        
        # Calculate match ratio
        if not doc_entities_lower:
            return 0.0
        
        # Count matches
        matches = sum(1 for qe in query_entities_lower if qe in doc_entities_lower)
        
        # Score = matches / max(query_entities, doc_entities)
        # Weighted by importance: domain > IP > tool
        weighted_matches = 0
        weighted_total = 0
        
        for qe in query_entities_lower:
            # Determine entity importance
            if self._is_domain(qe):
                weight = 3.0
            elif self._is_ip(qe):
                weight = 2.0
            elif self._is_cve(qe):
                weight = 2.5
            else:
                weight = 1.0
            
            weighted_total += weight
            if qe in doc_entities_lower:
                weighted_matches += weight
        
        if weighted_total == 0:
            return 0.0
        
        entity_score = weighted_matches / weighted_total
        return max(0.0, min(1.0, entity_score))
    
    def _is_domain(self, text: str) -> bool:
        """Check if text is a domain."""
        domain_pattern = r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$'
        return bool(re.match(domain_pattern, text))
    
    def _is_ip(self, text: str) -> bool:
        """Check if text is an IP address."""
        ip_pattern = r'^(?:\d{1,3}\.){3}\d{1,3}$'
        return bool(re.match(ip_pattern, text))
    
    def _is_cve(self, text: str) -> bool:
        """Check if text is a CVE number."""
        cve_pattern = r'^CVE-\d{4}-\d{4,}$'
        return bool(re.match(cve_pattern, text, re.IGNORECASE))
    
    def _calculate_task_relevance_score(self,
                                       task_type: Optional[str],
                                       metadata: Dict[str, Any]) -> float:
        """Calculate task relevance score.
        
        Args:
            task_type: Task type from query (recon, exploitation, analysis, mixed)
            metadata: Context metadata (may contain type, tool_name, etc.)
            
        Returns:
            Task relevance score (0.0 to 1.0)
        """
        if not task_type:
            return 0.5  # Neutral score if no task type specified
        
        task_type_lower = task_type.lower()
        context_type = metadata.get('type', '').lower()
        tool_name = metadata.get('tool_name', '').lower()
        
        # Map task types to context types and tools
        task_mappings = {
            'recon': {
                'context_types': ['conversation', 'tool_result'],
                'tools': ['nmap', 'whois', 'subfinder', 'amass', 'masscan', 'ps', 'finder', 'mass', 'dns', 'port']
            },
            'exploitation': {
                'context_types': ['tool_result', 'knowledge'],
                'tools': ['metasploit', 'exploit', 'payload', 'vulnerability']
            },
            'analysis': {
                'context_types': ['tool_result', 'knowledge', 'conversation'],
                'tools': ['analysis', 'vulnerability', 'scanner', 'log']
            },
            'mixed': {
                'context_types': ['conversation', 'tool_result', 'knowledge'],
                'tools': []  # All tools relevant
            }
        }
        
        mapping = task_mappings.get(task_type_lower, {})
        context_types = mapping.get('context_types', [])
        tools = mapping.get('tools', [])
        
        score = 0.0
        
        # Check context type match
        if context_type in context_types:
            score += 0.5
        
        # Check tool match
        if tools:
            if any(tool in tool_name for tool in tools):
                score += 0.5
        else:
            # Mixed task - all tools relevant
            if tool_name:
                score += 0.3
        
        # If no specific match, check if it's a general conversation
        if not score and context_type == 'conversation':
            score = 0.3  # General relevance
        
        return max(0.0, min(1.0, score))
    
    def get_top_k(self,
                 ranked_contexts: List[Dict[str, Any]],
                 k: int,
                 min_score: float = 0.0) -> List[Dict[str, Any]]:
        """Get top-k contexts with minimum score threshold.
        
        Args:
            ranked_contexts: Ranked list of contexts
            k: Number of top contexts to return
            min_score: Minimum final score threshold (default: 0.0)
            
        Returns:
            Top-k contexts that meet minimum score
        """
        filtered = [
            ctx for ctx in ranked_contexts
            if ctx.get('final_score', 0.0) >= min_score
        ]
        return filtered[:k]
