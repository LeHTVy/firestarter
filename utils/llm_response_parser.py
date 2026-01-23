"""
LLM Response Parser

Centralized parsing of LLM responses with JSON extraction.
Uses json_utils internally but provides typed, validated output.
"""

import logging
from typing import Dict, Any, Optional, TypeVar, Type, Callable

from utils.json_utils import extract_json_from_text

logger = logging.getLogger(__name__)

T = TypeVar('T')


def parse_llm_json_response(
    response_text: str,
    expected_fields: Optional[list] = None
) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response with validation.
    
    Handles common LLM output patterns:
    - JSON in ```json ... ``` code blocks
    - JSON in ``` ... ``` code blocks  
    - Plain JSON object
    - Thinking/reasoning tags
    
    Args:
        response_text: Raw LLM response text
        expected_fields: Optional list of expected field names to validate
        
    Returns:
        Parsed dict or None if extraction/validation fails
    """
    if not response_text:
        logger.debug("Empty response text")
        return None
    
    # Use centralized JSON extraction
    parsed = extract_json_from_text(response_text)
    
    if parsed is None:
        logger.debug("Failed to extract JSON from response")
        return None
    
    # Validate expected fields if provided
    if expected_fields:
        missing = [f for f in expected_fields if f not in parsed]
        if missing:
            logger.debug(f"Missing expected fields: {missing}")
            # Still return parsed data, caller can handle missing fields
    
    return parsed


def parse_to_dataclass(
    response_text: str,
    dataclass_type: Type[T],
    from_dict_method: str = "from_dict"
) -> Optional[T]:
    """Parse LLM response directly to a dataclass.
    
    Args:
        response_text: Raw LLM response text
        dataclass_type: The dataclass type to parse into
        from_dict_method: Name of the class method to create instance from dict
        
    Returns:
        Dataclass instance or None if parsing fails
    """
    parsed = parse_llm_json_response(response_text)
    
    if parsed is None:
        return None
    
    try:
        factory = getattr(dataclass_type, from_dict_method)
        return factory(parsed)
    except (AttributeError, TypeError, KeyError) as e:
        logger.warning(f"Failed to create {dataclass_type.__name__}: {e}")
        return None


def extract_field(
    response_text: str,
    field_name: str,
    default: Any = None
) -> Any:
    """Extract a single field from LLM JSON response.
    
    Args:
        response_text: Raw LLM response text
        field_name: Name of field to extract
        default: Default value if not found
        
    Returns:
        Field value or default
    """
    parsed = parse_llm_json_response(response_text)
    
    if parsed is None:
        return default
    
    return parsed.get(field_name, default)


def extract_list_field(
    response_text: str,
    field_name: str
) -> list:
    """Extract a list field from LLM JSON response.
    
    Args:
        response_text: Raw LLM response text
        field_name: Name of list field to extract
        
    Returns:
        List value or empty list
    """
    result = extract_field(response_text, field_name, [])
    return result if isinstance(result, list) else []


class LLMResponseParser:
    """Stateful parser for LLM responses with error tracking."""
    
    def __init__(self):
        self.last_error: Optional[str] = None
        self.parse_count: int = 0
        self.success_count: int = 0
    
    def parse(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response and track statistics.
        
        Args:
            response_text: Raw LLM response text
            
        Returns:
            Parsed dict or None
        """
        self.parse_count += 1
        self.last_error = None
        
        try:
            result = parse_llm_json_response(response_text)
            if result is not None:
                self.success_count += 1
            else:
                self.last_error = "No JSON found in response"
            return result
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Parse error: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get parsing statistics."""
        return {
            "parse_count": self.parse_count,
            "success_count": self.success_count,
            "success_rate": self.success_count / max(1, self.parse_count),
            "last_error": self.last_error
        }
