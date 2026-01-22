"""Subtask Creator - Creates subtasks and pentest plans based on user prompt.

Combines keyword analysis and proactive planning into a single module.
Inspired by rutx approach for simple, direct tool execution.
"""

from typing import Dict, Any, List, Optional, Callable
import uuid
import re


class SubtaskCreator:
    """Creates subtasks when model doesn't create them.
    
    Combines:
    - Keyword analysis for tool selection
    - Proactive pentest plan creation
    """
    
    def __init__(self, 
                 context_manager=None,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None):
        """Initialize subtask creator.
        
        Args:
            context_manager: Optional context manager for session context
            stream_callback: Optional callback for streaming events
        """
        self.context_manager = context_manager
        self.stream_callback = stream_callback
        self.keyword_to_tools = self._load_keyword_mappings()
    
    def _load_keyword_mappings(self) -> Dict[str, List[str]]:
        """Load keyword to tools mapping."""
        return {
            # Subdomain enumeration
            "subdomain": ["subdomain_discovery", "amass_enum"],
            "subdomain discovery": ["subdomain_discovery"],
            "find subdomain": ["subdomain_discovery"],
            "enumerate subdomain": ["subdomain_discovery", "amass_enum"],
            "subdomain enum": ["subdomain_discovery"],
            "amass": ["amass_enum"],
            "subfinder": ["subfinder"],
            
            # DNS related
            "dns": ["dns_enum", "dns_lookup"],
            "dns lookup": ["dns_lookup"],
            "dns enum": ["dns_enum"],
            "dns enumeration": ["dns_enum"],
            "resolve dns": ["dns_lookup"],
            
            # WHOIS related
            "whois": ["whois_lookup"],
            "domain info": ["whois_lookup"],
            "domain information": ["whois_lookup"],
            "registrar": ["whois_lookup"],
            
            # Port scanning
            "port": ["nmap_scan"],
            "port scan": ["nmap_scan"],
            "scan port": ["nmap_scan"],
            "open port": ["nmap_scan"],
            "nmap": ["nmap_scan"],
            "network scan": ["nmap_scan"],
            
            # Service detection
            "service": ["nmap_scan"],
            "service detection": ["nmap_scan"],
            "detect service": ["nmap_scan"],
            "banner": ["nmap_scan"],
            
            # Vulnerability
            "vulnerability": ["nmap_scan"],
            "vuln": ["nmap_scan"],
            "exploit": ["metasploit_exploit"],
            "cve": ["nmap_scan"],
            
            # SSL/TLS
            "ssl": ["ssl_scan"],
            "tls": ["ssl_scan"],
            "certificate": ["ssl_scan"],
            "cert": ["ssl_scan"],
            
            # Web related
            "web": ["nmap_scan"],
            "website": ["nmap_scan"],
            "http": ["nmap_scan"],
            "https": ["nmap_scan", "ssl_scan"],
            
            # OSINT/Recon
            "recon": ["whois_lookup", "dns_enum", "subdomain_discovery"],
            "reconnaissance": ["whois_lookup", "dns_enum", "subdomain_discovery"],
            "osint": ["whois_lookup", "dns_enum", "subdomain_discovery", "shodan_search"],
            "information gathering": ["whois_lookup", "dns_enum"],
            
            # Shodan
            "shodan": ["shodan_search"],
            "internet scan": ["shodan_search"],
        }
    
    def create_subtasks(self, 
                       task_type: str, 
                       target: str, 
                       user_prompt: str) -> List[Dict[str, Any]]:
        """Create subtasks based on user prompt analysis.
        
        Args:
            task_type: Task type (recon, exploitation, analysis, mixed)
            target: Target domain/IP
            user_prompt: Original user prompt
            
        Returns:
            List of subtask dictionaries
        """
        user_lower = user_prompt.lower()
        
        # Find matching tools
        matched_tools = self._find_matching_tools(user_lower)
        
        # Fallback to defaults if no matches
        if not matched_tools:
            matched_tools = self._get_default_tools(task_type)
        
        # Filter to available tools
        available_tools = self._filter_available_tools(matched_tools)
        
        # If still empty, use category-based fallback
        if not available_tools:
            available_tools = self._get_category_tools(task_type)
        
        # Create subtasks
        return self._build_subtasks(available_tools, target, user_prompt, task_type)
    
    def create_proactive_plan(self, 
                             state: Dict[str, Any], 
                             user_prompt: str, 
                             session_context=None) -> None:
        """Create proactive pentest plan when model fails.
        
        This ensures the agent is PROACTIVE - always creates a plan
        when user provides a target.
        
        Args:
            state: Graph state to update
            user_prompt: User's input prompt
            session_context: Current session context
        """
        target = self._extract_target(state, user_prompt, session_context)
        
        if not target:
            return
        
        # Detect intent
        intent = self._detect_intent(user_prompt)
        
        # Create subtasks based on intent
        if intent["is_attack"] or intent["is_general"]:
            subtasks = self._create_full_pentest_subtasks(target)
            task_type = "mixed"
        elif intent["is_recon"]:
            subtasks = self._create_recon_subtasks(target)
            task_type = "recon"
        elif intent["is_scan"]:
            subtasks = self._create_scan_subtasks(target)
            task_type = "scan"
        else:
            # Default: keyword-based subtasks
            subtasks = self.create_subtasks("recon", target, user_prompt)
            task_type = "recon"
        
        if subtasks:
            state["analysis"] = {
                "user_intent": f"Security assessment of {target}",
                "intent_type": "request",
                "task_type": task_type,
                "complexity": "medium",
                "needs_tools": True,
                "can_answer_directly": False
            }
            state["subtasks"] = subtasks
            
            if self.stream_callback:
                task_names = ', '.join([st['name'] for st in subtasks])
                self.stream_callback("model_response", "system", 
                    f"✅ Created pentest plan for {target}: {task_names}")
    
    def _find_matching_tools(self, user_lower: str) -> set:
        """Find tools matching keywords in user prompt."""
        matched = set()
        for keyword, tools in self.keyword_to_tools.items():
            if keyword in user_lower:
                matched.update(tools)
        return matched
    
    def _get_default_tools(self, task_type: str) -> set:
        """Get default tools for task type."""
        defaults = {
            "recon": ["whois_lookup", "dns_enum", "subdomain_discovery"],
            "exploitation": ["nmap_scan"],
            "analysis": ["nmap_scan"],
            "mixed": ["whois_lookup", "dns_enum", "nmap_scan"]
        }
        return set(defaults.get(task_type, defaults["recon"]))
    
    def _filter_available_tools(self, tools: set) -> List[str]:
        """Filter tools to only those available in registry."""
        from tools.registry import get_registry
        registry = get_registry()
        
        available = []
        for tool_name in tools:
            tool = registry.get_tool(tool_name)
            if tool:
                available.append(tool_name)
        return available
    
    def _get_category_tools(self, task_type: str) -> List[str]:
        """Get tools by category as fallback."""
        from tools.registry import get_registry
        registry = get_registry()
        
        category_map = {
            "recon": ["recon", "osint"],
            "exploitation": ["exploitation"],
            "analysis": ["scanning", "analysis"],
            "mixed": ["recon", "scanning"]
        }
        
        categories = category_map.get(task_type, ["recon"])
        available = []
        
        for tool in registry.list_tools():
            if tool.category in categories and len(available) < 3:
                available.append(tool.name)
        
        return available
    
    def _build_subtasks(self, tools: List[str], target: str, 
                       user_prompt: str, task_type: str) -> List[Dict[str, Any]]:
        """Build subtask dictionaries from tool list."""
        from tools.registry import get_registry
        registry = get_registry()
        
        user_lower = user_prompt.lower()
        subtasks = []
        
        # Extract action verb
        action_match = re.search(
            r'\b(find|scan|check|discover|enumerate|lookup|get|analyze|test|attack|exploit|assess|audit)\b',
            user_lower
        )
        action = action_match.group(1) if action_match else "Execute"
        
        # Determine agent
        agent_map = {
            "recon": "recon_agent",
            "exploitation": "exploit_agent",
            "analysis": "analysis_agent",
            "mixed": "recon_agent"
        }
        agent = agent_map.get(task_type, "recon_agent")
        
        for i, tool_name in enumerate(tools[:5]):  # Limit to 5
            tool = registry.get_tool(tool_name)
            tool_desc = tool.description if tool else tool_name
            
            subtasks.append({
                "id": f"subtask_{uuid.uuid4().hex[:8]}",
                "name": f"{action.capitalize()} {tool_name.replace('_', ' ')} on {target}",
                "description": f"{tool_desc} on {target}",
                "type": "tool_execution",
                "required_tools": [tool_name],
                "required_agent": agent,
                "priority": "high" if i == 0 else "medium"
            })
        
        return subtasks
    
    def _extract_target(self, state: Dict[str, Any], user_prompt: str, 
                       session_context) -> Optional[str]:
        """Extract target from various sources."""
        # 1. From session context
        if session_context:
            target = session_context.get_target()
            if target:
                return target
        
        # 2. From input normalizer
        try:
            from utils.input_normalizer import InputNormalizer
            normalizer = InputNormalizer()
            normalized = normalizer.normalize_input(user_prompt, verify_domains=False)
            targets = normalized.get("targets", [])
            if targets:
                return targets[0]
        except Exception:
            pass
        
        # 3. From target_clarification
        clarification = state.get("target_clarification", {})
        if clarification.get("verified_domain"):
            return clarification["verified_domain"]
        
        # 4. Regex extraction
        domain_pattern = r'\b([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.(?:[a-zA-Z]{2,}|co\.(?:za|uk|jp|kr|nz|au)))\b'
        matches = re.findall(domain_pattern, user_prompt)
        if matches:
            return matches[0]
        
        return None
    
    def _detect_intent(self, user_prompt: str) -> Dict[str, bool]:
        """Detect intent from user prompt keywords."""
        user_lower = user_prompt.lower()
        
        return {
            "is_recon": any(kw in user_lower for kw in 
                ["recon", "enumerate", "subdomain", "osint", "info", "whois", "dns"]),
            "is_scan": any(kw in user_lower for kw in 
                ["scan", "port", "service", "nmap"]),
            "is_attack": any(kw in user_lower for kw in 
                ["attack", "exploit", "vuln", "test", "assess", "pentest"]),
            "is_general": any(kw in user_lower for kw in 
                ["check", "analyze", "investigate", "look"])
        }
    
    def _create_full_pentest_subtasks(self, target: str) -> List[Dict[str, Any]]:
        """Create full pentest flow subtasks."""
        return [
            {
                "id": "subtask_recon",
                "name": "Reconnaissance & OSINT",
                "description": f"Gather information about {target}",
                "type": "tool_execution",
                "required_tools": ["whois_lookup", "dns_enum"],
                "required_agent": "recon_agent",
                "priority": "high"
            },
            {
                "id": "subtask_subdomain",
                "name": "Subdomain Enumeration",
                "description": f"Find subdomains of {target}",
                "type": "tool_execution",
                "required_tools": ["subdomain_discovery"],
                "required_agent": "recon_agent",
                "priority": "high"
            },
            {
                "id": "subtask_scan",
                "name": "Port & Service Scanning",
                "description": f"Scan ports and services on {target}",
                "type": "tool_execution",
                "required_tools": ["nmap_scan"],
                "required_agent": "recon_agent",
                "dependencies": ["subtask_recon"],
                "priority": "high"
            }
        ]
    
    def _create_recon_subtasks(self, target: str) -> List[Dict[str, Any]]:
        """Create reconnaissance subtasks."""
        return [
            {
                "id": "subtask_recon",
                "name": "Reconnaissance & OSINT",
                "description": f"Gather information about {target}",
                "type": "tool_execution",
                "required_tools": ["whois_lookup", "dns_enum", "subdomain_discovery"],
                "required_agent": "recon_agent",
                "priority": "high"
            }
        ]
    
    def _create_scan_subtasks(self, target: str) -> List[Dict[str, Any]]:
        """Create scanning subtasks."""
        return [
            {
                "id": "subtask_scan",
                "name": "Port & Service Scanning",
                "description": f"Scan ports and services on {target}",
                "type": "tool_execution",
                "required_tools": ["nmap_scan"],
                "required_agent": "recon_agent",
                "priority": "high"
            }
        ]
