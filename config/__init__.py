"""Configuration modules."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load Ollama configuration.
    
    Args:
        config_path: Path to config file. Defaults to ollama_config.yaml
        
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = Path(__file__).parent / "ollama_config.yaml"
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
