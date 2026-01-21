"""Memory Manager for Firestarter.

Combines Vector DB (semantic) and session memory for intelligent context management.
Adapted from rutx with enhancements for firestarter architecture.

Production Architecture:
- Persistent conversation buffer (PostgreSQL)
- Summary compression for long conversations
- Multi-conversation namespace isolation
- Agent state persistence
"""

import uuid
import warnings
from datetime import datetime
from typing import Optional, List, Dict, Any
from collections import defaultdict

from memory.session import SessionMemory, AgentContext
from memory.conversation_store import ConversationStore
from memory.summary_compressor import SummaryCompressor
from memory.namespace_manager import NamespaceManager
from memory.redis_buffer import RedisBuffer

# Lazy imports to avoid circular dependency
# from rag.retriever import ConversationRetriever
# from rag.results_storage import ToolResultsStorage


class MemoryManager:
    """
    Combined memory manager for firestarter.
    
    Production Architecture:
    - Persistent conversation buffer (PostgreSQL via ConversationStore)
    - Summary compression for long conversations
    - Multi-conversation namespace isolation
    - Agent state persistence
    
    Legacy Support:
    - Still supports session_id for backward compatibility
    - In-memory buffers maintained during transition period
    """
    
    def __init__(self, auto_cleanup_days: int = 30):
        """Initialize memory manager.
        
        Args:
            auto_cleanup_days: Days to retain old data (default: 30)
        """
        # Lazy import to avoid circular dependency
        from rag.retriever import ConversationRetriever
        from rag.results_storage import ToolResultsStorage
        
        self.conversation_retriever = ConversationRetriever()
        self.results_storage = ToolResultsStorage()
        self.auto_cleanup_days = auto_cleanup_days
        
        # Production: Persistent storage
        self.conversation_store = ConversationStore()
        self.summary_compressor = SummaryCompressor()
        self.namespace_manager = NamespaceManager()
        
        # Short-term buffer (Redis)
        self.redis_buffer = RedisBuffer()
        
        # Current conversation/session
        self.conversation_id: Optional[str] = None
        self.session_id: Optional[str] = None  # Legacy support
        self.target_domain: Optional[str] = None
        
        # Session memory (volatile, but can be persisted)
        self.session_memory: Optional[SessionMemory] = None
        
        # Legacy: Conversation buffer (short-term memory) - in-memory storage
        # DEPRECATED: Will be removed after migration to Redis
        # Key: session_id, Value: List of messages
        self._conversation_buffers: Dict[str, List[Dict[str, Any]]] = {}
        
        # Legacy: Verified targets (persisted per session)
        # DEPRECATED: Now stored in PostgreSQL conversations table
        # Key: session_id, Value: verified domain
        self._verified_targets: Dict[str, str] = {}
    
    # ==================== Conversation/Session Management ====================
    
    def start_conversation(self, title: Optional[str] = None, target_domain: Optional[str] = None) -> str:
        """
        Start a new conversation (production method).
        
        Args:
            title: Optional conversation title
            target_domain: Optional target domain
            
        Returns:
            conversation_id (UUID string)
        """
        # Create conversation in PostgreSQL
        self.conversation_id = self.conversation_store.create_conversation(title=title)
        
        # Legacy: Also create session_id for backward compatibility
        self.session_id = str(uuid.uuid4())
        
        # Update conversation with session_id for migration
        try:
            # Store session_id in conversation metadata for migration
            import psycopg2
            import os
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DATABASE", "firestarter_pg"),
                user=os.getenv("POSTGRES_USER", "firestarter_ad"),
                password=os.getenv("POSTGRES_PASSWORD", "")
            )
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations SET session_id = %s WHERE id = %s
            """, (self.session_id, self.conversation_id))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            pass  # Non-critical
        
        self.target_domain = target_domain
        
        # Initialize session memory
        self.session_memory = SessionMemory(session_id=self.conversation_id)  # Use conversation_id
        if target_domain:
            self.session_memory.agent_context.domain = target_domain
            self.conversation_store.update_verified_target(self.conversation_id, target_domain)
        
        return self.conversation_id
    
    def start_session(self, target_domain: str = None) -> str:
        """
        Start a new session (legacy method, creates conversation internally).
        
        DEPRECATED: Use start_conversation() instead.
        
        Args:
            target_domain: Optional target domain
            
        Returns:
            Session ID (legacy) - also creates conversation_id internally
        """
        warnings.warn(
            "start_session() is deprecated. Use start_conversation() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Create conversation internally
        self.start_conversation(target_domain=target_domain)
        return self.session_id  # Return legacy session_id
    
    def get_or_create_session(self, target_domain: str = None) -> str:
        """Get current session or create new one (legacy method)."""
        if self.session_id:
            return self.session_id
        return self.start_session(target_domain)
    
    def switch_conversation(self, conversation_id: str):
        """
        Switch to different conversation (context switch).
        
        Args:
            conversation_id: Conversation UUID to switch to
        """
        # Load conversation context
        context = self.namespace_manager.load_conversation_context(conversation_id)
        
        if not context:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        # Update current conversation
        self.conversation_id = conversation_id
        conversation = context.get("conversation", {})
        self.session_id = conversation.get("session_id")  # Legacy support
        self.target_domain = conversation.get("verified_target")
        
        # Load agent state
        agent_state = context.get("agent_state")
        if agent_state:
            # Reconstruct SessionMemory from state
            session_memory_data = agent_state.get("session_memory")
            if session_memory_data:
                # Reconstruct from dict (simplified, full implementation would use from_dict)
                self.session_memory = SessionMemory(session_id=conversation_id)
                if isinstance(session_memory_data, dict):
                    agent_context_data = session_memory_data.get("agent_context", {})
                    if agent_context_data:
                        self.session_memory.agent_context.domain = agent_context_data.get("domain", "")
                        # Load other fields as needed
                        if "subdomains" in agent_context_data:
                            self.session_memory.agent_context.subdomains = agent_context_data.get("subdomains", [])
                        if "ips" in agent_context_data:
                            self.session_memory.agent_context.ips = agent_context_data.get("ips", [])
                        if "open_ports" in agent_context_data:
                            self.session_memory.agent_context.open_ports = agent_context_data.get("open_ports", [])
                        if "vulnerabilities" in agent_context_data:
                            self.session_memory.agent_context.vulnerabilities = agent_context_data.get("vulnerabilities", [])
                        if "active_entities" in agent_context_data:
                            for entity in agent_context_data.get("active_entities", []):
                                self.session_memory.agent_context.add_active_entity(entity)
                        if "open_tasks" in agent_context_data:
                            for task in agent_context_data.get("open_tasks", []):
                                self.session_memory.agent_context.add_open_task(task)
                        if "topics" in agent_context_data:
                            self.session_memory.agent_context.add_topics(agent_context_data.get("topics", []))
        
        # Load topics, active entities, and open tasks from context (if not in agent state)
        topics = context.get("topics", [])
        active_entities = context.get("active_entities", [])
        open_tasks = context.get("open_tasks", [])
        
        if topics and not self.session_memory.agent_context.topics:
            self.session_memory.agent_context.add_topics(topics)
        if active_entities:
            for entity in active_entities:
                self.session_memory.agent_context.add_active_entity(entity)
        if open_tasks:
            for task in open_tasks:
                self.session_memory.agent_context.add_open_task(task)
        
        # Update target domain
        if self.target_domain:
            self.session_memory.agent_context.domain = self.target_domain
            self.session_memory.agent_context.add_active_entity(self.target_domain)
    
    def get_session_memory(self) -> Optional[SessionMemory]:
        """Get current session memory."""
        return self.session_memory
    
    def get_agent_context(self) -> Optional[AgentContext]:
        """Get current agent context."""
        if self.session_memory:
            return self.session_memory.agent_context
        return None
    
    # ==================== Message Handling ====================
    
    def save_turn(
        self,
        user_message: str,
        assistant_message: str,
        tools_used: List[str] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        context: Dict = None
    ):
        """
        Save a conversation turn (user + assistant).
        
        Saves to both Vector DB (for semantic search), session memory, and conversation buffer.
        
        Args:
            user_message: User message
            assistant_message: Assistant response
            tools_used: List of tools used
            session_id: Session identifier (legacy, uses current if None)
            conversation_id: Conversation identifier (preferred)
            context: Additional context
        """
        # Determine conversation_id
        conv_id = conversation_id or self.conversation_id
        if not conv_id:
            # Create conversation if doesn't exist
            conv_id = self.start_conversation()
        
        session = session_id or self.session_id or self.get_or_create_session()
        domain = context.get("target_domain") if context else self.target_domain
        
        try:
            self.conversation_store.add_message(conv_id, "user", user_message)
            self.conversation_store.add_message(conv_id, "assistant", assistant_message)
            # Auto-compress if needed
            self.summary_compressor.auto_compress_if_needed(conv_id)
        except Exception:
            # Fallback to legacy in-memory buffer
            self.add_to_conversation_buffer(session, "user", user_message, conversation_id=conv_id)
            self.add_to_conversation_buffer(session, "assistant", assistant_message, conversation_id=conv_id)
        
        # Save to Redis buffer (short-term memory)
        try:
            self.redis_buffer.add_message(conv_id, "user", user_message)
            self.redis_buffer.add_message(conv_id, "assistant", assistant_message)
        except Exception:
            pass  # Non-critical, Redis is optional
        
        # Save to Vector DB for semantic search (long-term memory)
        # Use conversation_id for namespace isolation
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message}
        ]
        # TODO: Update to use conversation_id when ConversationRetriever is updated
        self.conversation_retriever.add_conversation(messages, session_id=conv_id)  # Using conv_id as session_id for now
        
        # Update session memory
        if self.session_memory:
            if tools_used:
                for tool in tools_used:
                    self.session_memory.agent_context.add_tool_run(tool)
            
            if domain:
                self.session_memory.agent_context.domain = domain
                # Add domain as active entity
                self.session_memory.agent_context.add_active_entity(domain)
                # Also save as verified target if it's a clear domain
                if "." in domain:  # Valid domain format
                    self.save_verified_target(session_id=session, domain=domain, conversation_id=conv_id)
            
            # Extract and add topics from messages if not already present
            if not self.session_memory.agent_context.topics:
                from rag.topic_extractor import TopicExtractor
                extractor = TopicExtractor()
                # Extract topics from recent messages
                recent_messages = [
                    {"content": user_message},
                    {"content": assistant_message}
                ]
                topics = extractor.extract_topics(recent_messages, max_topics=5)
                if topics:
                    self.session_memory.agent_context.add_topics(topics)
        
        # Persist agent state (PostgreSQL + Redis)
        if self.session_memory:
            try:
                state_data = {
                    "session_memory": self.session_memory.to_dict(),
                    "agent_context": self.session_memory.agent_context.to_dict()
                }
                # Save to PostgreSQL (persistent)
                self.namespace_manager.save_agent_state(conv_id, "session_memory", state_data)
                # Save to Redis (short-term, faster access)
                self.redis_buffer.set_state(conv_id, "agent_context", self.session_memory.agent_context.to_dict())
            except Exception:
                pass  # Non-critical
    
    # ==================== Context Retrieval ====================
    
    def retrieve_context(
        self,
        query: str,
        k: int = 5,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        include_tool_results: bool = True,
        include_buffer: bool = True,
        task_type: Optional[str] = None,
        use_ranking: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context for a query with optional multi-factor ranking.
        
        Args:
            query: Search query
            k: Number of results
            session_id: Session identifier (legacy)
            conversation_id: Conversation identifier (preferred)
            include_tool_results: Whether to include tool results
            include_buffer: Whether to include conversation buffer
            task_type: Optional task type for relevance scoring (recon, exploitation, analysis, mixed)
            use_ranking: Whether to use ContextRanker for multi-factor ranking (default: True)
            
        Returns:
            Dictionary with conversation_context, tool_results, and conversation_buffer
        """
        session = session_id or self.session_id
        conv_id = conversation_id or self.conversation_id or session
        
        # Get conversation context (semantic search from vector DB with ranking)
        conversation_context = self.conversation_retriever.retrieve_context(
            query=query,
            k=k,
            session_id=session,
            conversation_id=conv_id,
            task_type=task_type,
            use_ranking=use_ranking
        )
        
        # Get tool results if requested (with ranking if enabled)
        tool_results = []
        if include_tool_results:
            tool_results = self.results_storage.retrieve_results(
                query=query,
                k=k,
                session_id=session,
                conversation_id=conv_id
            )
            
            # Apply ranking to tool results if enabled
            if use_ranking and tool_results:
                from rag.context_ranker import ContextRanker
                ranker = ContextRanker()
                query_entities = ranker._extract_entities(query)
                ranked_tool_results = ranker.rank_contexts(
                    query=query,
                    contexts=tool_results,
                    query_entities=query_entities,
                    task_type=task_type
                )
                tool_results = ranker.get_top_k(ranked_tool_results, k=k, min_score=0.0)
        
        # Get conversation buffer (full history)
        # Priority: Redis (short-term) -> PostgreSQL (persistent) -> Legacy in-memory
        conversation_buffer = []
        if include_buffer:
            conversation_buffer = self.get_conversation_buffer(session_id=session, conversation_id=conv_id)
        
        return {
            "conversation_context": conversation_context,
            "tool_results": tool_results,
            "conversation_buffer": conversation_buffer,
            "session_memory": self.session_memory.to_dict() if self.session_memory else None,
            "verified_target": self.get_verified_target(session, conversation_id=conv_id)
        }
    
    # ==================== Agent Context Updates ====================
    
    def update_agent_context(self, updates: Dict[str, Any]):
        """Update agent context with new findings.
        
        Args:
            updates: Dictionary with context updates (subdomains, ports, vulns, etc.)
        """
        if not self.session_memory:
            self.get_or_create_session()
        
        ctx = self.session_memory.agent_context
        
        # Update subdomains
        if "subdomains" in updates:
            ctx.add_subdomains(updates["subdomains"])
            # Add subdomains as active entities
            for subdomain in updates["subdomains"]:
                ctx.add_active_entity(subdomain)
        
        # Update IPs
        if "ips" in updates:
            for ip in updates["ips"]:
                ctx.add_ip(ip)
                # Add IPs as active entities
                ctx.add_active_entity(ip)
        
        # Update ports
        if "open_ports" in updates:
            for port_info in updates["open_ports"]:
                ctx.add_port(
                    host=port_info.get("host", ""),
                    port=port_info.get("port", 0),
                    service=port_info.get("service", ""),
                    version=port_info.get("version", "")
                )
        
        # Update vulnerabilities
        if "vulnerabilities" in updates:
            for vuln in updates["vulnerabilities"]:
                ctx.add_vulnerability(
                    vuln_type=vuln.get("type", ""),
                    target=vuln.get("target", ""),
                    severity=vuln.get("severity", "medium"),
                    cve=vuln.get("cve", ""),
                    details=vuln.get("details", {})
                )
        
        # Update technologies
        if "technologies" in updates:
            for tech in updates["technologies"]:
                ctx.add_technology(tech)
        
        # Update open tasks
        if "open_tasks" in updates:
            for task in updates["open_tasks"]:
                ctx.add_open_task(task)
        
        # Update topics
        if "topics" in updates:
            ctx.add_topics(updates["topics"])
    
    def get_context_summary(self) -> str:
        """Get a summary of current context."""
        if not self.session_memory:
            return "No active session"
        
        return self.session_memory.agent_context.get_summary()
    
    # ==================== Conversation Buffer (Short-Term Memory) ====================
    
    def get_conversation_buffer(self, session_id: Optional[str] = None, conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get full conversation buffer for a session/conversation.
        
        Priority: Redis buffer (short-term) -> PostgreSQL (persistent) -> Legacy in-memory
        
        Args:
            session_id: Session identifier (legacy, uses current if None)
            conversation_id: Conversation identifier (preferred)
            
        Returns:
            List of conversation messages (role, content)
        """
        # Determine conversation_id
        conv_id = conversation_id or self.conversation_id
        
        # Try Redis buffer first (short-term memory)
        if conv_id:
            try:
                redis_messages = self.redis_buffer.get_recent_messages(conv_id, n=self.redis_buffer.max_messages)
                if redis_messages:
                    return redis_messages
            except Exception:
                pass
        
        # Try PostgreSQL (persistent storage)
        if conv_id:
            try:
                messages = self.conversation_store.get_messages(conv_id)
                # Convert to legacy format
                return [{"role": msg.get("role"), "content": msg.get("content")} for msg in messages]
            except Exception:
                pass
        
        # Fallback to legacy in-memory buffer
        session = session_id or self.session_id
        if not session:
            return []
        
        # Legacy: Return in-memory buffer
        return self._conversation_buffers.get(session, [])
    
    def add_to_conversation_buffer(self,
                                   session_id: Optional[str],
                                   role: str,
                                   content: str,
                                   conversation_id: Optional[str] = None):
        """
        Add a message to conversation buffer.
        
        Saves to: Redis buffer (short-term) -> PostgreSQL (persistent) -> Legacy in-memory
        
        Args:
            session_id: Session identifier (legacy)
            role: Message role ("user" or "assistant")
            content: Message content
            conversation_id: Conversation identifier (preferred)
        """
        # Determine conversation_id
        conv_id = conversation_id or self.conversation_id
        
        # Save to Redis buffer (short-term memory)
        if conv_id:
            try:
                self.redis_buffer.add_message(conv_id, role, content)
            except Exception:
                pass  # Non-critical
        
        # Save to PostgreSQL (persistent storage)
        if conv_id:
            try:
                self.conversation_store.add_message(conv_id, role, content)
                # Auto-compress if needed
                self.summary_compressor.auto_compress_if_needed(conv_id)
            except Exception:
                pass
        
        # Fallback to legacy in-memory buffer
        session = session_id or self.get_or_create_session()
        
        if session not in self._conversation_buffers:
            self._conversation_buffers[session] = []
        
        self._conversation_buffers[session].append({
            "role": role,
            "content": content
        })
    
    def clear_conversation_buffer(self, session_id: Optional[str] = None, conversation_id: Optional[str] = None):
        """Clear conversation buffer for a session/conversation."""
        # Clear Redis buffer
        conv_id = conversation_id or self.conversation_id
        if conv_id:
            try:
                self.redis_buffer.clear_messages(conv_id)
            except Exception:
                pass
        
        # Clear legacy in-memory buffer
        session = session_id or self.session_id
        if session and session in self._conversation_buffers:
            del self._conversation_buffers[session]
    
    # ==================== Verified Target Management ====================
    
    def save_verified_target(self, session_id: Optional[str] = None, domain: str = None, 
                            conversation_id: Optional[str] = None, structured_info: Optional[Dict] = None):
        """
        Save verified target domain for a session/conversation.
        
        Args:
            session_id: Session identifier (legacy)
            domain: Verified domain name
            conversation_id: Conversation identifier (preferred)
            structured_info: Optional structured target info dict with:
                - legal_name: str
                - country: str
                - domain: str
                - asn: Optional[str]
                - ip_ranges: List[str]
                - confidence: float
        """
        # Try conversation_id first (production)
        if conversation_id and domain:
            try:
                self.conversation_store.update_verified_target(conversation_id, domain, structured_info=structured_info)
                self.target_domain = domain
                # Also update session memory
                if self.session_memory:
                    self.session_memory.agent_context.domain = domain
                    # Update structured fields if available
                    if structured_info:
                        if hasattr(self.session_memory.agent_context, 'legal_name'):
                            self.session_memory.agent_context.legal_name = structured_info.get("legal_name", "")
                        if hasattr(self.session_memory.agent_context, 'target_country'):
                            self.session_memory.agent_context.target_country = structured_info.get("country", "")
                return
            except Exception:
                pass
        
        # Fallback to legacy in-memory storage
        session = session_id or self.get_or_create_session()
        if session and domain:
            self._verified_targets[session] = domain
            
            # Also update session memory
            if self.session_memory:
                self.session_memory.agent_context.domain = domain
                self.target_domain = domain
                # Update structured fields if available
                if structured_info:
                    if hasattr(self.session_memory.agent_context, 'legal_name'):
                        self.session_memory.agent_context.legal_name = structured_info.get("legal_name", "")
                    if hasattr(self.session_memory.agent_context, 'target_country'):
                        self.session_memory.agent_context.target_country = structured_info.get("country", "")
    
    def get_verified_target(self, session_id: Optional[str] = None, conversation_id: Optional[str] = None,
                           structured: bool = False) -> Optional[Any]:
        """
        Get verified target domain for a session/conversation.
        
        Args:
            session_id: Session identifier (legacy, uses current if None)
            conversation_id: Conversation identifier (preferred)
            structured: If True, return structured dict; if False, return domain string (backward compatible)
            
        Returns:
            Verified domain (str) or structured dict, or None
        """
        # Try conversation_id first (production)
        if conversation_id:
            try:
                return self.conversation_store.get_verified_target(conversation_id, structured=structured)
            except Exception:
                pass
        
        # Fallback to legacy in-memory storage
        session = session_id or self.session_id
        if not session:
            return None
        
        # Check verified targets dict first
        verified = self._verified_targets.get(session)
        if verified:
            if structured:
                # Return simple structured dict for legacy data
                return {
                    "domain": verified,
                    "legal_name": "",
                    "country": "",
                    "asn": None,
                    "ip_ranges": [],
                    "confidence": 0.5
                }
            return verified
        
        # Fallback to session memory
        if self.session_memory and self.session_memory.agent_context.domain:
            domain = self.session_memory.agent_context.domain
            if structured:
                # Return structured dict from session memory if available
                return {
                    "domain": domain,
                    "legal_name": getattr(self.session_memory.agent_context, 'legal_name', ''),
                    "country": getattr(self.session_memory.agent_context, 'target_country', ''),
                    "asn": None,
                    "ip_ranges": [],
                    "confidence": 0.5
                }
            return domain
        
        return None
    
    def clear_verified_target(self, session_id: Optional[str] = None):
        """Clear verified target for a session."""
        session = session_id or self.session_id
        if session and session in self._verified_targets:
            del self._verified_targets[session]


# Singleton instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get singleton memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
