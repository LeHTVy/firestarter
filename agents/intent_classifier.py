"""Intent classifier for distinguishing security tasks, memory queries, and questions."""

import json
import re
from typing import Dict, Any, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from config import load_config
from models.llm_client import OllamaLLMClient

# Constants - Enhanced with 3 intents matching rutx pattern
INTENT_SECURITY_TASK = "security_task"  # Perform recon/scan/exploit action
INTENT_MEMORY_QUERY = "memory_query"    # Retrieve stored results
INTENT_QUESTION = "question"            # Seeking information/explanation

# Legacy aliases for backward compatibility
INTENT_REQUEST = INTENT_SECURITY_TASK

VALID_INTENTS = [INTENT_SECURITY_TASK, INTENT_MEMORY_QUERY, INTENT_QUESTION]

# System prompt for intent classification
SYSTEM_PROMPT = (
    "You are an expert intent classifier for a penetration testing agent. "
    "Classify user intent into exactly ONE of: security_task, memory_query, or question. "
    "Security tasks include reconnaissance, scanning, exploitation, and tool execution. "
    "Memory queries retrieve previously stored results. Questions seek information or advice. "
    "Attack/pentest keywords are ALWAYS security_task. Direct tool commands are ALWAYS security_task."
)

# Tool execution patterns for fallback classification
TOOL_EXECUTION_PATTERNS = [
    r"use\s+\w+\s+on\s+",       # "use whois on domain"
    r"use\s+\w+\s+for\s+",      # "use nmap for target"
    r"run\s+\w+\s+on\s+",       # "run nmap on target"
    r"execute\s+\w+\s+on\s+",   # "execute tool on target"
    r"scan\s+",                 # "scan example.com"
    r"attack\s+",               # "attack target.com"
    r"pentest\s+",              # "pentest example.org"
    r"find\s+subdomains",       # "find subdomains for X"
    r"enumerate\s+",            # "enumerate ports on Y"
    r"lookup\s+",               # "lookup IP for X"
]

# Memory query patterns for fallback
MEMORY_QUERY_PATTERNS = [
    r"show\s+me\s+",            # "show me the subdomains"
    r"list\s+(the\s+)?",        # "list the open ports"
    r"what\s+(did|have)\s+you\s+find",  # "what did you find"
    r"get\s+(the\s+)?results",  # "get the results"
    r"previous\s+(scan\s+)?results",  # "previous scan results"
]

# Obvious action verbs for fallback (security_task)
OBVIOUS_ACTION_VERBS = [
    "scan", "test", "run", "execute", "use", "attack", 
    "pentest", "exploit", "hack", "pwn", "enumerate",
    "find", "lookup", "discover", "assess", "probe"
]


class IntentClassifier:
    """Classifies user intent as question or request."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize intent classifier.
        
        Args:
            config_path: Path to Ollama config file
        """
        self.config = load_config(config_path) if config_path else self._load_default_config()
        # Use Mistral config (replacing Qwen3)
        self.model_config = self.config['models'].get('mistral', {
            'model_name': 'mistral:latest',
            'temperature': 0.85,
            'top_p': 0.95,
            'top_k': 50,
            'num_predict': 2048
        })
        self.ollama_base_url = self.config['ollama']['base_url']
        
        # Initialize LLM client (CRITICAL FIX)
        self.llm_client = OllamaLLMClient(
            model_name=self.model_config['model_name'],
            base_url=self.ollama_base_url,
            config_path=config_path,
            temperature=self.model_config.get('temperature', 0.85),
            top_p=self.model_config.get('top_p', 0.95),
            top_k=self.model_config.get('top_k', 50),
            num_predict=self.model_config.get('num_predict', 2048)
        )
        
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.intent_prompt_template = self.env.get_template("intent_classification.jinja2")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default config."""
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "ollama_config.yaml"
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def classify(self, user_prompt: str) -> Dict[str, Any]:
        """Classify user intent.
        
        Args:
            user_prompt: User prompt to classify
            
        Returns:
            Classification result with intent type, confidence, and reasoning
        """
        prompt = self.intent_prompt_template.render(user_prompt=user_prompt)
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # Use LangChain client
            response = self.llm_client.generate(
                messages=messages,
                stream=False,
                temperature=self.model_config.get('temperature', 0.3),
                top_p=self.model_config.get('top_p', 0.9),
                top_k=self.model_config.get('top_k', 40),
                num_predict=self.model_config.get('num_predict', 256)
            )
            
            if not response.get('success'):
                # Fallback classification
                intent = self._fallback_classify(user_prompt)
                return {
                    "success": False,
                    "intent": intent,
                    "confidence": 0.5,
                    "reasoning": f"Error during classification: {response.get('error', 'Unknown error')}",
                    "error": response.get('error', 'Unknown error')
                }
            
            content = response.get('content', '')
            
            # Extract and parse JSON from response
            json_data = self._extract_json_from_response(content)
            
            if json_data:
                # Validate and normalize intent
                intent = json_data.get("intent", "").lower()
                if intent not in VALID_INTENTS:
                    # Default based on keywords if parsing fails
                    intent = self._fallback_classify(user_prompt)
                
                return {
                    "success": True,
                    "intent": intent,
                    "confidence": float(json_data.get("confidence", 0.5)),
                    "reasoning": json_data.get("reasoning", ""),
                    "raw_response": content
                }
            else:
                # Fallback classification if JSON parsing fails
                intent = self._fallback_classify(user_prompt)
                return {
                    "success": True,
                    "intent": intent,
                    "confidence": 0.6,
                    "reasoning": "Fallback classification based on keywords",
                    "raw_response": content
                }
                
        except Exception as e:
            # Fallback on error
            intent = self._fallback_classify(user_prompt)
            return {
                "success": False,
                "intent": intent,
                "confidence": 0.5,
                "reasoning": f"Error during classification: {str(e)}",
                "error": str(e)
            }
    
    def _extract_json_from_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response (handles markdown code blocks).
        
        Args:
            content: Raw response content
            
        Returns:
            Parsed JSON dictionary or None
        """
        # Extract from ```json blocks
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            if json_end > json_start:
                content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            if json_end > json_start:
                content = content[json_start:json_end].strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    
    def _fallback_classify(self, user_prompt: str) -> str:
        """Fallback classification - ONLY used when LLM completely fails.
        
        This is a LAST RESORT. The LLM should handle 99% of cases.
        This fallback only exists for error recovery.
        
        Args:
            user_prompt: User prompt
            
        Returns:
            "security_task", "memory_query", or "question"
        """
        prompt_lower = user_prompt.lower()
        
        # Check for tool execution patterns (security_task)
        for pattern in TOOL_EXECUTION_PATTERNS:
            if re.search(pattern, prompt_lower):
                return INTENT_SECURITY_TASK
        
        # Check for memory query patterns
        for pattern in MEMORY_QUERY_PATTERNS:
            if re.search(pattern, prompt_lower):
                return INTENT_MEMORY_QUERY
        
        # Check if starts with obvious action verb (security_task)
        words = prompt_lower.split()
        if words and words[0] in OBVIOUS_ACTION_VERBS:
            return INTENT_SECURITY_TASK
        
        # Check for attack/pentest keywords anywhere (security_task)
        attack_keywords = ["attack", "pentest", "hack", "exploit", "pwn"]
        if any(kw in prompt_lower for kw in attack_keywords):
            return INTENT_SECURITY_TASK
        
        # Default to question if truly ambiguous (safer default)
        return INTENT_QUESTION

