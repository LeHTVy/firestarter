"""Intent classifier for distinguishing questions from requests."""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from config import load_config
from models.llm_client import OllamaLLMClient


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
            {"role": "system", "content": "You are an expert intent classifier for a penetration testing agent. You understand the semantic difference between questions (seeking information/explanation) and requests (requesting actions to be performed). You analyze the user's intent based on context, not just keywords. Direct tool execution commands (e.g., 'use whois on domain', 'run nmap on target') are ALWAYS requests, even if phrased as questions."},
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
            
            # Try to parse JSON from response
            try:
                # Extract JSON from markdown code blocks if present
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                elif "```" in content:
                    json_start = content.find("```") + 3
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                
                classification = json.loads(content)
                
                # Validate and normalize intent
                intent = classification.get("intent", "").lower()
                if intent not in ["question", "request"]:
                    # Default based on keywords if parsing fails
                    intent = self._fallback_classify(user_prompt)
                
                return {
                    "success": True,
                    "intent": intent,
                    "confidence": float(classification.get("confidence", 0.5)),
                    "reasoning": classification.get("reasoning", ""),
                    "raw_response": content
                }
            except json.JSONDecodeError:
                # Fallback classification
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
    
    def _fallback_classify(self, user_prompt: str) -> str:
        """Fallback classification - ONLY used when LLM completely fails.
        
        This is a LAST RESORT. The LLM should handle 99% of cases.
        This fallback only exists for error recovery.
        
        Args:
            user_prompt: User prompt
            
        Returns:
            "question" or "request"
        """
        prompt_lower = user_prompt.lower()
        
        # Only check for the most obvious direct tool execution patterns
        # These are unambiguous and should be caught by LLM, but we check as safety net
        import re
        tool_execution_patterns = [
            r"use\s+\w+\s+on\s+",  # "use whois on domain"
            r"use\s+\w+\s+for\s+",  # "use nmap for target"
            r"run\s+\w+\s+on\s+",   # "run nmap on target"
            r"execute\s+\w+\s+on\s+",  # "execute tool on target"
        ]
        
        for pattern in tool_execution_patterns:
            if re.search(pattern, prompt_lower):
                return "request"
        
        # Check if starts with obvious action verb (unambiguous commands)
        words = prompt_lower.split()
        if words:
            first_word = words[0]
            # Only the most obvious action verbs
            obvious_actions = ["scan", "test", "run", "execute", "use", "attack"]
            if first_word in obvious_actions:
                return "request"
        
        # Default to question if truly ambiguous (safer default)
        # The LLM should have caught this, but if we're here, it's ambiguous
        return "question"
