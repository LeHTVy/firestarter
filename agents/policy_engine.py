"""Policy Engine for tool execution authorization."""

from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from tools.registry import ToolDefinition
from agents.scope_manager import ScopeManager
from agents.mode_manager import ModeManager, ExecutionMode


class RiskLevel(Enum):
    """Legal risk level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PolicyDecision(Enum):
    """Policy decision result."""
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"


@dataclass
class PolicyResult:
    """Policy check result."""
    decision: PolicyDecision
    reason: str
    risk_level: Optional[RiskLevel] = None
    requires_approval: bool = False
    
    def is_allowed(self) -> bool:
        """Check if execution is allowed."""
        return self.decision == PolicyDecision.ALLOWED or (
            self.decision == PolicyDecision.REQUIRES_APPROVAL and not self.requires_approval
        )


class PolicyEngine:
    """Policy Engine for tool execution authorization.
    
    Policy Engine performs multiple checks before allowing tool execution:
    1. Scope validation (target in authorized scope)
    2. Legal risk assessment
    3. Mode compatibility check
    4. Authorization verification
    """
    
    def __init__(self):
        """Initialize Policy Engine."""
        self.scope_manager = ScopeManager()
        self.mode_manager = ModeManager()
        
        # Risk thresholds for approval requirement
        self.RISK_THRESHOLD_AUTO_APPROVAL = RiskLevel.LOW
        self.RISK_THRESHOLD_REQUIRES_APPROVAL = RiskLevel.MEDIUM
    
    def check_tool_execution(
        self,
        tool: ToolDefinition,
        target: str,
        conversation_id: Optional[str] = None,
        execution_mode: Optional[ExecutionMode] = None
    ) -> PolicyResult:
        """Check if tool execution is allowed.
        
        Args:
            tool: Tool definition
            target: Target domain, IP, or hostname
            conversation_id: Conversation UUID (optional)
            execution_mode: Execution mode (optional, uses current mode if not provided)
            
        Returns:
            PolicyResult with decision and reason
        """
        # Get execution mode if not provided
        if execution_mode is None:
            execution_mode = self.mode_manager.get_mode(conversation_id)
        
        # 1. Scope validation
        scope_result = self.validate_scope(target, conversation_id)
        if not scope_result[0]:
            return PolicyResult(
                decision=PolicyDecision.DENIED,
                reason=f"Target '{target}' is not in authorized scope. {scope_result[1]}"
            )
        
        # 2. Mode compatibility check
        mode_result = self.check_mode_compatibility(tool, execution_mode)
        if not mode_result[0]:
            return PolicyResult(
                decision=PolicyDecision.DENIED,
                reason=f"Tool '{tool.name}' is not compatible with mode '{execution_mode.value}'. {mode_result[1]}"
            )
        
        # 3. Legal risk assessment
        risk_level = self.assess_legal_risk(tool, execution_mode)
        
        # 4. Authorization verification
        auth_result = self.check_authorization(tool, conversation_id)
        if not auth_result[0]:
            return PolicyResult(
                decision=PolicyDecision.DENIED,
                reason=f"Tool '{tool.name}' requires authorization. {auth_result[1]}"
            )
        
        # 5. Determine if approval is required
        requires_approval = self._requires_approval(risk_level, tool)
        
        if requires_approval:
            return PolicyResult(
                decision=PolicyDecision.REQUIRES_APPROVAL,
                reason=f"Tool '{tool.name}' has {risk_level.value} legal risk and requires user approval.",
                risk_level=risk_level,
                requires_approval=True
            )
        
        return PolicyResult(
            decision=PolicyDecision.ALLOWED,
            reason=f"Tool '{tool.name}' execution is allowed for target '{target}'.",
            risk_level=risk_level,
            requires_approval=False
        )
    
    def validate_scope(self, target: str, conversation_id: Optional[str] = None) -> Tuple[bool, str]:
        """Validate that target is in authorized scope.
        
        Args:
            target: Target domain, IP, or hostname
            conversation_id: Conversation UUID (optional)
            
        Returns:
            Tuple of (is_valid, reason)
        """
        is_authorized = self.scope_manager.is_target_authorized(target, conversation_id)
        
        if is_authorized:
            return True, "Target is in authorized scope"
        
        return False, "Please add target to authorized scope first"
    
    def assess_legal_risk(self, tool: ToolDefinition, mode: ExecutionMode) -> RiskLevel:
        """Assess legal risk of tool execution.
        
        Args:
            tool: Tool definition
            mode: Execution mode
            
        Returns:
            RiskLevel (LOW, MEDIUM, HIGH)
        """
        # Get legal risk from tool metadata
        legal_risk = tool.legal_risk or tool.risk_level
        
        # Map to RiskLevel enum
        risk_mapping = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH
        }
        
        base_risk = risk_mapping.get(legal_risk.lower(), RiskLevel.MEDIUM)
        
        # Adjust risk based on mode
        # Passive mode reduces risk, destructive mode increases risk
        if mode == ExecutionMode.PASSIVE:
            # Passive mode is always low risk
            return RiskLevel.LOW
        elif mode == ExecutionMode.SIMULATION:
            # Simulation mode reduces risk slightly (safe environment)
            if base_risk == RiskLevel.HIGH:
                return RiskLevel.MEDIUM
            return base_risk
        else:
            # Cooperative mode keeps original risk
            return base_risk
    
    def check_mode_compatibility(self, tool: ToolDefinition, mode: ExecutionMode) -> Tuple[bool, str]:
        """Check if tool is compatible with execution mode.
        
        Args:
            tool: Tool definition
            mode: Execution mode
            
        Returns:
            Tuple of (is_compatible, reason)
        """
        tool_modes = tool.mode or []
        
        # If tool has no mode specified, allow it (backward compatibility)
        if not tool_modes:
            return True, "Tool has no mode restrictions"
        
        is_compatible = self.mode_manager.is_tool_compatible(tool_modes, conversation_id=None)
        
        if is_compatible:
            return True, "Tool is compatible with execution mode"
        
        allowed_modes = ModeManager.MODE_COMPATIBILITY.get(mode, [])
        return False, f"Tool modes {tool_modes} are not compatible with allowed modes {allowed_modes}"
    
    def check_authorization(self, tool: ToolDefinition, conversation_id: Optional[str] = None) -> Tuple[bool, str]:
        """Check if tool requires authorization and if it's provided.
        
        Args:
            tool: Tool definition
            conversation_id: Conversation UUID (optional)
            
        Returns:
            Tuple of (is_authorized, reason)
        """
        # Check if tool requires authorization
        requires_auth = tool.permission_required
        if requires_auth is None:
            # Fallback to requires_auth field if permission_required is not set
            requires_auth = tool.requires_auth
        
        if not requires_auth:
            return True, "Tool does not require authorization"
        
        # TODO: Check if authorization is provided (API keys, credentials, etc.)
        # For now, we assume authorization is provided if tool is in registry
        # This should be enhanced to check for actual credentials
        
        # Check if tool has required API keys/credentials
        # This is a placeholder - actual implementation should check credentials store
        return True, "Authorization check passed (assuming credentials are configured)"
    
    def _requires_approval(self, risk_level: RiskLevel, tool: ToolDefinition) -> bool:
        """Determine if approval is required based on risk level and tool.
        
        Args:
            risk_level: Assessed legal risk level
            tool: Tool definition
            
        Returns:
            True if approval is required, False otherwise
        """
        # High risk always requires approval
        if risk_level == RiskLevel.HIGH:
            return True
        
        # Medium risk requires approval for certain tool types
        if risk_level == RiskLevel.MEDIUM:
            # Check if tool is in high-risk categories
            high_risk_categories = ["exploitation", "post_exploitation"]
            if tool.category in high_risk_categories:
                return True
        
        # Low risk doesn't require approval
        return False
