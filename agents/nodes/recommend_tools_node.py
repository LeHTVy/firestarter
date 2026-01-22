"""Recommend Tools Node - Recommends tools to user with policy checks."""

from typing import Dict, Any, Optional, Callable
from agents.policy_engine import PolicyDecision


class RecommendToolsNode:
    """Node for recommending tools to user (Human in the Loop)."""
    
    def __init__(self,
                 context_manager,
                 mode_manager,
                 policy_engine,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None):
        """Initialize recommend tools node.
        
        Args:
            context_manager: Context manager instance
            mode_manager: Mode manager instance
            policy_engine: Policy engine instance
            stream_callback: Optional streaming callback
        """
        self.context_manager = context_manager
        self.mode_manager = mode_manager
        self.policy_engine = policy_engine
        self.stream_callback = stream_callback
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute recommend tools node.
        
        Formats suggested tools from analysis and displays them to user.
        Applies policy checks (scope validation, mode filtering) before recommending.
        Sets user_approval to None to indicate pending approval.
        
        Args:
            state: Graph state
            
        Returns:
            Updated state
        """
        subtasks = state.get("subtasks", [])
        analysis = state.get("analysis")
        if analysis is None or not isinstance(analysis, dict):
            analysis = {}
        conversation_id = state.get("conversation_id") or state.get("session_id")
        
        # Get target from session context
        session_context = self.context_manager.get_context(state.get("session_context"))
        target = None
        if session_context:
            target = session_context.get_target()
        
        # Get current execution mode
        execution_mode = self.mode_manager.get_mode(conversation_id)
        
        # Extract tool recommendations from subtasks and apply policy checks
        recommended_tools = []
        tool_subtasks = []
        policy_issues = []
        
        from tools.registry import get_tool_registry
        tool_registry = get_tool_registry()
        
        for subtask in subtasks:
            if subtask.get("type") == "tool_execution":
                tool_names = subtask.get("required_tools", [])
                filtered_tools = []
                
                for tool_name in tool_names:
                    tool = tool_registry.get_tool(tool_name)
                    if not tool:
                        continue
                    
                    # Check mode compatibility
                    if tool.mode and not self.mode_manager.is_tool_compatible(tool.mode, conversation_id):
                        # Check if this is a direct tool command
                        user_prompt = state.get("user_prompt", "").lower()
                        is_direct_command = any(cmd in user_prompt for cmd in ["run ", "use ", "execute ", "call "])
                        
                        if is_direct_command:
                            # User explicitly requested - allow with warning
                            policy_issues.append(
                                f"Tool '{tool_name}' is not compatible with current mode '{execution_mode.value}' "
                                f"but allowing due to explicit request"
                            )
                        else:
                            # Not explicit - block for safety
                            policy_issues.append(
                                f"Tool '{tool_name}' is not compatible with current mode '{execution_mode.value}'"
                            )
                            continue
                    
                    # Check scope if target is available
                    if target:
                        policy_result = self.policy_engine.check_tool_execution(
                            tool=tool,
                            target=target,
                            conversation_id=conversation_id,
                            execution_mode=execution_mode
                        )
                        
                        if policy_result.decision == PolicyDecision.DENIED:
                            policy_issues.append(
                                f"Tool '{tool_name}': {policy_result.reason}"
                            )
                            continue
                        
                        if policy_result.decision == PolicyDecision.REQUIRES_APPROVAL:
                            policy_issues.append(
                                f"Tool '{tool_name}' requires approval (risk: {policy_result.risk_level.value})"
                            )
                    
                    filtered_tools.append(tool_name)
                    if tool_name not in recommended_tools:
                        recommended_tools.append(tool_name)
                
                # Only add subtask if it has compatible tools
                if filtered_tools:
                    subtask_copy = subtask.copy()
                    subtask_copy["required_tools"] = filtered_tools
                    tool_subtasks.append(subtask_copy)
        
        # Format recommendations
        recommendations = {
            "tools": recommended_tools,
            "subtasks": tool_subtasks,
            "analysis_summary": analysis.get("user_intent", ""),
            "task_type": analysis.get("task_type", "mixed"),
            "complexity": analysis.get("complexity", "medium"),
            "target": target,
            "execution_mode": execution_mode.value,
            "policy_issues": policy_issues,
            "needs_approval": len(recommended_tools) > 0
        }
        
        state["tool_recommendations"] = recommendations
        state["user_approval"] = None  # Pending approval - will be set by main.py
        
        # Display recommendations via callback
        if self.stream_callback and (recommended_tools or policy_issues):
            # Format message for user
            target_str = f" on {target}" if target else ""
            mode_str = f" (Mode: {execution_mode.value})"
            msg = f"\n💡 [bold yellow]Recommended Tools for '{recommendations['analysis_summary']}'{target_str}{mode_str}:[/bold yellow]\n\n"
            
            if policy_issues:
                msg += f"⚠️  [yellow]Policy Issues:[/yellow]\n"
                for issue in policy_issues[:3]:
                    msg += f"  - {issue}\n"
                msg += "\n"
            
            if recommended_tools:
                for i, subtask in enumerate(tool_subtasks[:5], 1):
                    tool_names = ", ".join(subtask.get("required_tools", []))
                    msg += f"  {i}. [cyan]{subtask.get('name', 'Tool execution')}[/cyan]\n"
                    msg += f"     Tools: [dim]{tool_names}[/dim]\n"
                    if subtask.get("description"):
                        msg += f"     {subtask.get('description')}\n"
                    msg += "\n"
            else:
                msg += "  [dim]No compatible tools available after policy checks.[/dim]\n"
            
            self.stream_callback("model_response", "system", msg)
        
        return state
