"""
Message Templates for Target Clarification

Centralized message templates replacing hardcoded strings.
Supports future i18n by keeping all user-facing text in one place.
"""

from typing import List, Optional, Dict, Any


class ClarificationMessages:
    """Message templates for target clarification workflow."""
    
    # Candidate discovery messages
    CANDIDATES_FOUND = "I found {count} potential matching companies/organizations:\n\n"
    CANDIDATE_LINE = "{index}. {name}{country_suffix} – domain: {domain}{extra}\n"
    CANDIDATES_PROMPT = "\nWhich company are you referring to? (Enter 1-{count} or provide more details)"
    
    # Confirmation messages
    CONFIRM_HEADER = "You are referring to:\n"
    CONFIRM_LEGAL_NAME = "- Legal Name: {legal_name}\n"
    CONFIRM_COUNTRY = "- Country: {country}\n"
    CONFIRM_DOMAIN = "- Domain: {domain}\n"
    CONFIRM_ASN = "- ASN: {asn}\n"
    CONFIRM_IP_RANGES = "- IP Ranges: {ip_ranges}\n"
    CONFIRM_CONFIDENCE = "\nConfidence: {score}/10\n"
    CONFIRM_CONFLICTS = "\nNote: Found some conflicts: {conflicts}\n"
    CONFIRM_QUESTION = "\nIs this correct?"
    
    # Error/fallback messages
    SEARCH_FAILED = "Note: Web search failed: {error}"
    AUTO_SEARCH_FAILED = "Note: Automatic domain search failed: {error}. Please provide the domain name."
    NO_VALID_DOMAIN = "Note: Could not find a valid domain from search results. Please provide the domain name."
    NO_TOOL_CALL = "Note: Could not automatically search for domain. Please provide the domain name."
    
    # Information request messages
    NEED_MORE_INFO = "I need more information to identify {target}.\n\n"
    PROVIDE_OPTIONS = "Please provide one of the following:\n"
    ALTERNATIVE_HEADER = "Alternatively, you can provide:\n"
    ALTERNATIVE_DOMAIN = "- The domain name (e.g., example.com)\n"
    ALTERNATIVE_IP = "- The IP address (e.g., 192.168.1.1)\n"
    ALTERNATIVE_URL = "- The website URL (e.g., https://example.com)\n"
    ALTERNATIVE_CONTEXT = "- Additional context like company location or industry"
    
    # Status messages
    FOUND_FROM_DB = "Found verified target from database: {domain}"
    SEARCHING = "Searching for information about {target}... Please provide more details if available."
    
    @classmethod
    def format_candidates_found(
        cls, 
        candidates: List[Dict[str, Any]]
    ) -> str:
        """Format multiple candidates for user selection.
        
        Args:
            candidates: List of candidate dicts with domain, confidence, etc.
            
        Returns:
            Formatted message string
        """
        if not candidates:
            return ""
        
        message = cls.CANDIDATES_FOUND.format(count=len(candidates))
        
        for i, candidate in enumerate(candidates, 1):
            domain = candidate.get("domain", "N/A")
            legal_name = candidate.get("legal_name", "")
            country = candidate.get("country", "")
            confidence = candidate.get("confidence", 0)
            asn = candidate.get("asn")
            ip_ranges = candidate.get("ip_ranges", [])
            
            # Build name part
            name = legal_name if legal_name else domain
            
            # Build country suffix
            country_suffix = f" – {country}" if country else ""
            
            # Build extra info
            extras = []
            if asn:
                extras.append(f"ASN: {asn}")
            if ip_ranges:
                extras.append(f"IP ranges: {', '.join(ip_ranges[:3])}")
            extras.append(f"confidence: {int(confidence * 100)}%")
            
            extra = " – " + " – ".join(extras) if extras else ""
            
            message += cls.CANDIDATE_LINE.format(
                index=i,
                name=name,
                country_suffix=country_suffix,
                domain=domain,
                extra=extra
            )
        
        message += cls.CANDIDATES_PROMPT.format(count=len(candidates))
        
        return message
    
    @classmethod
    def format_confirmation(
        cls,
        legal_name: Optional[str] = None,
        country: Optional[str] = None,
        domain: str = "",
        asn: Optional[str] = None,
        ip_ranges: Optional[List[str]] = None,
        confidence: float = 0.0,
        conflicts: Optional[List[str]] = None
    ) -> str:
        """Format confirmation message with entity details.
        
        Args:
            legal_name: Legal company name
            country: Country/region
            domain: Domain name
            asn: ASN number
            ip_ranges: List of IP ranges
            confidence: Confidence score (0-1)
            conflicts: List of validation conflicts
            
        Returns:
            Formatted confirmation message
        """
        message = cls.CONFIRM_HEADER
        
        if legal_name:
            message += cls.CONFIRM_LEGAL_NAME.format(legal_name=legal_name)
        if country:
            message += cls.CONFIRM_COUNTRY.format(country=country)
        
        message += cls.CONFIRM_DOMAIN.format(domain=domain)
        
        if asn:
            message += cls.CONFIRM_ASN.format(asn=asn)
        if ip_ranges:
            message += cls.CONFIRM_IP_RANGES.format(ip_ranges=", ".join(ip_ranges))
        
        message += cls.CONFIRM_CONFIDENCE.format(score=int(confidence * 10))
        
        if conflicts:
            message += cls.CONFIRM_CONFLICTS.format(conflicts=", ".join(conflicts))
        
        message += cls.CONFIRM_QUESTION
        
        return message
    
    @classmethod
    def format_need_more_info(
        cls,
        target: str = "the target",
        suggested_questions: Optional[List[str]] = None
    ) -> str:
        """Format message requesting more information.
        
        Args:
            target: Target name/description
            suggested_questions: Optional list of suggested questions
            
        Returns:
            Formatted request message
        """
        message = cls.NEED_MORE_INFO.format(target=target)
        
        if suggested_questions:
            message += cls.PROVIDE_OPTIONS
            for i, question in enumerate(suggested_questions[:3], 1):
                message += f"{i}. {question}\n"
            message += "\n"
        
        message += cls.ALTERNATIVE_HEADER
        message += cls.ALTERNATIVE_DOMAIN
        message += cls.ALTERNATIVE_IP
        message += cls.ALTERNATIVE_URL
        message += cls.ALTERNATIVE_CONTEXT
        
        return message
