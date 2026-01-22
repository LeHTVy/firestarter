"""Tool Execution Node - Handles tool execution with policy validation.

Combines tool execution and policy checks into a single module.
Inspired by rutx approach for simple, direct tool execution.
"""

from typing import Dict, Any, Optional, Callable, List
from tools.executor import get_executor
# FeedbackLearner removed


class ToolExecutorNode:
    """Node for executing tools with policy validation and fallback."""
    
    def __init__(self, 
                 context_manager,
                 memory_manager,
                 results_storage,
                 mode_manager=None,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None,
                 tool_calling_model: Optional[str] = None):
        """Initialize tool executor node.
        
        Args:
            context_manager: Context manager instance
            memory_manager: Memory manager instance
            results_storage: Results storage instance
            mode_manager: Optional mode manager for execution mode
            stream_callback: Optional streaming callback
            tool_calling_model: Optional tool calling model name
        """
        self.context_manager = context_manager
        self.memory_manager = memory_manager
        self.results_storage = results_storage
        self.mode_manager = mode_manager
        self.stream_callback = stream_callback
        self.executor = get_executor()
        
        # Feedback tracking removed
        
        # Tool calling registry (optional - for semantic tool selection)
        from models.tool_calling_registry import get_tool_calling_registry
        self.tool_calling_registry = get_tool_calling_registry()
        self.tool_calling_model_name = tool_calling_model or "json_tool_calling"
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tools from subtasks with policy validation.
        
        Strategy:
        1. Validate tools against policy
        2. Try tool calling model for semantic selection
        3. Fallback to direct execution if model doesn't call tools
        
        Args:
            state: Graph state with subtasks
            
        Returns:
            Updated state with tool_results
        """
        subtasks = state.get("subtasks", [])
        
        # Get target and validate policy
        target = self._get_target(state)
        conversation_id = state.get("conversation_id") or state.get("session_id")
        
        # Validate subtasks against policy
        if self.mode_manager:
            execution_mode = self.mode_manager.get_mode(conversation_id)
            subtasks = self._validate_subtasks(subtasks, target, conversation_id, execution_mode)
            state["subtasks"] = subtasks
        
        # Execute tools
        tool_results = self._execute_subtasks(state, subtasks, target)
        state["tool_results"] = tool_results
        
        # Analyze results for multi-turn
        self._analyze_results(state, tool_results, subtasks)
        
        return state
    
    def _get_target(self, state: Dict[str, Any]) -> Optional[str]:
        """Get target from session context or state."""
        session_context = self.context_manager.get_context(state.get("session_context"))
        if session_context:
            return session_context.get_target()
        return None
    
    def _validate_subtasks(self, subtasks: List[Dict], target: Optional[str],
                          conversation_id: Optional[str], execution_mode) -> List[Dict]:
        """Validate subtasks against mode compatibility."""
        from tools.registry import get_registry
        
        tool_registry = get_registry()
        validated = []
        
        for subtask in subtasks:
            if subtask.get("type") != "tool_execution":
                validated.append(subtask)
                continue
            
            tool_names = subtask.get("required_tools", [])
            validated_tools = []
            
            for tool_name in tool_names:
                tool = tool_registry.get_tool(tool_name)
                if not tool:
                    continue
                
                # Mode compatibility check only
                if self.mode_manager and tool.mode:
                    if not self.mode_manager.is_tool_compatible(tool.mode, conversation_id):
                        if self.stream_callback:
                            self.stream_callback("model_response", "system",
                                f"⚠️ Tool '{tool_name}' not compatible with current execution mode")
                        continue
                
                validated_tools.append(tool_name)
            
            if validated_tools:
                subtask_copy = subtask.copy()
                subtask_copy["required_tools"] = validated_tools
                validated.append(subtask_copy)
        
        return validated
    
    def _execute_subtasks(self, state: Dict[str, Any], subtasks: List[Dict],
                         target: Optional[str]) -> List[Dict]:
        """Execute all tool subtasks."""
        tool_results = []
        
        # Create callbacks
        model_callback = self._create_model_callback()
        tool_stream_callback = self._create_tool_callback()
        
        # Get targets
        targets = self._extract_targets(state, target)
        
        for subtask in subtasks:
            if subtask.get("type") != "tool_execution":
                continue
            
            tools = subtask.get("required_tools", [])
            
            for tool_name in tools:
                result = self._execute_single_tool(
                    state, subtask, tool_name, targets,
                    model_callback, tool_stream_callback
                )
                
                if result:
                    tool_results.append(result)
                    self._store_result(result, state)
                    self._track_feedback(result, tool_name, state)
        
        return tool_results
    
    def _execute_single_tool(self, state: Dict, subtask: Dict, tool_name: str,
                            targets: List[str], model_callback, tool_stream_callback) -> Optional[Dict]:
        """Execute a single tool with fallback."""
        user_prompt = state.get("user_prompt", "")
        subtask_name = subtask.get("name", "")
        subtask_desc = subtask.get("description", "")
        targets_str = ", ".join(targets) if targets else "target"
        
        # Build tool prompt
        tool_prompt = f"""Execute {tool_name}:
Task: {subtask_name}
Description: {subtask_desc}
Target: {targets_str}
Request: {user_prompt}

Extract parameters from context and execute the tool."""
        
        # Try tool calling model first
        try:
            tool_calling_agent = self.tool_calling_registry.get_model(self.tool_calling_model_name)
            
            result = tool_calling_agent.call_with_tools(
                user_prompt=tool_prompt,
                tools=[tool_name],
                agent=state.get("selected_agent"),
                session_id=state.get("conversation_id") or state.get("session_id"),
                conversation_history=state.get("conversation_history", []),
                stream_callback=model_callback,
                tool_stream_callback=tool_stream_callback
            )
            
            # Check if model called tools
            if result.get("tool_results") and len(result["tool_results"]) > 0:
                return result["tool_results"][0].get("result", {})
        except Exception as e:
            if self.stream_callback:
                self.stream_callback("model_response", "system", f"⚠️ Tool calling error: {e}")
        
        # FALLBACK: Direct execution
        if self.stream_callback:
            self.stream_callback("model_response", "system", 
                f"📦 Executing {tool_name} directly...")
        
        return self._execute_direct(tool_name, targets, subtask_desc, state, tool_stream_callback)
    
    def _execute_direct(self, tool_name: str, targets: List[str], description: str,
                       state: Dict, tool_stream_callback) -> Dict:
        """Execute tool directly without model."""
        # Build parameters
        params = {}
        if targets:
            target = targets[0]
            params["target"] = target
            params["domain"] = target
            params["host"] = target
            if "." in target and not target.startswith("http"):
                params["url"] = f"https://{target}"
        
        # Extract ports if mentioned
        import re
        desc_lower = description.lower()
        if "port" in desc_lower:
            ports = re.findall(r'\b(\d{1,5})\b', desc_lower)
            if ports:
                params["ports"] = ",".join(ports[:10])
        
        # Execute with streaming
        if tool_stream_callback:
            def callback(line: str):
                tool_stream_callback(tool_name, "", line)
            
            return self.executor.execute_tool_streaming(
                tool_name=tool_name,
                parameters=params,
                stream_callback=callback,
                agent=state.get("selected_agent"),
                session_id=state.get("conversation_id") or state.get("session_id")
            )
        else:
            return self.executor.execute_tool(
                tool_name=tool_name,
                parameters=params,
                agent=state.get("selected_agent"),
                session_id=state.get("conversation_id") or state.get("session_id")
            )
    
    def _extract_targets(self, state: Dict, verified_target: Optional[str]) -> List[str]:
        """Extract targets from state."""
        from utils.input_normalizer import InputNormalizer
        
        normalizer = InputNormalizer()
        normalized = normalizer.normalize_input(state.get("user_prompt", ""), verify_domains=False)
        targets = normalized.get("targets", [])
        
        if verified_target and verified_target not in targets:
            targets.insert(0, verified_target)
        
        return targets
    
    def _store_result(self, result: Dict, state: Dict) -> None:
        """Store tool result."""
        if not result.get("success"):
            return
        
        self.results_storage.store_result(
            tool_name=result.get("tool_name", ""),
            parameters=result.get("parameters", {}),
            results=result.get("results"),
            agent=state.get("selected_agent"),
            session_id=state.get("conversation_id") or state.get("session_id"),
            conversation_id=state.get("conversation_id"),
            execution_id=result.get("execution_id")
        )
        
        # Update context with findings
        results = result.get("results", {})
        if isinstance(results, dict):
            findings = {}
            for key in ["subdomains", "ips", "open_ports", "vulnerabilities", "technologies"]:
                if key in results:
                    findings[key] = results[key]
            
            if findings:
                self.memory_manager.update_agent_context(findings)
                self.context_manager.update_context(findings)
    
    def _track_feedback(self, result: Dict, tool_name: str, state: Dict) -> None:
        """Track execution feedback."""
        # FeedbackLearner removed - no tracking
        pass
    
    def _analyze_results(self, state: Dict, tool_results: List[Dict], subtasks: List[Dict]) -> None:
        """Analyze results and suggest next tools."""
        if not tool_results:
            return
        
        # Result analyzer removed - basic analysis only
        state["result_analysis"] = {
            "summary": f"Executed {len(tool_results)} tool(s)",
            "findings": {},
            "suggested_tools": []
        }
        
        # Mark completed subtasks
        self._mark_completed(tool_results, subtasks)
    
    def _mark_completed(self, tool_results: List[Dict], subtasks: List[Dict]) -> None:
        """Mark completed subtasks in session memory."""
        if not self.memory_manager or not self.memory_manager.session_memory:
            return
        
        for result in tool_results:
            if not result.get("success"):
                continue
            
            tool_name = result.get("tool_name", "")
            for subtask in subtasks:
                if tool_name in subtask.get("required_tools", []):
                    subtask_id = subtask.get("id")
                    if subtask_id:
                        self.memory_manager.session_memory.agent_context.complete_task(subtask_id)
    
    def _create_model_callback(self) -> Optional[Callable]:
        """Create model streaming callback."""
        if not self.stream_callback:
            return None
        
        def callback(chunk: str):
            self.stream_callback("model_response", self.tool_calling_model_name, chunk)
        return callback
    
    def _create_tool_callback(self) -> Optional[Callable]:
        """Create tool streaming callback."""
        if not self.stream_callback:
            return None
        
        def callback(tool_name: str, command: str, line: str):
            self.stream_callback("tool_output", 
                f"{tool_name}:{command}" if command else tool_name, line)
        return callback
