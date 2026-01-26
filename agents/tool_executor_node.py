"""Tool Execution Node - Handles tool execution with policy validation.

Combines tool execution and policy checks into a single module.
Inspired by rutx approach for simple, direct tool execution.
"""

from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tools.executor import get_executor
from agents.target_resolver import TargetSetResolver
# FeedbackLearner removed

MAX_CONCURRENT_TOOLS = 5  # Maximum tools to run in parallel


class ToolExecutorNode:
    """Node for executing tools with policy validation and fallback."""
    
    def __init__(self, 
                 memory_manager,
                 results_storage,
                 mode_manager=None,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None,
                 tool_calling_model: Optional[str] = None):
        """Initialize tool executor node.
        
        Args:
            memory_manager: Memory manager instance
            results_storage: Results storage instance
            mode_manager: Optional mode manager for execution mode
            stream_callback: Optional streaming callback
            tool_calling_model: Optional tool calling model name
        """
        self.memory_manager = memory_manager
        self.results_storage = results_storage
        self.mode_manager = mode_manager
        self.stream_callback = stream_callback
        self.executor = get_executor()
        self.target_resolver = TargetSetResolver(memory_manager)
        
        # Feedback tracking removed
        
        # Tool calling registry (optional - for semantic tool selection)
        from models.tool_calling_registry import get_tool_calling_registry
        self.tool_calling_registry = get_tool_calling_registry()
        self.tool_calling_model_name = tool_calling_model or "json_tool_calling"
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tools from subtasks with policy validation.
        
        Strategy:
        1. Validate tools against policy
        2. Check autonomy level for each tool
        3. Try tool calling model for semantic selection
        4. Fallback to direct execution if model doesn't call tools
        
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
        
        # Check autonomy level for tools
        from agents.autonomy_controller import get_autonomy_controller
        autonomy_controller = get_autonomy_controller()
        
        gated_tools = []
        approved_subtasks = []
        
        for subtask in subtasks:
            if subtask.get("type") != "tool_execution":
                approved_subtasks.append(subtask)
                continue
            
            tool_names = subtask.get("required_tools", [])
            approved_tools = []
            
            for tool_name in tool_names:
                can_execute, message = autonomy_controller.gate(
                    tool_name, 
                    context={"target": target},
                    conversation_id=conversation_id
                )
                
                if can_execute:
                    approved_tools.append(tool_name)
                else:
                    gated_tools.append((tool_name, message))
                    if self.stream_callback:
                        self.stream_callback("model_response", "autonomy", message)
            
            if approved_tools:
                subtask_copy = subtask.copy()
                subtask_copy["required_tools"] = approved_tools
                approved_subtasks.append(subtask_copy)
        
        # If all tools were gated, return with message
        if gated_tools and not any(s.get("type") == "tool_execution" for s in approved_subtasks):
            state["tool_results"] = []
            state["autonomy_blocked"] = True
            state["gated_tools"] = [t[0] for t in gated_tools]
            if self.stream_callback:
                self.stream_callback("model_response", "autonomy", 
                    f"\n⚠️ All requested tools require higher autonomy level. "
                    f"Use /autonomy <level> to change level or approve actions manually.")
            return state
        
        # Execute approved tools
        tool_results = self._execute_subtasks(state, approved_subtasks, target)
        state["tool_results"] = tool_results
        
        # Analyze results for multi-turn
        self._analyze_results(state, tool_results, approved_subtasks)
        
        return state
    
    def _get_target(self, state: Dict[str, Any]) -> Optional[str]:
        """Get target from session context or state."""
        conversation_id = state.get("conversation_id") or state.get("session_id")
        
        # Use MemoryManager to get verified target
        target = self.memory_manager.get_verified_target(conversation_id=conversation_id)
        if target:
            return target
            
        # Fallback to session memory
        if self.memory_manager.session_memory:
            return self.memory_manager.session_memory.agent_context.get_target()
            
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
                original_name = tool_name
                resolved_tool = None
                
                # 1. Try exact match first
                resolved_tool = tool_registry.get_tool(tool_name)
                
                # 2. Try case-insensitive match
                if not resolved_tool:
                    for t in tool_registry.list_tools():
                        if t.name.lower() == tool_name.lower():
                            resolved_tool = t
                            tool_name = t.name
                            break
                
                # 3. Try fuzzy matching - find tools containing the name
                if not resolved_tool:
                    for t in tool_registry.list_tools():
                        # Check if tool_name is part of actual tool name
                        if tool_name.lower() in t.name.lower():
                            resolved_tool = t
                            tool_name = t.name
                            if self.stream_callback:
                                self.stream_callback("model_response", "system",
                                    f"📝 Fuzzy match: '{original_name}' → '{tool_name}'")
                            break
                        # Check if actual tool name is part of tool_name
                        if t.name.lower() in tool_name.lower():
                            resolved_tool = t
                            tool_name = t.name
                            if self.stream_callback:
                                self.stream_callback("model_response", "system",
                                    f"📝 Fuzzy match: '{original_name}' → '{tool_name}'")
                            break
                
                # 4. Try capability-based matching (e.g., "subdomain" → subdomain_discovery)
                if not resolved_tool:
                    search_terms = tool_name.lower().replace("_", " ").replace("-", " ").split()
                    for t in tool_registry.list_tools():
                        # Check in name, description, or capabilities
                        tool_text = f"{t.name} {t.description}".lower()
                        if hasattr(t, 'capability') and t.capability:
                            tool_text += " " + " ".join(t.capability)
                        
                        # Check if any search term matches
                        if any(term in tool_text for term in search_terms):
                            resolved_tool = t
                            tool_name = t.name
                            if self.stream_callback:
                                self.stream_callback("model_response", "system",
                                    f"📝 Capability match: '{original_name}' → '{tool_name}'")
                            break
                
                if not resolved_tool:
                    if self.stream_callback:
                        self.stream_callback("model_response", "system",
                            f"⚠️ Tool '{original_name}' not found in registry (150+ tools available)")
                    continue
                
                tool = resolved_tool
                
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
        """Execute all tool subtasks with concurrent execution support."""
        tool_results = []
        
        # Create callbacks
        model_callback = self._create_model_callback()
        tool_stream_callback = self._create_tool_callback()
        
        # Get targets
        targets = self._extract_targets(state, target)
        
        # SRE Optimization (Strategic Recon Expansion):
        scan_tools = ["nmap_scan", "nmap", "ps", "port_scan", "masscan"]
        is_scan_task = any(any(t in subtask.get("required_tools", []) for t in scan_tools) for subtask in subtasks)
        
        target_map = {} # IP -> [domains]
        if is_scan_task and targets:
            target_map = self.target_resolver.resolve_to_ips(targets)
            if target_map:
                effective_targets = list(target_map.keys())
                state["execution_target_map"] = target_map
                if self.stream_callback:
                    self.stream_callback("model_response", "system", 
                        f"🎯 SRE Optimized: Resolved {len(targets)} subdomains to {len(effective_targets)} unique IPs.")
            else:
                effective_targets = targets
        else:
            effective_targets = targets

        # Fan-out / DSQ Strategy
        # If targets > 10, offload to Durable Scanning Queue (DSQ) for persistence
        use_dsq = len(targets) > 10 and is_scan_task and hasattr(self.memory, 'scanning_queue')
        
        if use_dsq:
            if self.stream_callback:
                self.stream_callback("model_response", "system", 
                    f"📦 Large target list ({len(targets)}) detected. Offloading to Durable Scanning Queue (PostgreSQL)...")
            
            # 1. Add targets to queue
            # We assume the first subtask's tool for now as a simple implementation
            tool_name = subtasks[0].get("required_tools", [scan_tools[0]])[0]
            cmd_name = subtasks[0].get("command", "quick")
            self.memory.scanning_queue.add_targets(
                self.memory.conversation_id,
                targets,
                tool_name,
                cmd_name
            )
            
            # 2. Worker loop for concurrent execution from queue
            all_worker_results = []
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TOOLS) as executor_pool:
                futures = {}
                for i in range(MAX_CONCURRENT_TOOLS):
                    future = executor_pool.submit(self._dsq_worker, state, tool_stream_callback)
                    futures[future] = f"DSQ_Worker_{i}"
                
                for future in as_completed(futures):
                    try:
                        results = future.result()
                        if results: 
                            all_worker_results.extend(results)
                    except Exception as e:
                        self.logger.error(f"DSQ Worker failed: {e}")
            
            # 3. Aggregate results for the QA agent and memory
            if all_worker_results:
                # Filter successful results
                successful_results = [r for r in all_worker_results if r.get("success")]
                
                # Combine results (e.g., all open ports found)
                aggregated_data = {
                    "total_targets": len(targets),
                    "successful_targets": len(successful_results),
                    "open_ports": [],
                    "vulnerabilities": [],
                    "technologies": [],
                    "raw_output": f"Durable Scan Batch Complete. Scanned {len(targets)} targets. {len(successful_results)} successful."
                }
                
                for r in successful_results:
                    parsed = r.get("parsed_data", {})
                    host = r.get("target") or r.get("host")
                    
                    if "open_ports" in parsed:
                        for p in parsed["open_ports"]:
                            p_copy = p.copy()
                            p_copy["host"] = host
                            aggregated_data["open_ports"].append(p_copy)
                    
                    if "vulnerabilities" in parsed:
                        for v in parsed["vulnerabilities"]:
                            v_copy = v.copy()
                            v_copy["host"] = host
                            aggregated_data["vulnerabilities"].append(v_copy)

                # Create a master result object
                master_result = {
                    "tool_name": tool_name,
                    "parameters": {"targets_count": len(targets), "tool": tool_name, "command": cmd_name},
                    "results": aggregated_data,
                    "success": len(successful_results) > 0,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Persist to tool_results table so QA agents can see it
                self._store_result(master_result, state)
                tool_results.append(master_result)

            # Final progress report
            progress = self.memory.scanning_queue.get_progress(self.memory.conversation_id)
            if self.stream_callback:
                self.stream_callback("model_response", "system", 
                    f"✅ Background scan batch complete. Total findings promoted to Entity View: {progress['done']}/{progress['total']}.")
            
            return tool_results

        # Collect all tool execution tasks (Standard Fan-out for small lists)
        tool_tasks = []
        for subtask in subtasks:
            if subtask.get("type") != "tool_execution":
                continue
            tools = subtask.get("required_tools", [])
            for tool_name in tools:
                if effective_targets:
                    # FAN-OUT: Create a task for each target
                    # Limit fan-out to prevent explosion
                    max_targets = effective_targets[:50] 
                    for target_item in max_targets:
                        tool_tasks.append((subtask, tool_name, target_item))
                else:
                    tool_tasks.append((subtask, tool_name, None))
        
        # Execute tools concurrently (max MAX_CONCURRENT_TOOLS at a time)
        if len(tool_tasks) == 0:
            return []

        if self.stream_callback:
            msg = f"🚀 Executing {len(tool_tasks)} task(s) "
            if len(targets) > 1:
                msg += f"across {len(targets)} targets "
            msg += f"concurrently (max {MAX_CONCURRENT_TOOLS})..."
            self.stream_callback("model_response", "system", msg)
        
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TOOLS) as executor_pool:
            futures = {}
            for subtask, tool_name, target_item in tool_tasks:
                # Create unique display name for the task
                display_name = f"{tool_name} on {target_item}" if target_item else tool_name
                
                # Create per-tool stream callback for concurrent execution
                def create_tool_callback(dn):
                    def callback(tool, cmd, line):
                        if self.stream_callback:
                            self.stream_callback("tool_output", dn, line)
                    return callback
                
                future = executor_pool.submit(
                    self._execute_single_tool,
                    state, subtask, tool_name, [target_item] if target_item else [],
                    None, create_tool_callback(display_name)
                )
                futures[future] = display_name
            
            for future in as_completed(futures):
                display_name = futures[future]
                try:
                    result = future.result()
                    if result:
                        tool_results.append(result)
                        summary = self._store_result(result, state)
                        self._track_feedback(result, tool_name, state)
                        if self.stream_callback:
                            status = "✅" if result.get("success") else "❌"
                            msg = f"{status} {tool_name} completed"
                            if summary:
                                msg += f" ({summary})"
                            self.stream_callback("model_response", "system", msg)
                except Exception as e:
                    if self.stream_callback:
                        self.stream_callback("model_response", "system",
                            f"❌ {tool_name} failed: {e}")
        
        return tool_results
    
    def _execute_single_tool(self, state: Dict, subtask: Dict, tool_name: str,
                            targets: List[str], model_callback, tool_stream_callback) -> Optional[Dict]:
        """Execute a single tool with fallback."""
        # Build tool prompt
        # Use target from subtask parameters if provided (set by analyze_node for memory expansion)
        subtask_params = subtask.get("parameters", {})
        if "target" in subtask_params:
            effective_targets = [subtask_params["target"]]
        else:
            effective_targets = targets
            
        targets_str = ", ".join(effective_targets) if effective_targets else "target"
        
        # Build tool prompt
        subtask_name = subtask.get("name", "Unknown")
        subtask_desc = subtask.get("description", "No description")
        user_prompt = state.get("user_prompt", "")
        
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
                f"📦 Executing {tool_name} directly on {targets_str}...")
        
        return self._execute_direct(tool_name, effective_targets, subtask_desc, state, tool_stream_callback)
    
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
        
        # Special handling for web_search
        if tool_name == "web_search" and "query" not in params:
            # Generate a default query from target
            if targets:
                target = targets[0]
                if "." in target and not target.startswith("http"):
                    params["query"] = f'"{target}" security vulnerabilities OR site:{target} "vulnerabilities"'
                else:
                    params["query"] = f'"{target}" vulnerabilities'
            else:
                params["query"] = f"security vulnerabilities {description}"
        
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
            
        # [MEMORY FUSION RESOLUTION]
        # Resolve targets using L1/L2/L3 Memory layers
        if self.target_resolver:
            resolved = self.target_resolver.resolve_targets(state.get("user_prompt", ""), targets)
            if resolved:
                # Filter out redundant roots if subdomains are present? 
                # No, keep both for now, TargetSetResolver handles deduplication
                targets = resolved
        
        return targets

        

    def _resolve_memory_targets(self, prompt: str, targets: List[str]) -> None:
        """Resolve targets from memory based on prompt keywords."""
        prompt_lower = prompt.lower()
        agent_context = self.memory_manager.session_memory.agent_context
        
        # Mapping: keyword -> (context_field, context_attribute)
        # We check if keyword exists in prompt, then fetch data from context
        mappings = [
            (["subdomain", "finding", "asset"], "subdomains"),
            (["open port", "service"], "open_ports"), 
            (["ip", "address"], "ips")
        ]
        
        for keywords, field in mappings:
            if any(k in prompt_lower for k in keywords):
                data = getattr(agent_context, field, [])
                if not data:
                    continue
                    
                count = 0
                if field == "open_ports":
                    # Special handling for ports: get hosts
                    hosts = set(p.get("host") for p in data if p.get("host"))
                    for h in hosts:
                        if h not in targets:
                            targets.append(h)
                            count += 1
                else:
                    # Standard list of strings
                    for item in data:
                        if isinstance(item, str) and item not in targets:
                            targets.append(item)
                            count += 1
                
                if count > 0 and self.stream_callback:
                    self.stream_callback("model_response", "system", 
                        f"🔄 Resolved {count} {field} from memory.")

    def _store_result(self, result: Dict, state: Dict) -> str:
        """Store tool result and return summary string."""
        summary = ""
        
        self.results_storage.store_result(
            tool_name=result.get("tool_name", ""),
            parameters=result.get("parameters", {}),
            results=result.get("results"),
            success=result.get("success", False),  # Pass success status
            agent=state.get("selected_agent"),
            session_id=state.get("conversation_id") or state.get("session_id"),
            conversation_id=state.get("conversation_id"),
            execution_id=result.get("execution_id")
        )
        
        # Update context with findings
        results = result.get("results", {})
        if isinstance(results, dict):
            findings = {}
            for key in ["subdomains", "ips", "open_ports", "vulnerabilities", "technologies", "emails", "urls"]:
                if key in results:
                    data = results[key]
                    if data:
                        findings[key] = data
                        count = len(data) if isinstance(data, list) else 1
                        summary += f"Found {count} {key}. "
            
            if findings:
                # Stream findings
                if self.stream_callback:
                    for key, value in findings.items():
                        self.stream_callback("finding", "tool_executor", {
                            "type": key,
                            "data": {key: value} if not isinstance(value, dict) else value,
                            "severity": "info"
                        })

                # Persist to structured database (PostgreSQL findings table)
                conversation_id = state.get("conversation_id") or state.get("session_id")
                
                # SRE Broadcasting: If we scanned an IP that represents multiple domains,
                # broadcast the findings to all of them in memory.
                target_map = state.get("execution_target_map", {})
                actual_target = result.get("target") or state.get("target") or self._get_target(state)
                
                broadcast_targets = [actual_target]
                if actual_target in target_map:
                    # This was an IP scan representing multiple domains
                    broadcast_targets.extend(target_map[actual_target])
                    # Ensure unique
                    broadcast_targets = list(set(broadcast_targets))

                if conversation_id:
                    for b_target in broadcast_targets:
                        for ftype, items in findings.items():
                            if isinstance(items, list):
                                for item in items:
                                    self.memory_manager.conversation_store.add_finding(
                                        conversation_id=conversation_id,
                                        finding_type=ftype,
                                        value=str(item),
                                        source_tool=result.get("tool_name", ""),
                                        target=b_target
                                    )
                            else:
                                self.memory_manager.conversation_store.add_finding(
                                    conversation_id=conversation_id,
                                    finding_type=ftype,
                                    value=str(items),
                                    source_tool=result.get("tool_name", ""),
                                    target=b_target
                                )

                    # Update session context with findings
                    self.memory_manager.update_agent_context(findings)
                
        return summary.strip()
    
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
            # Standard tool output stream
            self.stream_callback("tool_output", 
                f"{tool_name}:{command}" if command else tool_name, line)
            
            # [TRUST FIX] Mirror to model_response for immediate visibility
            # Use 'tool_log' type which should be rendered as a log stream
            prefix = f"[{tool_name}] " 
            if line:
                 self.stream_callback("model_response", "tool_stdout", prefix + line)
        return callback

    def _dsq_worker(self, state: Dict, tool_stream_callback) -> List[Dict]:
        """Worker to consume tasks from Durable Scanning Queue."""
        results = []
        while True:
            task = self.memory.scanning_queue.claim_task(self.memory.conversation_id)
            if not task:
                break
            
            task_id = task["id"]
            host = task["host"]
            tool_name = task["tool_name"]
            cmd_name = task["command_name"]
            
            display_name = f"DSQ: {tool_name} on {host}"
            self.stream_callback("model_response", "system", f"🔍 Scanning {host}...")
            
            # Wrap callback to route to the correct UI stream
            def wrap_cb(tool, cmd, line):
                if self.stream_callback:
                    self.stream_callback("tool_output", display_name, line)
            
            # Create a mock subtask for the executor
            subtask = {
                "name": f"Scan {host}",
                "type": "tool_execution",
                "required_tools": [tool_name],
                "command": cmd_name,
                "parameters": task.get("parameters", {})
            }
            
            # Direct execution
            result = self._execute_single_tool(
                state, subtask, tool_name, [host], 
                None, wrap_cb
            )
            
            if result:
                results.append(result)
                # Update DB status
                self.memory.scanning_queue.update_result(
                    task_id, 
                    success=result.get("success", False),
                    result=result.get("parsed_data", {}),
                    error=result.get("error")
                )
                
                # Report finding to user
                if result.get("success") and result.get("parsed_data"):
                    ports = result.get("parsed_data", {}).get("open_ports", [])
                    if ports:
                        self.stream_callback("model_response", "system", 
                            f"✨ Finding: {host} has open ports: {', '.join([str(p['port']) for p in ports])}")
            
        return results
