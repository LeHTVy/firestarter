"""Autonomy Controller - Controls AI automation levels.

Provides a gate between "AI thinking" and "AI acting", allowing:
- Level 0 (MANUAL): All actions require user confirmation
- Level 1 (COPILOT): Recon auto, exploit/pivot require confirmation  
- Level 2 (SEMI_AUTO): Recon + Scan auto, exploit requires confirmation
- Level 3 (FULL_AUTO): Full autonomous red team mode

This enables seamless switching between Copilot and Autonomous Red Team modes,
supporting enterprise compliance and audit requirements.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Optional, List, Callable, Any
from datetime import datetime
import json


class AutonomyLevel(IntEnum):
    """Autonomy level enum."""
    MANUAL = 0       # All actions require confirmation
    COPILOT = 1      # Recon auto, rest needs confirmation
    SEMI_AUTO = 2    # Recon + Scan auto, exploit needs confirmation
    FULL_AUTO = 3    # Full autonomous mode


# Human-readable level descriptions
LEVEL_DESCRIPTIONS = {
    AutonomyLevel.MANUAL: "Manual - All actions require user confirmation",
    AutonomyLevel.COPILOT: "Copilot - Recon auto, exploits need approval",
    AutonomyLevel.SEMI_AUTO: "Semi-Auto - Recon + Scan auto, exploits need approval",
    AutonomyLevel.FULL_AUTO: "Full Auto - Autonomous Red Team mode"
}


@dataclass
class AutonomyPolicy:
    """Defines which actions require which autonomy level."""
    action_levels: Dict[str, AutonomyLevel] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.action_levels:
            self.action_levels = {
                # Information gathering - most permissive (Level 1: COPILOT)
                "recon": AutonomyLevel.COPILOT,
                "whois": AutonomyLevel.COPILOT,
                "dns": AutonomyLevel.COPILOT,
                "subdomain": AutonomyLevel.COPILOT,
                "theharvester": AutonomyLevel.COPILOT,
                "amass": AutonomyLevel.COPILOT,
                "shodan": AutonomyLevel.COPILOT,
                "censys": AutonomyLevel.COPILOT,
                
                # Scanning - medium (Level 2: SEMI_AUTO)
                "scan": AutonomyLevel.SEMI_AUTO,
                "nmap": AutonomyLevel.SEMI_AUTO,
                "nikto": AutonomyLevel.SEMI_AUTO,
                "wpscan": AutonomyLevel.SEMI_AUTO,
                "nuclei": AutonomyLevel.SEMI_AUTO,
                "vuln_scan": AutonomyLevel.SEMI_AUTO,
                "gobuster": AutonomyLevel.SEMI_AUTO,
                "dirbuster": AutonomyLevel.SEMI_AUTO,
                "ffuf": AutonomyLevel.SEMI_AUTO,
                
                # Exploitation - requires full auto (Level 3: FULL_AUTO)
                "exploit": AutonomyLevel.FULL_AUTO,
                "metasploit": AutonomyLevel.FULL_AUTO,
                "sqlmap": AutonomyLevel.FULL_AUTO,
                "hydra": AutonomyLevel.FULL_AUTO,
                "pivot": AutonomyLevel.FULL_AUTO,
                "lateral_move": AutonomyLevel.FULL_AUTO,
                "exfiltrate": AutonomyLevel.FULL_AUTO,
                "privilege_escalation": AutonomyLevel.FULL_AUTO,
            }
    
    def get_required_level(self, action: str) -> AutonomyLevel:
        """Get required level for action.
        
        Args:
            action: Action/tool name
            
        Returns:
            Required AutonomyLevel for this action
        """
        action_lower = action.lower()
        
        # Direct match
        if action_lower in self.action_levels:
            return self.action_levels[action_lower]
        
        # Partial match (e.g., "nmap_scan" matches "nmap")
        for key, level in self.action_levels.items():
            if key in action_lower or action_lower in key:
                return level
        
        # Default to FULL_AUTO for unknown actions (safest)
        return AutonomyLevel.FULL_AUTO


class AutonomyController:
    """Controls AI automation level with user confirmation gating.
    
    This is the central control point for determining whether an action
    can be automatically executed or requires user confirmation.
    
    Usage:
        controller = get_autonomy_controller()
        controller.set_level(AutonomyLevel.COPILOT)
        
        # Check if action can auto-execute
        can_exec, msg = controller.gate("nmap", context={"target": "example.com"})
        if not can_exec:
            # Ask user for confirmation
            approved = controller.request_confirmation("nmap", context)
    """
    
    def __init__(self, 
                 level: AutonomyLevel = AutonomyLevel.COPILOT,
                 policy: Optional[AutonomyPolicy] = None,
                 confirm_callback: Optional[Callable[[str, Dict], str]] = None):
        """Initialize autonomy controller.
        
        Args:
            level: Default autonomy level
            policy: Custom policy (uses default if None)
            confirm_callback: Callback function for user confirmation prompts
        """
        self.level = level
        self.policy = policy or AutonomyPolicy()
        self.confirm_callback = confirm_callback
        
        # Per-conversation level overrides
        self._conversation_levels: Dict[str, AutonomyLevel] = {}
        
        # Audit log for compliance
        self.audit_log: List[Dict[str, Any]] = []
    
    def get_level(self, conversation_id: Optional[str] = None) -> AutonomyLevel:
        """Get autonomy level for conversation.
        
        Args:
            conversation_id: Optional conversation ID for per-conversation levels
            
        Returns:
            Current AutonomyLevel
        """
        if conversation_id and conversation_id in self._conversation_levels:
            return self._conversation_levels[conversation_id]
        return self.level
    
    def get_level_description(self, conversation_id: Optional[str] = None) -> str:
        """Get human-readable description of current level."""
        level = self.get_level(conversation_id)
        return LEVEL_DESCRIPTIONS.get(level, f"Unknown level: {level}")
    
    def set_level(self, level: AutonomyLevel, 
                  conversation_id: Optional[str] = None) -> None:
        """Set autonomy level.
        
        Args:
            level: New autonomy level
            conversation_id: Optional conversation ID for per-conversation levels
        """
        old_level = self.get_level(conversation_id)
        
        if conversation_id:
            self._conversation_levels[conversation_id] = level
        else:
            self.level = level
        
        self._log_audit("level_change", {
            "old_level": old_level.name,
            "new_level": level.name,
            "conversation_id": conversation_id
        })
    
    def can_execute(self, action: str, 
                    conversation_id: Optional[str] = None) -> bool:
        """Check if action can be auto-executed at current level.
        
        Args:
            action: Action/tool name to check
            conversation_id: Optional conversation ID
            
        Returns:
            True if action can auto-execute, False if needs confirmation
        """
        current_level = self.get_level(conversation_id)
        required_level = self.policy.get_required_level(action)
        return current_level >= required_level
    
    def gate(self, action: str, 
             context: Optional[Dict[str, Any]] = None,
             conversation_id: Optional[str] = None) -> tuple:
        """Gate function - decide to auto-execute or ask user.
        
        This is the main entry point for checking whether an action
        should proceed automatically or needs user confirmation.
        
        Args:
            action: Action/tool name
            context: Optional context dict with target, parameters, etc.
            conversation_id: Optional conversation ID
            
        Returns:
            Tuple of (can_proceed: bool, message: str)
        """
        current_level = self.get_level(conversation_id)
        required_level = self.policy.get_required_level(action)
        
        if current_level >= required_level:
            self._log_audit("auto_execute", {
                "action": action,
                "level": current_level.name,
                "required_level": required_level.name,
                "context": context,
                "conversation_id": conversation_id
            })
            return True, f"✅ Auto-executing: {action} (level {current_level.name})"
        
        # Need confirmation
        self._log_audit("confirmation_required", {
            "action": action,
            "current_level": current_level.name,
            "required_level": required_level.name,
            "context": context,
            "conversation_id": conversation_id
        })
        
        return False, (
            f"⚠️ Action '{action}' requires level {required_level.name}, "
            f"current level is {current_level.name}. User confirmation needed."
        )
    
    def request_confirmation(self, action: str, 
                            context: Optional[Dict[str, Any]] = None) -> bool:
        """Request user confirmation for gated action.
        
        Args:
            action: Action/tool name
            context: Optional context dict
            
        Returns:
            True if user approves, False otherwise
        """
        if self.confirm_callback:
            message = f"Execute {action}?"
            if context:
                target = context.get("target", "unknown")
                message = f"Execute {action} on {target}?"
            
            response = self.confirm_callback(message, context or {})
            approved = response.lower() in ["yes", "y", "ok", "approve", ""]
            
            self._log_audit("user_response", {
                "action": action,
                "approved": approved,
                "response": response,
                "context": context
            })
            return approved
        
        # No callback - default deny for safety
        return False
    
    def get_actions_for_level(self, level: AutonomyLevel) -> List[str]:
        """Get list of actions allowed at a specific level.
        
        Args:
            level: Autonomy level to check
            
        Returns:
            List of action names allowed at this level
        """
        allowed = []
        for action, required_level in self.policy.action_levels.items():
            if level >= required_level:
                allowed.append(action)
        return sorted(allowed)
    
    def _log_audit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log audit event for compliance.
        
        Args:
            event_type: Type of event (level_change, auto_execute, etc.)
            data: Event data
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            **data
        }
        self.audit_log.append(entry)
        
        # Keep last 1000 entries to prevent memory issues
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
        """
        return self.audit_log[-limit:]
    
    def export_audit_log(self, filepath: str) -> None:
        """Export audit log to JSON file.
        
        Args:
            filepath: Path to output file
        """
        with open(filepath, 'w') as f:
            json.dump(self.audit_log, f, indent=2, default=str)


# Singleton instance
_autonomy_controller: Optional[AutonomyController] = None


def get_autonomy_controller() -> AutonomyController:
    """Get global autonomy controller instance.
    
    Returns:
        Singleton AutonomyController instance
    """
    global _autonomy_controller
    if _autonomy_controller is None:
        _autonomy_controller = AutonomyController()
    return _autonomy_controller


def reset_autonomy_controller() -> None:
    """Reset the global autonomy controller (mainly for testing)."""
    global _autonomy_controller
    _autonomy_controller = None
