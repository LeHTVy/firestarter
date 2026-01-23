"""
Entity Information Dataclasses

Structured data types for the target clarification pipeline.
Replaces raw dict usage with typed, validated dataclasses.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class EntityCandidate:
    """A candidate entity from database or search results."""
    
    domain: str
    source: str = "unknown"
    confidence: float = 0.0
    legal_name: Optional[str] = None
    country: Optional[str] = None
    asn: Optional[str] = None
    ip_ranges: List[str] = field(default_factory=list)
    context: Optional[str] = None
    conversation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntityCandidate":
        """Create from dictionary."""
        return cls(
            domain=data.get("domain", ""),
            source=data.get("source", "unknown"),
            confidence=float(data.get("confidence", 0.0)),
            legal_name=data.get("legal_name"),
            country=data.get("country"),
            asn=data.get("asn"),
            ip_ranges=data.get("ip_ranges", []),
            context=data.get("context"),
            conversation_id=data.get("conversation_id")
        )


@dataclass
class EntityInfo:
    """Extracted entity information from search results."""
    
    legal_name: str = ""
    country: str = ""
    domain: str = ""
    asn: Optional[str] = None
    ip_ranges: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntityInfo":
        """Create from dictionary with validation."""
        return cls(
            legal_name=data.get("legal_name", "") or "",
            country=data.get("country", "") or "",
            domain=data.get("domain", "") or "",
            asn=data.get("asn"),
            ip_ranges=data.get("ip_ranges", []) or [],
            confidence=min(1.0, max(0.0, float(data.get("confidence", 0.0))))
        )
    
    @classmethod
    def empty(cls) -> "EntityInfo":
        """Create an empty entity info with zero confidence."""
        return cls(confidence=0.0)
    
    def is_valid(self) -> bool:
        """Check if entity has valid domain."""
        return bool(self.domain and len(self.domain) > 3)


@dataclass
class ValidationResult:
    """Cross-check validation result."""
    
    valid: bool = False
    confidence: float = 0.0
    conflicts: List[str] = field(default_factory=list)
    validated_info: Optional[EntityInfo] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "valid": self.valid,
            "confidence": self.confidence,
            "conflicts": self.conflicts
        }
        if self.validated_info:
            result["validated_info"] = self.validated_info.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationResult":
        """Create from dictionary."""
        validated_info = None
        if data.get("validated_info"):
            validated_info = EntityInfo.from_dict(data["validated_info"])
        
        return cls(
            valid=bool(data.get("valid", False)),
            confidence=float(data.get("confidence", 0.0)),
            conflicts=data.get("conflicts", []),
            validated_info=validated_info
        )
    
    @classmethod
    def failed(cls, reason: str = "Validation error") -> "ValidationResult":
        """Create a failed validation result."""
        return cls(valid=False, confidence=0.0, conflicts=[reason])


@dataclass
class ExtractedQuery:
    """Extracted company name and location from user prompt."""
    
    company_name: Optional[str] = None
    location: Optional[str] = None
    
    def has_info(self) -> bool:
        """Check if any info was extracted."""
        return bool(self.company_name or self.location)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractedQuery":
        """Create from dictionary."""
        return cls(
            company_name=data.get("company_name"),
            location=data.get("location")
        )


@dataclass
class ClarificationResult:
    """Result of the clarification pipeline."""
    
    is_ambiguous: bool = True
    verified_domain: Optional[str] = None
    candidates: List[EntityCandidate] = field(default_factory=list)
    ambiguity_score: float = 1.0
    message: str = ""
    needs_user_input: bool = False
    entity_info: Optional[EntityInfo] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state storage."""
        return {
            "is_ambiguous": self.is_ambiguous,
            "verified_domain": self.verified_domain,
            "candidates": [c.to_dict() for c in self.candidates],
            "ambiguity_score": self.ambiguity_score,
            "message": self.message,
            "needs_user_input": self.needs_user_input,
            "entity_info": self.entity_info.to_dict() if self.entity_info else None
        }
