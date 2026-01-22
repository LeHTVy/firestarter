"""Tool Execution Node - Handles tool execution with FunctionGemma and fallback."""

from typing import Dict, Any, Optional, Callable
from tools.executor import get_executor
from agents.tool_feedback_tracker import ToolFeedbackTracker
from agents.result_analyzer import ResultAnalyzer
from agents.feedback_learner import FeedbackLearner


class ToolExecutorNode:
    """Node for executing tools with FunctionGemma and fallback to direct execution."""
    
    def __init__(self, 
                 functiongemma,
                 context_manager,
                 memory_manager,
                 results_storage,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None,
                 tool_calling_model: Optional[str] = None):
        """Initialize tool executor node.
        
        Args:
            functiongemma: FunctionGemma agent instance (for backward compatibility)
            context_manager: Context manager instance
            memory_manager: Memory manager instance
            results_storage: Results storage instance
            stream_callback: Optional streaming callback
            tool_calling_model: Optional tool calling model name (default: functiongemma)
        """
        self.functiongemma = functiongemma
        self.context_manager = context_manager
        self.memory_manager = memory_manager
        self.results_storage = results_storage
        self.stream_callback = stream_callback
        self.executor = get_executor()
        self.feedback_tracker = ToolFeedbackTracker()  # Track tool execution feedback
        self.result_analyzer = ResultAnalyzer()  # Analyze results and suggest next tools
        self.feedback_learner = FeedbackLearner(feedback_tracker=self.feedback_tracker)  # Learn from feedback
        
        # Initialize tool calling registry
        from models.tool_calling_registry import get_tool_calling_registry
        self.tool_calling_registry = get_tool_calling_registry()
        self.tool_calling_model_name = tool_calling_model or "functiongemma"
        
        # Initialize tool calling registry
        from models.tool_calling_registry import get_tool_calling_registry
        self.tool_calling_registry = get_tool_calling_registry()
        self.tool_calling_model_name = tool_calling_model or "functiongemma"
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tools from subtasks.
        
        Strategy:
        1. Try FunctionGemma to call tools (preferred - semantic tool selection)
        2. If FunctionGemma doesn't call tools, fallback to direct execution from registry
        
        Args:
            state: Graph state with subtasks
            
        Returns:
            Updated state with tool_results
        """
        subtasks = state.get("subtasks", [])
        tool_results = []
        
        # Create streaming callbacks
        model_callback = None
        tool_stream_callback = None
        
        if self.stream_callback:
            def model_cb(chunk: str):
                self.stream_callback("model_response", "functiongemma", chunk)
            model_callback = model_cb
            
            def tool_cb(tool_name: str, command_name: str, line: str):
                self.stream_callback("tool_output", f"{tool_name}:{command_name}" if command_name else tool_name, line)
            tool_stream_callback = tool_cb
        
        # Get verified target from session context
        session_context = self.context_manager.get_context(state.get("session_context"))
        verified_target = None
        if session_context:
            verified_target = session_context.get_target()
        
        # Extract targets from user prompt
        user_prompt_original = state.get("user_prompt", "")
        from utils.input_normalizer import InputNormalizer
        normalizer = InputNormalizer()
        normalized = normalizer.normalize_input(user_prompt_original, verify_domains=False)
        targets = normalized.get("targets", [])
        
        # Prefer verified target if available
        if verified_target and verified_target not in targets:
            targets.insert(0, verified_target)
        
        # Process each subtask
        for subtask in subtasks:
            subtask_id = subtask.get("id")
            if subtask.get("type") == "tool_execution":
                tools = subtask.get("required_tools", [])
                subtask_description = subtask.get("description", "")
                subtask_name = subtask.get("name", "")
                
                targets_str = ", ".join(targets) if targets else "target from user request"
                
                # Include conversation context in tool prompt
                conversation_context = ""
                conversation_history = state.get("conversation_history", [])
                if conversation_history:
                    recent = conversation_history[-3:]
                    conversation_context = "\n".join([
                        f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:200]}" 
                        for msg in recent
                    ])
                
                # Try FunctionGemma first (preferred - semantic tool selection)
                for tool_name in tools:
                    # Build comprehensive prompt for FunctionGemma with context
                    tool_prompt = f"""Execute {tool_name} for the following task:
Task: {subtask_name}
Description: {subtask_description}
Target: {targets_str}
Original request: {user_prompt_original}"""
                    
                    if conversation_context:
                        tool_prompt += f"\n\nRecent conversation context:\n{conversation_context}"
                    
                    tool_prompt += "\n\nExtract the required parameters from the context above and execute the tool with appropriate values. For example, if the target is a domain like \"hellogroup.co.za\", use it as the \"domain\" parameter."
                    
                    # Get tool calling model from registry
                    tool_calling_agent = self.tool_calling_registry.get_model(self.tool_calling_model_name)
                    
                    result = tool_calling_agent.call_with_tools(
                        user_prompt=tool_prompt,
                        tools=tools,  # Pass specific tools
                        agent=state.get("selected_agent"),
                        session_id=state.get("conversation_id") or state.get("session_id"),
                        conversation_history=state.get("conversation_history", []),
                        stream_callback=model_callback,
                        tool_stream_callback=tool_stream_callback
                    )
                    
                    # Check if FunctionGemma actually called tools
                    if result.get("tool_results") and len(result["tool_results"]) > 0:
                        # FunctionGemma successfully called tools
                        for tr in result["tool_results"]:
                            exec_result = tr.get("result", {})
                            tool_results.append(exec_result)
                            self._store_and_update_context(exec_result, state)
                            
                            # Track feedback for learning
                            self.feedback_tracker.record_execution(
                                tool_name=tool_name,
                                success=exec_result.get("success", False),
                                execution_time=exec_result.get("execution_time", 0.0),
                                error=exec_result.get("error"),
                                parameters=exec_result.get("parameters"),
                                results=exec_result.get("results"),
                                agent=state.get("selected_agent"),
                                session_id=state.get("conversation_id") or state.get("session_id")
                            )
                            
                            # Collect feedback for learning (with reasoning if available)
                            reasoning = result.get("reasoning")
                            self.feedback_learner.collect_feedback(
                                tool_name=tool_name,
                                success=exec_result.get("success", False),
                                execution_time=exec_result.get("execution_time", 0.0),
                                reasoning=reasoning,
                                error=exec_result.get("error"),
                                parameters=exec_result.get("parameters")
                            )
                    else:
                        # FALLBACK: FunctionGemma didn't call tools, execute directly from registry
                        if self.stream_callback:
                            self.stream_callback("model_response", "system", 
                                f"⚠️ FunctionGemma didn't call {tool_name}. Executing directly from registry...")
                        
                        # Prepare base parameters
                        base_params = {}
                        if targets:
                            target = targets[0]
                            base_params["domain"] = target
                            base_params["target"] = target
                            base_params["host"] = target
                            # Build URL if domain
                            if "." in target and not target.startswith("http"):
                                base_params["url"] = f"https://{target}"
                        
                        # Try to extract additional params from subtask description
                        subtask_desc = subtask_description.lower()
                        if "port" in subtask_desc:
                            # Extract port numbers if mentioned
                            import re
                            ports = re.findall(r'\b(\d{1,5})\b', subtask_desc)
                            if ports:
                                base_params["ports"] = ",".join(ports[:10])  # Limit to 10 ports
                        
                        # Execute tool directly via executor (fallback)
                        if tool_stream_callback:
                            def tool_callback(line: str):
                                tool_stream_callback(tool_name, "", line)
                            
                            exec_result = self.executor.execute_tool_streaming(
                                tool_name=tool_name,
                                parameters=base_params,
                                stream_callback=tool_callback,
                                agent=state.get("selected_agent"),
                                session_id=state.get("conversation_id") or state.get("session_id")
                            )
                        else:
                            exec_result = self.executor.execute_tool(
                                tool_name=tool_name,
                                parameters=base_params,
                                agent=state.get("selected_agent"),
                                session_id=state.get("conversation_id") or state.get("session_id")
                            )
                        
                        tool_results.append(exec_result)
                        self._store_and_update_context(exec_result, state)
                        
                        # Track feedback for learning
                        self.feedback_tracker.record_execution(
                            tool_name=tool_name,
                            success=exec_result.get("success", False),
                            execution_time=exec_result.get("execution_time", 0.0),
                            error=exec_result.get("error"),
                            parameters=exec_result.get("parameters"),
                            results=exec_result.get("results"),
                            agent=state.get("selected_agent"),
                            session_id=state.get("conversation_id") or state.get("session_id")
                        )
                        
                        # Collect feedback for learning
                        self.feedback_learner.collect_feedback(
                            tool_name=tool_name,
                            success=exec_result.get("success", False),
                            execution_time=exec_result.get("execution_time", 0.0),
                            reasoning=None,  # No reasoning from fallback execution
                            error=exec_result.get("error"),
                            parameters=exec_result.get("parameters")
                        )
        
        state["tool_results"] = tool_results
        
        # MULTI-TURN: Analyze results and suggest next tools (probe → observe → adapt)
        if tool_results:
            analysis = self.result_analyzer.analyze_results(tool_results)
            
            # Store analysis in state
            state["result_analysis"] = analysis
            
            # If we have findings and suggested tools, add follow-up subtasks
            suggested_tools = analysis.get("suggested_tools", [])
            if suggested_tools and len(suggested_tools) > 0:
                # Check if we should continue (multi-turn execution)
                # Only add follow-up if we have meaningful findings
                findings = analysis.get("findings", {})
                has_findings = any(
                    findings.get(key) and len(findings[key]) > 0
                    for key in ["subdomains", "ips", "open_ports", "vulnerabilities", "technologies"]
                )
                
                if has_findings:
                    follow_up_subtasks = self.result_analyzer.get_next_subtasks(
                        findings=findings,
                        suggested_tools=suggested_tools
                    )
                    
                    # Add follow-up subtasks to state (will be processed in next iteration if enabled)
                    existing_subtasks = state.get("subtasks", [])
                    state["follow_up_subtasks"] = follow_up_subtasks
                    
                    if self.stream_callback:
                        summary = analysis.get("summary", "No summary")
                        self.stream_callback("model_response", "system", 
                            f"📊 Analysis: {summary}")
                        self.stream_callback("model_response", "system", 
                            f"💡 Suggested next tools: {', '.join(suggested_tools[:3])}")
        
        # Mark completed subtasks as done in session memory
        if self.memory_manager and self.memory_manager.session_memory:
            # Get subtask IDs that had successful tool executions
            completed_subtask_ids = set()
            for result in tool_results:
                if result.get("success"):
                    # Try to find matching subtask by tool name
                    tool_name = result.get("tool_name", "")
                    for subtask in subtasks:
                        if tool_name in subtask.get("required_tools", []):
                            subtask_id = subtask.get("id")
                            if subtask_id:
                                completed_subtask_ids.add(subtask_id)
            
            # Mark subtasks as completed
            for subtask_id in completed_subtask_ids:
                self.memory_manager.session_memory.agent_context.complete_task(subtask_id)
        
        return state
    
    def _store_and_update_context(self, exec_result: Dict[str, Any], state: Dict[str, Any]):
        """Store tool result and update context with findings.
        
        Args:
            exec_result: Tool execution result
            state: Graph state
        """
        if not exec_result.get("success"):
            return
        
        # Store in results storage
        self.results_storage.store_result(
            tool_name=exec_result.get("tool_name", ""),
            parameters=exec_result.get("parameters", {}),
            results=exec_result.get("results"),
            agent=state.get("selected_agent"),
            session_id=state.get("conversation_id") or state.get("session_id"),
            conversation_id=state.get("conversation_id"),
            execution_id=exec_result.get("execution_id")
        )
        
        # Update agent context with findings from tool results
        results = exec_result.get("results", {})
        if isinstance(results, dict):
            # Extract findings from results
            findings = {}
            if "subdomains" in results:
                findings["subdomains"] = results["subdomains"]
            if "ips" in results:
                findings["ips"] = results["ips"]
            if "open_ports" in results:
                findings["open_ports"] = results["open_ports"]
            if "vulnerabilities" in results:
                findings["vulnerabilities"] = results["vulnerabilities"]
            if "technologies" in results:
                findings["technologies"] = results["technologies"]
            
            if findings:
                self.memory_manager.update_agent_context(findings)
                # Update session context
                self.context_manager.update_context(findings)
