"""
JSON Extraction Utilities

Centralized JSON parsing with multiple fallback patterns.
Used across the codebase to eliminate duplicate code.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from text with multiple fallback patterns.
    
    Handles:
    - JSON in ```json ... ``` code blocks
    - JSON in ``` ... ``` code blocks
    - Plain JSON object {...}
    - JSON array [...]
    - Thinking tags removal
    
    Args:
        text: Raw text that may contain JSON
        
    Returns:
        Parsed dict or None if extraction fails
    """
    if not text:
        return None
    
    # Remove thinking/reasoning tags
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)
    text = re.sub(r'<output>|</output>', '', text)
    
    # Try extraction patterns in order
    patterns = [
        (r'```json\s*([\{\[].*?[\}\]])\s*```', "json code block"),
        (r'```\s*([\{\[].*?[\}\]])\s*```', "code block"),
        (r'(\{\s*"[^"]+"\s*:.*\})', "json object"),
        (r'(\[\s*\{.*\}\s*\])', "json array"),
    ]
    
    for pattern, pattern_name in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            result = _try_parse_json(match)
            if result is not None:
                logger.debug(f"JSON extracted via {pattern_name}")
                return result
    
    # Last resort: find first { and last }
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end > brace_start:
        candidate = text[brace_start:brace_end + 1]
        result = _try_parse_json(candidate)
        if result is not None:
            logger.debug("JSON extracted via brace matching")
            return result
    
    logger.debug("No JSON found in text")
    return None


def _try_parse_json(json_str: str) -> Optional[Dict[str, Any]]:
    """Try to parse JSON string with cleanup.
    
    Args:
        json_str: Raw JSON string
        
    Returns:
        Parsed dict or None
    """
    if not json_str:
        return None
    
    try:
        # Cleanup
        json_str = json_str.strip()
        json_str = re.sub(r',\s*}', '}', json_str)  # Trailing comma before }
        json_str = re.sub(r',\s*]', ']', json_str)  # Trailing comma before ]
        json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)  # Control chars
        
        parsed = json.loads(json_str)
        
        # Normalize to dict
        if isinstance(parsed, list):
            return {"items": parsed}
        elif isinstance(parsed, dict):
            return parsed
        else:
            return {"value": parsed}
            
    except json.JSONDecodeError as e:
        logger.debug(f"JSON parse error: {e}")
        return None


def extract_json_field(text: str, field: str, default: Any = None) -> Any:
    """Extract a specific field from JSON in text.
    
    Args:
        text: Text containing JSON
        field: Field name to extract
        default: Default value if not found
        
    Returns:
        Field value or default
    """
    data = extract_json_from_text(text)
    if data is None:
        return default
    return data.get(field, default)


def safe_json_loads(text: str, default: Any = None) -> Any:
    """Safe JSON loading with default value.
    
    Args:
        text: JSON string
        default: Default value on failure
        
    Returns:
        Parsed value or default
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def extract_tools_from_response(text: str) -> List[Dict[str, Any]]:
    """Extract tool calls from LLM response.
    
    Handles various formats:
    - {"tools": [...]}
    - {"tool_calls": [...]}
    - [{"name": "...", ...}]
    - {"name": "...", ...}
    
    Args:
        text: LLM response text
        
    Returns:
        List of tool call dicts
    """
    data = extract_json_from_text(text)
    if data is None:
        return []
    
    # Check for tools array
    if "tools" in data:
        tools = data["tools"]
        return tools if isinstance(tools, list) else []
    
    # Check for tool_calls array
    if "tool_calls" in data:
        tools = data["tool_calls"]
        return tools if isinstance(tools, list) else []
    
    # Check for items (from array normalization)
    if "items" in data:
        items = data["items"]
        if isinstance(items, list) and items and "name" in items[0]:
            return items
    
    # Single tool object
    if "name" in data:
        return [data]
    
    return []
