"""LangChain Ollama client wrapper for consistent LLM access."""

from typing import Dict, Any, List, Optional, Callable
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from config import load_config
from pathlib import Path


class OllamaLLMClient:
    """LangChain-based Ollama client with streaming and function calling support.
    
    This wrapper provides a consistent interface for all Ollama model interactions,
    replacing direct `ollama.chat()` calls with LangChain's ChatOllama.
    """
    
    def __init__(self, 
                 model_name: str,
                 base_url: Optional[str] = None,
                 config_path: Optional[Path] = None,
                 **default_options):
        """Initialize Ollama LLM client.
        
        Args:
            model_name: Ollama model name (e.g., "mistral:latest", "llama3.1:8b")
            base_url: Ollama base URL (defaults to config)
            config_path: Optional path to config file
            **default_options: Default options (temperature, top_p, etc.)
        """
        self.model_name = model_name
        self.config = load_config(config_path) if config_path else self._load_default_config()
        
        if base_url is None:
            base_url = self.config['ollama']['base_url']
        
        self.base_url = base_url
        self.default_options = default_options
        self._llm = None  # Lazy initialization
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default config."""
        import yaml
        config_path = Path(__file__).parent.parent / "config" / "ollama_config.yaml"
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _get_llm(self, **override_options) -> ChatOllama:
        """Lazy initialization of ChatOllama with options.
        
        Args:
            **override_options: Options to override defaults
            
        Returns:
            ChatOllama instance
        """
        # Merge default options with overrides
        options = {**self.default_options, **override_options}
        
        # Extract LangChain-compatible options
        temperature = options.get('temperature', 0.7)
        top_p = options.get('top_p', 0.9)
        top_k = options.get('top_k', 40)
        num_predict = options.get('num_predict', 2048)
        repeat_penalty = options.get('repeat_penalty', 1.1)
        
        # Create ChatOllama instance
        return ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            num_predict=num_predict,
            repeat_penalty=repeat_penalty,
        )
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List:
        """Convert dict messages to LangChain message objects.
        
        Args:
            messages: List of dict messages with 'role' and 'content'
            
        Returns:
            List of LangChain message objects
        """
        langchain_messages = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'system':
                langchain_messages.append(SystemMessage(content=content))
            elif role == 'user':
                langchain_messages.append(HumanMessage(content=content))
            elif role == 'assistant':
                langchain_messages.append(AIMessage(content=content))
            else:
                # Default to human message
                langchain_messages.append(HumanMessage(content=content))
        
        return langchain_messages
    
    def generate(self,
                 messages: List[Dict[str, str]],
                 stream: bool = False,
                 stream_callback: Optional[Callable[[str], None]] = None,
                 **options) -> Dict[str, Any]:
        """Generate response from messages.
        
        Args:
            messages: List of dict messages with 'role' and 'content'
            stream: Whether to stream the response
            stream_callback: Optional callback for streaming chunks
            **options: Additional options (temperature, top_p, etc.)
            
        Returns:
            Dict with 'content', 'message', and other metadata
        """
        llm = self._get_llm(**options)
        langchain_messages = self._convert_messages(messages)
        
        try:
            if stream:
                # Streaming mode
                content = ""
                for chunk in llm.stream(langchain_messages):
                    chunk_content = chunk.content
                    if chunk_content:
                        content += chunk_content
                        if stream_callback:
                            stream_callback(chunk_content)
                
                return {
                    "success": True,
                    "content": content,
                    "message": {"content": content, "role": "assistant"}
                }
            else:
                # Non-streaming mode
                response = llm.invoke(langchain_messages)
                content = response.content if hasattr(response, 'content') else str(response)
                
                return {
                    "success": True,
                    "content": content,
                    "message": {"content": content, "role": "assistant"}
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
        """Generate response with function calling support (for FunctionGemma).
        
        Note: FunctionGemma requires direct API calls for tool calling.
        This method uses direct ollama.chat() for compatibility.
        
        Args:
            messages: List of dict messages
            tools: List of tool definitions in Ollama format
            **options: Additional options
            
        Returns:
            Dict with 'content', 'tool_calls', and 'message'
        """
        import ollama
        
        # For function calling, use direct ollama.chat() as LangChain
        # doesn't fully support Ollama's tool calling format yet
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=messages,
                tools=tools,
                options={
                    "temperature": options.get('temperature', 0.0),
                    "top_p": options.get('top_p', 0.9),
                    "top_k": options.get('top_k', 40),
                    "num_predict": options.get('num_predict', 512),
                }
            )
            
            message = response.get('message', {})
            content = message.get('content', '')
            tool_calls = message.get('tool_calls', [])
            
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
    """LangChain-based Ollama embeddings client."""
    
    def __init__(self, model_name: str = "nomic-embed-text", base_url: Optional[str] = None):
        """Initialize Ollama embeddings client.
        
        Args:
            model_name: Embedding model name (default: nomic-embed-text)
            base_url: Ollama base URL
        """
        self.model_name = model_name
        self.base_url = base_url or "http://localhost:11434"
        self._embeddings = None
        
        # Check if model exists, if not, try to pull it
        self._ensure_model_exists()
    
    def _ensure_model_exists(self):
        """Ensure embedding model exists, pull if needed."""
        try:
            import ollama
            # Try to check if model exists
            try:
                ollama.show(self.model_name)
            except:
                # Model doesn't exist, try to pull it
                import warnings
                warnings.warn(
                    f"Embedding model '{self.model_name}' not found. "
                    f"Please run: ollama pull {self.model_name}",
                    UserWarning
                )
        except ImportError:
            # ollama not available, skip check
            pass
        except Exception as e:
            # Ignore errors, will fail later if model truly doesn't exist
            pass
    
    def _get_embeddings(self) -> OllamaEmbeddings:
        """Lazy initialization of OllamaEmbeddings."""
        if self._embeddings is None:
            self._embeddings = OllamaEmbeddings(
                model=self.model_name,
                base_url=self.base_url
            )
        return self._embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            embeddings = self._get_embeddings()
            return embeddings.embed_query(text)
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
        try:
            embeddings = self._get_embeddings()
            return embeddings.embed_documents(texts)
        except Exception as e:
            print(f"Error embedding documents: {e}")
            return [[] for _ in texts]
