"""Context Manager - Immutable Snapshots & Semantic Memory.

This module implements the logic for creating immutable snapshots of the session
state at each turn and storing them in pgvector for semantic recall.

Key concepts:
- Snapshot: A frozen state of the session at a specific turn.
- turn_id: Monotonically increasing ID for each interaction.
- pgvector: Stores the embedding of each snapshot.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import uuid
import hashlib

# Lazy imports to avoid circular deps
# from memory.manager import MemoryManager 

@dataclass
class SessionSnapshot:
    """Immutable snapshot of a conversation turn."""
    id: str
    session_id: str
    turn_id: int
    user_intent: Dict[str, Any]
    agent_plan: Dict[str, Any]
    tool_execution: List[Dict[str, Any]]
    model_response: str
    reasoning_summary: str = ""
    confidence: float = 0.0
    snapshot_hash: str = field(init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __post_init__(self):
        """Compute hash after initialization."""
        self.snapshot_hash = self._compute_hash()
        
    def _compute_hash(self) -> str:
        """Compute SHA256 hash to ensure immutability."""
        try:
            # Sort keys for consistent hashing
            content = f"{self.session_id}:{self.turn_id}:{json.dumps(self.user_intent, sort_keys=True)}:{self.model_response}"
            return hashlib.sha256(content.encode()).hexdigest()
        except Exception:
            return str(uuid.uuid4())
    
    def to_text_representation(self) -> str:
        """Convert snapshot to text for embedding."""
        try:
            intent_str = json.dumps(self.user_intent)
            plan_str = json.dumps(self.agent_plan)
            tools_str = json.dumps([
                {
                    "tool": t.get("tool"), 
                    "stdout": t.get("stdout", "")[:200]  # Truncate for embedding
                } 
                for t in self.tool_execution
            ])
            
            return f"""
            User Intent: {intent_str}
            Agent Plan: {plan_str}
            Tools: {tools_str}
            Response: {self.model_response[:500]}
            """.strip()
        except Exception:
            return f"Snapshot {self.id} (Error serializing)"


class ContextManager:
    """Manages session snapshots and semantic memory."""
    
    def __init__(self, memory_manager):
        """Initialize with memory manager reference."""
        self.memory_manager = memory_manager
        # self.vector_store references the underlying pgvector store via memory_manager
        
    def create_snapshot(self, 
                       session_id: str,
                       turn_id: int,
                       user_input: str,
                       model_response: str,
                       tool_outputs: List[Dict[str, Any]],
                       agent_plan: Optional[Dict[str, Any]] = None,
                       reasoning_summary: str = "",
                       confidence: float = 1.0) -> SessionSnapshot:
        """Create and save a new snapshot."""
        
        # 1. Normalize User Intent (Mock logic or use IntentClassifier result if passed)
        user_intent = {
            "request": user_input,
            "task": "unknown", # TODO: Extract from classifier
            "target": self.memory_manager.get_verified_target(conversation_id=session_id)
        }
        
        # 2. Normalize Plan
        plan = agent_plan or {"selected_agent": "unknown", "subtasks": []}
        
        # 3. Create Snapshot Object
        snapshot = SessionSnapshot(
            id=str(uuid.uuid4()),
            session_id=session_id,
            turn_id=turn_id,
            user_intent=user_intent,
            agent_plan=plan,
            tool_execution=tool_outputs,
            model_response=model_response,
            reasoning_summary=reasoning_summary,
            confidence=confidence
        )
        
        # 4. Save to Vector Store (pgvector)
        self._save_to_vector_store(snapshot)
        
        return snapshot

    def _save_to_vector_store(self, snapshot: SessionSnapshot):
        """Embed and save snapshot to pgvector."""
        try:
            vector_store = self.memory_manager.conversation_retriever.vectorstore
            
            text = snapshot.to_text_representation()
            metadata = {
                "snapshot_id": snapshot.id,
                "session_id": snapshot.session_id,
                "turn_id": snapshot.turn_id,
                "type": "snapshot",
                "reasoning_summary": snapshot.reasoning_summary,
                "confidence": snapshot.confidence,
                "hash": snapshot.snapshot_hash,
                "timestamp": snapshot.timestamp
            }
            
            vector_store.add_documents(
                texts=[text],
                metadatas=[metadata],
                ids=[snapshot.id]
            )
            
        except Exception as e:
            print(f"Failed to save snapshot to vector store: {e}")

    def recall_similar_snapshots(self, query: str, session_id: Optional[str] = None, k: int = 3):
        """Retrieve similar past snapshots."""
        try:
            vector_store = self.memory_manager.conversation_retriever.vectorstore
            return vector_store.similarity_search(query, k=k)
            
        except Exception:
            return []
