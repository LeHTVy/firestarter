"""Session Memory - In-Session Context for LLM & Agents.

This module provides VOLATILE memory for the current session:
- Shared context between all agents
- Attack facts and hypotheses
- LLM context window management

This is DIFFERENT from Conversation History (persistent storage) which is PERSISTENT.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from uuid import uuid4
import json
import re
from urllib.parse import urlparse


@dataclass
class AgentContext:
    """
    Shared context that all agents can read/write.
    This is the "message board" for inter-agent communication.
    """
    
    # Target info
    domain: str = ""
    targets: List[str] = field(default_factory=list)
    
    # Structured target info (for enhanced verification)
    legal_name: str = ""
    target_country: str = ""
    target_asn: Optional[str] = None
    target_ip_ranges: List[str] = field(default_factory=list)
    
    # Phase 1: Recon findings
    subdomains: List[str] = field(default_factory=list)
    ips: List[str] = field(default_factory=list)
    asns: List[Dict] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    dns_records: List[Dict] = field(default_factory=list)
    
    # Phase 2: Scan findings
    open_ports: List[Dict] = field(default_factory=list)  # {port, host, ip, protocol, service, version, fingerprint}
    services: List[Dict] = field(default_factory=list)
    directories: List[str] = field(default_factory=list)
    endpoints: List[str] = field(default_factory=list)
    
    # Phase 3: Vulnerability findings
    vulnerabilities: List[Dict] = field(default_factory=list)  # {type, severity, target, cve}
    misconfigs: List[Dict] = field(default_factory=list)
    cves: List[str] = field(default_factory=list)
    
    # Phase 4: Exploitation findings
    exploits_attempted: List[Dict] = field(default_factory=list)
    successful_exploits: List[Dict] = field(default_factory=list)
    credentials: List[Dict] = field(default_factory=list)  # {username, password, service}
    shells: List[Dict] = field(default_factory=list)  # {type, host, access_level}
    
    # Phase 5: Post-exploitation
    privilege_escalations: List[Dict] = field(default_factory=list)
    lateral_movements: List[Dict] = field(default_factory=list)
    persistence: List[Dict] = field(default_factory=list)
    
    # Metadata
    tools_run: List[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Active entities and open tasks (for conversation switching)
    active_entities: List[str] = field(default_factory=list)  
    open_tasks: List[Dict[str, Any]] = field(default_factory=list)  
    topics: List[str] = field(default_factory=list)  
    
    # Authorized scope (for policy enforcement)
    authorized_scope: List[str] = field(default_factory=list)  
    
    def add_subdomain(self, subdomain: str):
        """Add a subdomain if not already present."""
        if subdomain and subdomain not in self.subdomains:
            self.subdomains.append(subdomain)
            self._touch()
    
    def add_subdomains(self, subdomains: List[str]):
        """Add multiple subdomains."""
        for s in subdomains:
            self.add_subdomain(s)
    
    def add_ip(self, ip: str):
        """Add an IP if not already present."""
        if ip and ip not in self.ips:
            self.ips.append(ip)
            self._touch()
    
    def add_port(self, host: str, port: int, protocol: str = "tcp", service: str = "", ip: str = "", version: str = "", fingerprint: str = ""):
        """Add an open port finding."""
        entry = {
            "host": host, 
            "ip": ip or host, # Fallback to host if ip unknown
            "port": port, 
            "protocol": protocol,
            "service": service, 
            "version": version,
            "fingerprint": fingerprint
        }
        if entry not in self.open_ports:
            self.open_ports.append(entry)
            self._touch()
    
    def add_vulnerability(self, vuln_type: str, target: str, severity: str = "medium", 
                         cve: str = "", details: Dict = None):
        """Add a vulnerability finding."""
        entry = {
            "type": vuln_type,
            "target": target,
            "severity": severity,
            "cve": cve,
            "details": details or {}
        }
        self.vulnerabilities.append(entry)
        if cve and cve not in self.cves:
            self.cves.append(cve)
        self._touch()
    
    def add_technology(self, tech: str):
        """Add detected technology."""
        if tech and tech not in self.technologies:
            self.technologies.append(tech)
            self._touch()
    
    def add_tool_run(self, tool: str):
        """Record that a tool was run."""
        if tool and tool not in self.tools_run:
            self.tools_run.append(tool)
            self._touch()
    
    def add_active_entity(self, entity: str):
        """Add an active entity (domain, IP) being worked on."""
        if entity and entity not in self.active_entities:
            self.active_entities.append(entity)
            self._touch()
    
    def remove_active_entity(self, entity: str):
        """Remove an active entity."""
        if entity in self.active_entities:
            self.active_entities.remove(entity)
            self._touch()
    
    def add_open_task(self, task: Dict[str, Any]):
        """Add an open task (subtask not yet completed)."""
        task_id = task.get("id")
        if task_id:
            self.open_tasks = [t for t in self.open_tasks if t.get("id") != task_id]
            self.open_tasks.append(task)
            self._touch()
    
    def complete_task(self, task_id: str):
        """Mark a task as completed."""
        self.open_tasks = [t for t in self.open_tasks if t.get("id") != task_id]
        self._touch()
    
    def add_topic(self, topic: str):
        """Add a conversation topic."""
        if topic and topic not in self.topics:
            self.topics.append(topic)
            self._touch()
    
    def add_topics(self, topics: List[str]):
        """Add multiple topics."""
        for topic in topics:
            self.add_topic(topic)
    
    def _touch(self):
        """Update last_updated timestamp."""
        self.last_updated = datetime.now().isoformat()
    
    def get_targets_for_scanning(self) -> List[str]:
        """Get all targets (domain + subdomains + IPs) for scanning."""
        targets = set()
        if self.domain:
            targets.add(self.domain)
        targets.update(self.subdomains)
        targets.update(self.ips)
        return list(targets)
    
    def get_high_value_targets(self) -> List[str]:
        """Get high-value targets (admin panels, APIs, etc.)."""
        high_value = []
        keywords = ["admin", "api", "login", "auth", "dashboard", "manage", "portal"]
        
        for sub in self.subdomains:
            if any(kw in sub.lower() for kw in keywords):
                high_value.append(sub)
        
        for endpoint in self.endpoints:
            if any(kw in endpoint.lower() for kw in keywords):
                high_value.append(endpoint)
        
        return high_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "domain": self.domain,
            "targets": self.targets,
            "legal_name": self.legal_name,
            "target_country": self.target_country,
            "target_asn": self.target_asn,
            "target_ip_ranges": self.target_ip_ranges,
            "subdomains": self.subdomains,
            "ips": self.ips,
            "technologies": self.technologies,
            "open_ports": self.open_ports,
            "services": self.services,
            "vulnerabilities": self.vulnerabilities,
            "cves": self.cves,
            "tools_run": self.tools_run,
            "last_updated": self.last_updated,
            "active_entities": self.active_entities,
            "open_tasks": self.open_tasks,
            "topics": self.topics,
            "authorized_scope": self.authorized_scope,
        }
    
    def get_summary(self) -> str:
        """Get a brief summary of findings."""
        parts = []
        if self.domain:
            parts.append(f"Target: {self.domain}")
        if self.subdomains:
            parts.append(f"Subdomains: {len(self.subdomains)}")
        if self.ips:
            parts.append(f"IPs: {len(self.ips)}")
        if self.open_ports:
            parts.append(f"Open ports: {len(self.open_ports)}")
        if self.vulnerabilities:
            parts.append(f"Vulnerabilities: {len(self.vulnerabilities)}")
        if self.tools_run:
            parts.append(f"Tools run: {', '.join(self.tools_run[-5:])}")
        if self.tools_run:
            parts.append(f"Tools run: {', '.join(self.tools_run[-5:])}")
        return " | ".join(parts) if parts else "No findings yet"

    def get_target(self) -> Optional[str]:
        """
        Get the prioritized target.
        
        Priority order:
        1. domain (explicitly verified)
        2. Last active entity that looks like a domain
        3. First IP in ips
        """
        if self.domain and self._is_valid_domain(self.domain):
            return self.domain
        
        # Check active entities for domains
        for entity in reversed(self.active_entities):
            if self._is_valid_domain(entity):
                return entity
                
        # Fallback to IPs
        if self.ips and self._is_valid_ip(self.ips[0]):
            return self.ips[0]
            
        return None
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Check if string looks like a valid domain."""
        if not domain:
            return False
        pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Check if string looks like a valid IP."""
        if not ip:
            return False
        pattern = r'^(?:\d{1,3}\.){3}\d{1,3}$'
        return bool(re.match(pattern, ip))


@dataclass
class Fact:
    """
    A single normalized observation from a tool.
    Facts are atomic units of knowledge that can be queried.
    """
    id: str
    fact_type: str  # "open_port", "subdomain", "vulnerability", "service", "technology"
    target: str     # IP/domain this fact relates to
    data: Dict[str, Any]  # Structured data
    source_tool: str      # Which tool produced this
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = 1.0  # Confidence level (0.0-1.0)


@dataclass
class SessionMemory:
    """
    Volatile in-session memory for current pentest session.
    
    This is different from persistent storage - it's cleared when session ends.
    """
    session_id: str = field(default_factory=lambda: str(uuid4()))
    agent_context: AgentContext = field(default_factory=AgentContext)
    facts: List[Fact] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_fact(self, fact: Fact):
        """Add a fact to the session."""
        self.facts.append(fact)
        self.updated_at = datetime.now().isoformat()
    
    def get_facts_by_type(self, fact_type: str) -> List[Fact]:
        """Get all facts of a specific type."""
        return [f for f in self.facts if f.fact_type == fact_type]
    
    def get_facts_by_target(self, target: str) -> List[Fact]:
        """Get all facts related to a target."""
        return [f for f in self.facts if f.target == target]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "agent_context": self.agent_context.to_dict(),
            "facts": [{"id": f.id, "type": f.fact_type, "target": f.target, "data": f.data, "source": f.source_tool} for f in self.facts],
            "hypotheses": self.hypotheses,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


# =============================================================================
# Structured Interaction Logic (User Request)
# =============================================================================

@dataclass
class InteractionItem:
    """
    A single structured unit of interaction (Prompt + Response + Outcome).
    Represents a 'thought unit' or a complete turn broken down.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Raw Content
    role: str = "user"  # user, assistant, system
    content: str = ""
    
    # Structured Analysis
    intents: List[str] = field(default_factory=list)      # What was the goal?
    facts: List[Dict] = field(default_factory=list)       # What facts were discovered?
    tool_outputs: List[Dict] = field(default_factory=list)# Raw tool outputs
    
    # Context
    session_id: str = ""
    conversation_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "role": self.role,
            "content": self.content,
            "intents": self.intents,
            "facts": self.facts,
            "tool_outputs": self.tool_outputs,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InteractionItem':
        item = cls(
            id=data.get("id", str(uuid4())),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            role=data.get("role", "user"),
            content=data.get("content", ""),
            session_id=data.get("session_id", ""),
            conversation_id=data.get("conversation_id", "")
        )
        item.intents = data.get("intents", [])
        item.facts = data.get("facts", [])
        item.tool_outputs = data.get("tool_outputs", [])
        return item


class SessionProcessor:
    """
    Central processor for session interactions.
    
    Responsibilities:
    1. Breakdown inputs (prompt/response/tools) into structured items.
    2. Coordinate persistence across 3 memory layers:
       - Redis (Short-term buffer)
       - PostgreSQL (Long-term history)
       - VectorDB (Semantic search)
    """
    
    def __init__(self, 
                 redis_buffer,
                 conversation_store,
                 vector_store):
        """
        Initialize with references to memory stores.
        
        Args:
            redis_buffer: RedisBuffer instance
            conversation_store: ConversationStore instance
            vector_store: PgVectorStore instance
        """
        self.redis_buffer = redis_buffer
        self.conversation_store = conversation_store
        self.vector_store = vector_store
        
    def breakdown_turn(self, 
                      user_input: str, 
                      model_response: str, 
                      tool_outputs: List[Dict[str, Any]],
                      context: Dict[str, Any]) -> List[InteractionItem]:
        """
        Break down a conversation turn into structured interaction items.
        
        Args:
            user_input: Raw user prompt
            model_response: Raw model text response
            tool_outputs: List of tool execution results
            context: Session context (ids, etc)
            
        Returns:
            List of InteractionItems (usually User Item + Assistant Item)
        """
        items = []
        session_id = context.get("session_id", "")
        conversation_id = context.get("conversation_id", "")
        
        # 1. Process User Input
        user_item = InteractionItem(
            role="user",
            content=user_input,
            session_id=session_id,
            conversation_id=conversation_id,
            intents=self._extract_intents(user_input) # Simple heuristic or extraction logic
        )
        items.append(user_item)
        
        # 2. Process Assistant Output + Tools
        assistant_facts = []
        
        # Extract facts from tool outputs
        for tool_out in tool_outputs:
            if tool_out.get("success"):
                results = tool_out.get("results")
                # Normalize outcomes into generic facts
                if isinstance(results, dict):
                    # Flat extraction of keys as facts
                    assistant_facts.append({
                        "source": tool_out.get("tool_name"),
                        "data": results,
                        "type": "tool_finding"
                    })
                elif isinstance(results, str):
                    assistant_facts.append({
                        "source": tool_out.get("tool_name"),
                        "snippet": results[:200], # Trucate for summary
                        "type": "tool_output"
                    })

        assistant_item = InteractionItem(
            role="assistant",
            content=model_response,
            session_id=session_id,
            conversation_id=conversation_id,
            facts=assistant_facts,
            tool_outputs=tool_outputs
        )
        items.append(assistant_item)
        
        return items

    def process_and_save(self, 
                        user_input: str, 
                        model_response: str, 
                        tool_outputs: List[Dict[str, Any]],
                        context: Dict[str, Any]):
        """
        Main entry point: Breakdown and Save to all layers.
        """
        # 1. Breakdown
        items = self.breakdown_turn(user_input, model_response, tool_outputs, context)
        
        # 2. Persist
        for item in items:
            self.save_item(item)
            
    def save_item(self, item: InteractionItem):
        """
        Save a single item to all memory layers.
        """
        # Layer 1: Redis (Short-term / Fast Recall)
        # We store the full item dict for quick reconstruction
        try:
            # Add to message list for potential "replay" or context window
            # Storing as special "interaction_item" type in Redis
            item_key = f"interaction:{item.id}"
            self.redis_buffer.set_state(
                item.conversation_id, 
                item_key, 
                item.to_dict(), 
                ttl=86400 # 24h retention
            )
            # Also push to standard message buffer for compatibility
            self.redis_buffer.add_message(
                item.conversation_id, 
                item.role, 
                item.content, 
                metadata={"item_id": item.id, "intents": item.intents, "has_facts": bool(item.facts)}
            )
        except Exception:
            pass # Redis is optional/cache
            
        # Layer 2: PostgreSQL (Long-term / Source of Truth)
        try:
            # We use the existing add_message but enrich metadata
            self.conversation_store.add_message(
                item.conversation_id,
                item.role,
                item.content,
                metadata={
                    "item_id": item.id,
                    "intents": item.intents,
                    "facts_count": len(item.facts),
                    "tool_outputs_count": len(item.tool_outputs),
                    # We might not store full facts/tools in msg metadata to keep it light,
                    # but for now it helps "rehydration".
                    "structured_facts": item.facts 
                }
            )
        except Exception as e:
            print(f"Error saving to Postgres: {e}")

        # Layer 3: VectorDB (Semantic Search / RAG)
        try:
            # We embed the content AND the structured facts if meaningful
            text_to_embed = item.content
            if item.facts:
                # Append facts text for better semantic matching
                facts_text = "\nFound Facts:\n" + "\n".join([str(f) for f in item.facts])
                text_to_embed += facts_text
            
            self.vector_store.add_documents(
                texts=[text_to_embed],
                metadatas=[{
                    "item_id": item.id,
                    "role": item.role,
                    "conversation_id": item.conversation_id,
                    "intents": item.intents,
                    "timestamp": item.timestamp
                }],
                ids=[item.id]
            )
        except Exception as e:
            print(f"Error saving to VectorDB: {e}")

    def recall(self, query: str, conversation_id: str, limit: int = 5) -> List[InteractionItem]:
        """
        Smart recall: Check Redis -> VectorDB -> Postgres.
        """
        results = []
        
        # 1. Try Vector Search (Semantic)
        try:
            vector_results = self.vector_store.similarity_search(
                query, 
                k=limit, 
                filter={"conversation_id": conversation_id}
            )
            
            for res in vector_results:
                # Rehydrate from metadata/content
                meta = res.get("metadata", {})
                item = InteractionItem(
                    id=res.get("id"),
                    role=meta.get("role", "unknown"),
                    content=res.get("document", ""), # This might contain appended facts
                    conversation_id=conversation_id,
                    intents=meta.get("intents", [])
                )
                results.append(item)
        except Exception as e:
            print(f"Recall error: {e}")
            
        return results

    def _extract_intents(self, text: str) -> List[str]:
        """
        Basic intent extraction (Keyword/Regex based for now).
        Could be upgraded to LLM classifier.
        """
        intents = []
        lower_text = text.lower()
        if "scan" in lower_text or "assess" in lower_text:
            intents.append("recon")
        if "exploit" in lower_text or "attack" in lower_text:
            intents.append("exploitation")
        if "summary" in lower_text or "show me" in lower_text:
            intents.append("reporting")
        return intents
