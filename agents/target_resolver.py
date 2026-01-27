
import re
import logging
import socket
from typing import List, Dict, Any, Optional, Set
from memory.session import AgentContext
from memory.manager import MemoryManager

class TargetSetResolver:
    """
    Hybrid Retrieval-Augmented Target Resolver (Memory Fusion).
    
    Implements Memory Fusion across 3 layers:
    - L1: Redis/RAM (Short-term session context)
    - L2: Postgres/Findings (Long-term structured results)
    - L3: PGVector/Context (Semantic recall)
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.logger = logging.getLogger(__name__)

    def resolve_targets(self, prompt: str, initial_targets: List[str] = None) -> List[str]:
        """
        Perform Memory Fusion to resolve all applicable targets.
        """
        targets = set(initial_targets or [])
        prompt_lower = prompt.lower()
        conversation_id = self.memory_manager.conversation_id
        
        # 1. Determine Scope (Root Domain)
        # Try to get verified target from memory if root_domain is not set
        root_domain = self.memory_manager.target_domain
        if not root_domain:
            root_domain = self.memory_manager.get_verified_target(conversation_id=conversation_id)
            if root_domain:
                self.memory_manager.target_domain = root_domain
                
        if not root_domain and initial_targets:
            root_domain = initial_targets[0] # Best guess
            
        # 2. Layer 1: Session Context (Redis/RAM)
        self._resolve_from_session(prompt_lower, targets)
        
        # 3. Layer 2: Postgres Findings (Historical)
        # Always try to resolve from findings if we have a conversation_id, 
        # even if root_domain is still None (it might be found in findings)
        self._resolve_from_findings(prompt_lower, root_domain, targets)
        
        # 4. Layer 3: Semantic Recall (VectorDB)
        self._resolve_from_vector(prompt_lower, conversation_id, targets)
        
        # 5. Deduplicate and Validate
        final_targets = self._filter_and_validate(targets, root_domain)
        
        return final_targets

    def _resolve_from_session(self, prompt: str, targets: Set[str]):
        """Resolve targets from active session context."""
        ctx = self.memory_manager.get_agent_context()
        if not ctx:
            return
            
        # Context keywords to fields mapping
        mappings = {
            "subdomain": ctx.subdomains,
            "finding": ctx.subdomains,
            "asset": ctx.subdomains,
            "open port": [p.get("host") for p in ctx.open_ports if p.get("host")],
            "service": [p.get("host") for p in ctx.open_ports if p.get("host")],
            "ip": ctx.ips,
            "address": ctx.ips
        }
        
        for keyword, data in mappings.items():
            if keyword in prompt:
                for item in data:
                    if item: targets.add(item)

    def _resolve_from_findings(self, prompt: str, root_domain: str, targets: Set[str]):
        """Resolve targets from persistent findings database."""
        if not root_domain:
            return
            
        # Keywords that trigger "all subdomains" or "all hosts"
        trigger_keywords = ["subdomain", "host", "finding", "discovered", "all", "previous"]
        if not any(k in prompt for k in trigger_keywords):
            return
            
        try:
            results = self.memory_manager.results_storage.retrieve_results(
                query=f"subdomains of {root_domain}",
                conversation_id=self.memory_manager.conversation_id,
                k=100
            )
            
            for res in results:
                data = res.get("results") or {}
                if isinstance(data, dict):
                    if "subdomains" in data:
                        for s in data["subdomains"]: targets.add(s)
                    if "hosts" in data:
                        for h in data["hosts"]: targets.add(h)
                    if "target" in data and isinstance(data["target"], str):
                        targets.add(data["target"])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, str) and "." in item:
                            targets.add(item)
        except Exception as e:
            self.logger.error(f"Error resolving from findings: {e}")

    def _resolve_from_vector(self, prompt: str, conversation_id: str, targets: Set[str]):
        """Resolve targets from semantic memory search."""
        if not conversation_id:
            return
            
        # Semantic trigger keywords
        semantic_keywords = ["previous", "earlier", "yesterday", "last", "mentioned", "before"]
        if not any(k in prompt for k in semantic_keywords):
            return
            
        try:
            # Search context for target-like strings
            context = self.memory_manager.conversation_retriever.retrieve_context(
                query=prompt,
                conversation_id=conversation_id,
                k=5
            )
            
            # Simple regex to find domains/IPs in semantic results
            pattern = r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b|\b(?:\d{1,3}\.){3}\d{1,3}\b'
            for res in context:
                doc = res.get("document", "")
                matches = re.findall(pattern, doc, re.IGNORECASE)
                for m in matches:
                    targets.add(m)
        except Exception as e:
            self.logger.error(f"Error resolving from vector: {e}")

    def _filter_and_validate(self, targets: Set[str], root_domain: str) -> List[str]:
        """Cleanup and filter targets based on root domain scope."""
        valid = []
        pattern = r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b|\b(?:\d{1,3}\.){3}\d{1,3}\b'
        
        for t in targets:
            if not t or not isinstance(t, str):
                continue
            
            # Normalize
            t = t.strip().lower()
            
            # Basic format check
            if not re.match(pattern, t):
                continue
                
            # Root domain scope check (simple suffix check)
            if root_domain and root_domain in t:
                valid.append(t)
            elif not root_domain:
                valid.append(t)
                
        # Return sorted list for determinism
        return sorted(list(set(valid)))

    def resolve_to_ips(self, targets: List[str]) -> Dict[str, List[str]]:
        """
        Group targets by their resolved IPv4 addresses.
        Returns: { ip: [domain1, domain2, ...] }
        """
        ip_map = {}
        for target in targets:
            # If target is already an IP
            if re.match(r'^(?:\d{1,3}\.){3}\d{1,3}$', target):
                if self._is_valid_public_ip(target):
                    ip_map.setdefault(target, []).append(target)
                continue
                
            # If target is a domain, resolve it
            try:
                ip = socket.gethostbyname(target)
                if self._is_valid_public_ip(ip):
                    ip_map.setdefault(ip, []).append(target)
                else:
                    self.logger.warning(f"Skipping internal/resolver IP: {ip} for {target}")
            except (socket.gaierror, socket.timeout):
                self.logger.debug(f"Could not resolve {target}")
                continue
                
        return ip_map

    def _is_valid_public_ip(self, ip: str) -> bool:
        """Filter out loopback, private, and system resolver IPs."""
        if not ip: return False
        
        # System resolver often seen in logs
        if ip == "127.0.0.53": return False
        
        # Loopback
        if ip.startswith("127."): return False
        
        return True
