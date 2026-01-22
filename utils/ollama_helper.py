"""Utility functions for Ollama model management."""

import requests
from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml


def get_ollama_base_url() -> str:
    """Get Ollama base URL from config or environment."""
    try:
        from config import load_config
        config = load_config()
        base_url = config.get('ollama', {}).get('base_url', 'http://localhost:11434')
    except Exception:
        # Fallback to environment or default
        import os
        base_url = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        if not base_url.startswith('http'):
            base_url = f'http://{base_url}'
    
    return base_url


def list_ollama_models(base_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all available Ollama models.
    
    Args:
        base_url: Ollama base URL (defaults to config)
        
    Returns:
        List of model dictionaries with 'name' and 'model' fields
    """
    if base_url is None:
        base_url = get_ollama_base_url()
    
    try:
        # Remove trailing slash if present
        base_url = base_url.rstrip('/')
        url = f"{base_url}/api/tags"
        
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        models = data.get('models', [])
        
        return models
    except requests.exceptions.RequestException as e:
        # Return empty list if connection fails
        return []
    except Exception as e:
        # Return empty list on any error
        return []


def get_model_names(base_url: Optional[str] = None) -> List[str]:
    """Get list of model names from Ollama.
    
    Args:
        base_url: Ollama base URL (defaults to config)
        
    Returns:
        List of model names (e.g., ['mistral:latest', 'llama3.1:8b'])
    """
    models = list_ollama_models(base_url)
    model_names = []
    
    for model in models:
        # Model dict has 'name' field which is the full model name
        name = model.get('name', '')
        if name:
            model_names.append(name)
    
    return sorted(model_names)


def check_model_exists(model_name: str, base_url: Optional[str] = None) -> bool:
    """Check if a specific model exists in Ollama.
    
    Args:
        model_name: Model name to check (e.g., 'mistral:latest')
        base_url: Ollama base URL (defaults to config)
        
    Returns:
        True if model exists, False otherwise
    """
    model_names = get_model_names(base_url)
    return model_name in model_names
