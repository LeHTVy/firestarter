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
    open_ports: List[Dict] = field(default_factory=list)  # {port, service, version, host}
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
    active_entities: List[str] = field(default_factory=list)  # Domains, IPs currently being worked on
    open_tasks: List[Dict[str, Any]] = field(default_factory=list)  # Subtasks not yet completed
    topics: List[str] = field(default_factory=list)  # Conversation topics
    
    # Authorized scope (for policy enforcement)
    authorized_scope: List[str] = field(default_factory=list)  # Authorized targets (domains, IPs)
    
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
    
    def add_port(self, host: str, port: int, service: str = "", version: str = ""):
        """Add an open port finding."""
        entry = {"host": host, "port": port, "service": service, "version": version}
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
            # Remove existing task with same ID if present
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
        return " | ".join(parts) if parts else "No findings yet"


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
