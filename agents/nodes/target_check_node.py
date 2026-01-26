"""Target check and confirmation detection nodes.

Handles target ambiguity checking and user confirmation detection.
"""

from typing import Dict, Any, Optional, Callable
import re


class TargetCheckNode:
    """Handles target checking and confirmation detection."""
    
    def __init__(self,
                 memory_manager,
                 input_normalizer,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None):
        """Initialize target check node.
        
        Args:
            memory_manager: Memory manager for verified targets
            input_normalizer: Input normalizer for target extraction
            stream_callback: Optional callback for streaming events
        """
        self.memory_manager = memory_manager
        self.input_normalizer = input_normalizer
        self.stream_callback = stream_callback
    
    def check_target(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Check if target is ambiguous.
        
        Args:
            state: Graph state
            
        Returns:
            Updated state with target_clarification
        """
        # First check if target already verified
        conversation_id = state.get("conversation_id") or state.get("session_id")
        verified_target = self.memory_manager.get_verified_target(
            session_id=conversation_id,
            conversation_id=conversation_id if state.get("conversation_id") else None
        )
        
        if verified_target:
            state["target_clarification"] = self._create_verified_clarification(verified_target)
            self._update_session_context(state, verified_target)
            return state
        
        # No verified target, check for ambiguity
        user_prompt = state["user_prompt"]
        conversation_context = self._get_conversation_context(state)
        
        ambiguity_check = self.input_normalizer.is_target_ambiguous(
            user_prompt, 
            conversation_context=conversation_context
        )
        
        state["target_clarification"] = ambiguity_check
        return state
    
    def detect_confirmation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Detect user confirmation responses.
        
        Checks if user is confirming a previously suggested domain.
        
        Args:
            state: Graph state
            
        Returns:
            Updated state
        """
        user_prompt = state["user_prompt"].lower().strip()
        conversation_history = state.get("conversation_history", [])
        
        # Check if user input is a confirmation
        if not self._is_confirmation(user_prompt):
            return state
        
        # Look for previously suggested domain
        suggested_domain = self._find_suggested_domain(conversation_history, state)
        
        if suggested_domain:
            self._save_verified_target(state, suggested_domain)
            self._update_clarification(state, suggested_domain)
            # Update user prompt to include verified domain
            state["user_prompt"] = f"{state['user_prompt']} {suggested_domain}"
        
        return state
    
    def _create_verified_clarification(self, verified_target: str) -> Dict[str, Any]:
        """Create clarification dict for verified target."""
        return {
            "is_ambiguous": False,
            "verified_domain": verified_target,
            "has_domain": True,
            "has_ip": False,
            "has_url": False,
            "potential_targets": [verified_target],
            "suggested_questions": [],
            "can_search": False,
            "search_context": {}
        }
    
    def _get_conversation_context(self, state: Dict[str, Any]) -> Optional[str]:
        """Get conversation context for semantic understanding."""
        conversation_history = state.get("conversation_history", [])
        if not conversation_history:
            return None
        
        recent_messages = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
        return " ".join([
            msg.get("content", "") 
            for msg in recent_messages 
            if isinstance(msg, dict)
        ])
    
    def _update_session_context(self, state: Dict[str, Any], target: str) -> None:
        """Update session context with verified target."""
        if self.memory_manager.session_memory:
             self.memory_manager.session_memory.agent_context.domain = target
             state["session_context"] = self.memory_manager.session_memory.agent_context.to_dict()
    
    def _is_confirmation(self, user_prompt: str) -> bool:
        """Check if user input is a confirmation."""
        confirmation_keywords = [
            "yes", "correct", "right", "that's right", "that is correct",
            "yes it is", "yes it's", "yes its", "yep", "yeah", "ok", "okay",
            "confirmed", "confirm", "that's it", "that is it", "exactly"
        ]
        return any(keyword in user_prompt for keyword in confirmation_keywords)
    
    def _find_suggested_domain(self, conversation_history: list, state: Dict[str, Any]) -> Optional[str]:
        """Find previously suggested domain from conversation history."""
        domain_pattern = r'\b([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.(?:[a-zA-Z]{2,}|co\.(?:za|uk|jp|kr|nz|au)))\b'
        
        # Check assistant's last message
        for msg in reversed(conversation_history):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                matches = re.findall(domain_pattern, content)
                if matches:
                    return matches[0]
        
        # Check target_clarification
        clarification = state.get("target_clarification", {})
        return clarification.get("verified_domain")
    
    def _save_verified_target(self, state: Dict[str, Any], domain: str) -> None:
        """Save verified target to memory."""
        conversation_id = state.get("conversation_id") or state.get("session_id")
        
        self.memory_manager.save_verified_target(
            session_id=conversation_id,
            domain=domain,
            conversation_id=conversation_id if state.get("conversation_id") else None
        )
        
        self._update_session_context(state, domain)
    
    def _update_clarification(self, state: Dict[str, Any], domain: str) -> None:
        """Update target clarification with verified domain."""
        clarification = state.get("target_clarification", {})
        clarification["is_ambiguous"] = False
        clarification["verified_domain"] = domain
        state["target_clarification"] = clarification
