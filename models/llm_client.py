"""
Ollama LLM Client - Direct HTTP API (No LangChain Guardrails)

This module provides direct Ollama HTTP API access without LangChain's
safety filters. Essential for penetration testing tasks.

IMPORTANT: LangChain has been removed to prevent model refusal caused by
its policy layers. This client calls Ollama's HTTP API directly.
"""

from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import json
import requests
import yaml


class OllamaLLMClient:
    """Direct Ollama HTTP API client - NO LangChain guardrails.
    
    This client bypasses LangChain's safety layers by making direct HTTP requests
    to the Ollama API. This is essential for penetration testing tasks where
    LangChain's policy filters may cause model refusal.
    """
    
    def __init__(self, 
                 model_name: str,
                 base_url: Optional[str] = None,
                 config_path: Optional[Path] = None,
                 **default_options):
        """Initialize Ollama LLM client.
        
        Args:
            model_name: Ollama model name (e.g., "mistral:latest", "qwen2.5:7b")
            base_url: Ollama base URL (defaults to config)
            config_path: Optional path to config file
            **default_options: Default options (temperature, top_p, etc.)
        """
        self.model_name = model_name
        self.config = self._load_config(config_path)
        
        if base_url is None:
            base_url = self.config.get('ollama', {}).get('base_url', 'http://localhost:11434')
        
        self.base_url = base_url.rstrip('/')
        self.timeout = self.config.get('ollama', {}).get('timeout', 300)
        self.default_options = {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "num_predict": 2048,
            "repeat_penalty": 1.1,
            **default_options
        }
    
    def _load_config(self, config_path: Optional[Path] = None) -> Dict[str, Any]:
        """Load config from file."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "ollama_config.yaml"
        
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception:
            return {"ollama": {"base_url": "http://localhost:11434", "timeout": 300}}
    
    def _build_options(self, **override_options) -> Dict[str, Any]:
        """Build options dict merging defaults with overrides."""
        return {**self.default_options, **override_options}
    
    def generate(self,
                 messages: List[Dict[str, str]],
                 stream: bool = False,
                 stream_callback: Optional[Callable[[str], None]] = None,
                 **options) -> Dict[str, Any]:
        """Generate response using direct Ollama HTTP API.
        
        NO LANGCHAIN - Direct HTTP calls to bypass guardrails.
        
        Args:
            messages: List of dict messages with 'role' and 'content'
            stream: Whether to stream the response
            stream_callback: Optional callback for streaming chunks
            **options: Additional options (temperature, top_p, etc.)
            
        Returns:
            Dict with 'content', 'message', and other metadata
        """
        url = f"{self.base_url}/api/chat"
        merged_options = self._build_options(**options)
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": merged_options.get("temperature", 0.7),
                "top_p": merged_options.get("top_p", 0.9),
                "top_k": merged_options.get("top_k", 40),
                "num_predict": merged_options.get("num_predict", 2048),
                "repeat_penalty": merged_options.get("repeat_penalty", 1.1),
            }
        }
        
        try:
            if stream:
                return self._stream_response(url, payload, stream_callback)
            else:
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                
                data = response.json()
                message = data.get("message", {})
                content = message.get("content", "")
                
                return {
                    "success": True,
                    "content": content,
                    "message": message
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": f"Request timeout after {self.timeout}s",
                "content": None,
                "message": None
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": f"Cannot connect to Ollama at {self.base_url}",
                "content": None,
                "message": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "message": None
            }
    
    def _stream_response(self,
                        url: str,
                        payload: Dict[str, Any],
                        callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Stream response from Ollama API."""
        try:
            response = requests.post(url, json=payload, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            content = ""
            
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        chunk_content = chunk.get("message", {}).get("content", "")
                        
                        if chunk_content:
                            content += chunk_content
                            if callback:
                                callback(chunk_content)
                        
                        if chunk.get("done", False):
                            break
                            
                    except json.JSONDecodeError:
                        continue
            
            return {
                "success": True,
                "content": content,
                "message": {"role": "assistant", "content": content}
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "message": None
            }
    
    def generate_with_tools(self,
                            messages: List[Dict[str, str]],
                            tools: List[Dict[str, Any]],
                            **options) -> Dict[str, Any]:
        """Generate response with native Ollama tool calling.
        
        Uses Ollama's native function calling API - NO LANGCHAIN.
        
        Args:
            messages: List of dict messages
            tools: List of tool definitions in Ollama format
            **options: Additional options
            
        Returns:
            Dict with 'content', 'tool_calls', and 'message'
        """
        url = f"{self.base_url}/api/chat"
        
        # Use lower temperature for tool calling
        tool_options = {
            "temperature": options.get('temperature', 0.0),
            "top_p": options.get('top_p', 0.9),
            "top_k": options.get('top_k', 40),
            "num_predict": options.get('num_predict', 512),
        }
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": tool_options
        }
        
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            message = data.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            
            return {
                "success": True,
                "content": content,
                "tool_calls": tool_calls,
                "message": message
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "tool_calls": [],
                "message": None
            }


class OllamaEmbeddingClient:
    """Ollama embeddings client using direct HTTP API.
    
    Note: Embeddings don't have safety issues, but we use direct API
    for consistency.
    """
    
    def __init__(self, 
                 model_name: str = "nomic-embed-text", 
                 base_url: Optional[str] = None):
        """Initialize Ollama embeddings client.
        
        Args:
            model_name: Embedding model name (default: nomic-embed-text)
            base_url: Ollama base URL
        """
        self.model_name = model_name
        self.base_url = (base_url or "http://localhost:11434").rstrip('/')
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        url = f"{self.base_url}/api/embeddings"
        
        try:
            response = requests.post(
                url,
                json={"model": self.model_name, "prompt": text},
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("embedding", [])
            
        except Exception as e:
            print(f"Error embedding query: {e}")
            return []
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in texts:
            embedding = self.embed_query(text)
            embeddings.append(embedding)
        return embeddings
