"""Input normalization and target extraction with typo correction."""

import re
import json
from typing import Dict, Any, List, Optional, Callable
from urllib.parse import urlparse

from utils.fuzzy_matcher import FuzzyMatcher


class InputNormalizer:
    """Normalize user input and extract targets."""
    
    # Common TLDs for domain matching
    COMMON_TLDS = [
        'com', 'org', 'net', 'edu', 'gov', 'io', 'co', 'uk', 'de', 'fr',
        'jp', 'cn', 'au', 'ca', 'in', 'br', 'mx', 'za', 'nl', 'se',
        'no', 'dk', 'fi', 'pl', 'it', 'es', 'ru', 'kr', 'tw', 'sg',
        'hk', 'nz', 'ie', 'ch', 'at', 'be', 'pt', 'gr', 'tr', 'cz'
    ]
    
    def __init__(self, search_aggregator=None, interactive_callback: Optional[Callable[[str], str]] = None, ai_model=None):
        """Initialize input normalizer.
        
        Args:
            search_aggregator: Optional SearchAggregator instance for web search
            interactive_callback: Optional callback function to ask user questions
            ai_model: Optional AI model for semantic understanding (GenericOllamaAgent) - removes need for hardcoded keywords
        """
        self.fuzzy_matcher = FuzzyMatcher()
        self.search_aggregator = search_aggregator
        self.interactive_callback = interactive_callback
        self.ai_model = ai_model  # For semantic understanding (no hardcode)
        
        # IP address pattern (with optional spaces)
        self.ip_pattern = re.compile(
            r'\b(\d{1,3})\s*\.\s*(\d{1,3})\s*\.\s*(\d{1,3})\s*\.\s*(\d{1,3})\b'
        )
        
        # Domain pattern (more flexible to catch potential misspells)
        # Match single TLD (e.g., .com, .org) or multi-part TLD (e.g., .co.za, .co.uk)
        self.domain_pattern = re.compile(
            r'\b([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.(?:' +
            '|'.join(self.COMMON_TLDS) + r')(?:\.[a-z]{2,})?)\b',
            re.IGNORECASE
        )
        
        # Potential domain pattern (catches words that look like domains)
        # This should match multi-part domains like example.co.za
        self.potential_domain_pattern = re.compile(
            r'\b([a-zA-Z0-9][a-zA-Z0-9-]{2,}(?:\.[a-zA-Z]{2,}){1,3})\b',
            re.IGNORECASE
        )
        
        # URL pattern
        self.url_pattern = re.compile(
            r'https?://[^\s]+',
            re.IGNORECASE
        )
    
    def normalize_target(self, target: str) -> str:
        """Normalize target (IP, domain, URL) by fixing spacing and typos.
        
        Args:
            target: Target string (may have spacing issues)
            
        Returns:
            Normalized target
        """
        if not target:
            return target
        
        # Remove extra whitespace
        target = ' '.join(target.split())
        
        # Fix IP addresses with spaces
        target = self._normalize_ip(target)
        
        # Fix domains (remove spaces in domain names)
        target = self._normalize_domain(target)
        
        # Fix URLs
        target = self._normalize_url(target)
        
        return target.strip()
    
    def _normalize_ip(self, text: str) -> str:
        """Normalize IP addresses by removing spaces."""
        def fix_ip(match):
            parts = [match.group(i) for i in range(1, 5)]
            return '.'.join(parts)
        
        return self.ip_pattern.sub(fix_ip, text)
    
    def _normalize_domain(self, text: str) -> str:
        """Normalize domain names by removing spaces."""
        # Simple approach: remove spaces between alphanumeric and dots
        # More sophisticated: use fuzzy matching against known domains
        text = re.sub(r'([a-zA-Z0-9])\s+\.\s*([a-zA-Z0-9])', r'\1.\2', text)
        text = re.sub(r'([a-zA-Z0-9])\s+([a-zA-Z0-9])', r'\1\2', text)
        return text
    
    def _normalize_url(self, text: str) -> str:
        """Normalize URLs."""
        # Remove spaces in URLs
        def fix_url(match):
            url = match.group(0)
            return url.replace(' ', '')
        
        return self.url_pattern.sub(fix_url, text)
    
    def extract_targets(self, text: str, verify_domains: bool = False) -> List[str]:
        """Extract targets (IPs, domains, URLs) from text.
        
        Args:
            text: Input text
            verify_domains: Whether to verify domains with web search
            
        Returns:
            List of extracted targets
        """
        targets = []
        
        # Extract IPs
        ip_matches = self.ip_pattern.findall(text)
        for match in ip_matches:
            ip = '.'.join(match)
            targets.append(ip)
        
        # Extract URLs
        url_matches = self.url_pattern.findall(text)
        targets.extend(url_matches)
        
        # Extract domains (but not if already in URL)
        domain_matches = self.domain_pattern.findall(text)
        potential_domains = self.potential_domain_pattern.findall(text)
        
        # Combine confirmed and potential domains
        all_domains = list(set(domain_matches + potential_domains))
        
        for domain in all_domains:
            # Check if domain is already part of a URL
            if not any(domain.lower() in url.lower() for url in url_matches):
                domain_lower = domain.lower()
                targets.append(domain_lower)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_targets = []
        for target in targets:
            normalized = self.normalize_target(target)
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_targets.append(normalized)
        
        return unique_targets
    
    def is_target_ambiguous(self, text: str, conversation_context: Optional[str] = None) -> Dict[str, Any]:
        """Check if target is ambiguous (lacks context like domain/IP).
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with:
            {
                "is_ambiguous": bool,
                "potential_targets": List[str],  # Company names, keywords
                "has_domain": bool,
                "has_ip": bool,
                "has_url": bool,
                "suggested_questions": List[str]  # Questions to ask user
            }
        """
        # Extract any clear targets first
        targets = self.extract_targets(text, verify_domains=False)
        has_domain = any(self._is_domain(t) for t in targets)
        has_ip = any(self._is_ip(t) for t in targets)
        has_url = any(self._is_url(t) for t in targets)
        
        # If we have clear targets, not ambiguous
        if has_domain or has_ip or has_url:
            return {
                "is_ambiguous": False,
                "potential_targets": targets,
                "has_domain": has_domain,
                "has_ip": has_ip,
                "has_url": has_url,
                "suggested_questions": []
            }
        
        potential_targets = self._extract_potential_targets_semantic(text)
        potential_targets = [
            t for t in potential_targets 
            if (len(t.split()) <= 3 and 
                len(t) < 50) 
        ]
        
        if not potential_targets and self.ai_model:
            # Ask AI if there's a target mentioned in the text
            ai_check = self._check_target_with_ai(text)
            if ai_check:
                potential_targets = ai_check.get("potential_targets", [])

        is_ambiguous = (
            (len(potential_targets) > 0 and not (has_domain or has_ip or has_url)) or
            (not (has_domain or has_ip or has_url) and self._looks_like_has_target(text))
        )
        
        # Generate suggested questions
        suggested_questions = []
        if is_ambiguous:
            main_target = potential_targets[0] if potential_targets else "target"
            suggested_questions = [
                f"What is the domain name or website URL for {main_target}?",
                f"What is the IP address of {main_target}?",
                f"Which country or region is {main_target} located in?",
                f"What industry or business does {main_target} operate in?",
                f"Can you provide the full company name or website for {main_target}?"
            ]
        
        # Check if we can extract search context
        search_context = {}
        can_search = False
        if is_ambiguous:
            search_context = self._extract_search_context(text, conversation_context)
            can_search = bool(search_context.get("company_name") or search_context.get("location"))
        
        return {
            "is_ambiguous": is_ambiguous,
            "potential_targets": potential_targets,
            "has_domain": has_domain,
            "has_ip": has_ip,
            "has_url": has_url,
            "suggested_questions": suggested_questions,
            "can_search": can_search,
            "search_context": search_context
        }
    
    def _extract_targets_with_ai(self, text: str, conversation_context: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Extract target information using AI model (semantic understanding, no hardcode).
        
        Args:
            text: Input text
            conversation_context: Previous conversation context
            
        Returns:
            Dictionary with target information or None if AI extraction fails
        """
        if not self.ai_model:
            return None
        
        try:
            # Build prompt for AI to understand target
            prompt = f"""Analyze this text and determine if it contains a clear target (domain, IP, URL) or if the target is ambiguous.

Text: {text}
"""
            if conversation_context:
                prompt += f"\nPrevious conversation context: {conversation_context}\n"
            
            prompt += """
Extract:
1. Clear targets (domains, IPs, URLs) - if any
2. Company/organization names - if mentioned
3. Location/country - if mentioned
4. Whether target is ambiguous (lacks domain/IP/URL)

Return JSON format:
{
  "has_clear_target": true/false,
  "clear_targets": ["domain.com", "192.168.1.1"],
  "company_name": "company name or null",
  "location": "location or null",
  "is_ambiguous": true/false,
  "potential_targets": ["potential names"]
}"""
            
            # Use AI model to analyze
            result = self.ai_model.analyze_and_breakdown(
                user_prompt=prompt,
                conversation_history=None,
                stream_callback=None
            )
            
            if result.get("success"):
                analysis = result.get("analysis", {})
                raw_response = result.get("raw_response", "")
                
                # Try to parse JSON from response
                try:
                    if isinstance(analysis, dict) and "has_clear_target" in analysis:
                        extracted = analysis
                    else:
                        # Try to extract JSON from raw response
                        json_match = re.search(r'\{[^}]+\}', raw_response, re.DOTALL)
                        if json_match:
                            extracted = json.loads(json_match.group())
                        else:
                            return None
                    
                    # Build result
                    has_clear = extracted.get("has_clear_target", False)
                    clear_targets = extracted.get("clear_targets", [])
                    
                    return {
                        "is_ambiguous": not has_clear and extracted.get("is_ambiguous", False),
                        "potential_targets": extracted.get("potential_targets", []),
                        "has_domain": any(self._is_domain(t) for t in clear_targets),
                        "has_ip": any(self._is_ip(t) for t in clear_targets),
                        "has_url": any(self._is_url(t) for t in clear_targets),
                        "suggested_questions": [],
                        "can_search": bool(extracted.get("company_name") or extracted.get("location")),
                        "search_context": {
                            "company_name": extracted.get("company_name"),
                            "location": extracted.get("location"),
                            "industry": None
                        }
                    }
                except (json.JSONDecodeError, KeyError):
                    return None
        except Exception:
            # AI extraction failed, return None to use fallback
            return None
        
        return None
    
    def _extract_search_context_with_ai(self, text: str, conversation_context: Optional[str] = None) -> Dict[str, Any]:
        """Extract search context using AI model (semantic, no hardcode).
        
        Args:
            text: Current text
            conversation_context: Previous conversation
            
        Returns:
            Dictionary with company_name, location, industry
        """
        if not self.ai_model:
            return {}
        
        try:
            prompt = f"""Extract company name and location from this conversation.

Current message: {text}
"""
            if conversation_context:
                prompt += f"Previous context: {conversation_context}\n"
            
            prompt += """
Extract:
1. Company/organization name (if mentioned)
2. Location/country (if mentioned)
3. Industry (if mentioned)

Return JSON:
{"company_name": "...", "location": "...", "industry": "..."}
Use null if not found."""
            
            result = self.ai_model.analyze_and_breakdown(
                user_prompt=prompt,
                conversation_history=None,
                stream_callback=None
            )
            
            if result.get("success"):
                analysis = result.get("analysis", {})
                raw_response = result.get("raw_response", "")
                
                try:
                    if isinstance(analysis, dict) and "company_name" in analysis:
                        return analysis
                    else:
                        json_match = re.search(r'\{[^}]+\}', raw_response, re.DOTALL)
                        if json_match:
                            return json.loads(json_match.group())
                except (json.JSONDecodeError, KeyError):
                    pass
        except Exception:
            pass
        
        return {}
    
    def _is_additional_context(self, text: str, conversation_context: Optional[str] = None) -> bool:
        """Check if text provides additional context about a previous target.
        
        Uses AI model if available, otherwise uses semantic patterns (not hardcoded keywords).
        
        Args:
            text: Current text
            conversation_context: Previous conversation
            
        Returns:
            True if this looks like additional context
        """
        if not conversation_context:
            return False
        
        # Use AI model if available
        if self.ai_model:
            try:
                prompt = f"""Does this message provide additional context about a target mentioned in previous conversation?

Previous: {conversation_context}
Current: {text}

Answer: true or false"""
                
                result = self.ai_model.analyze_and_breakdown(
                    user_prompt=prompt,
                    conversation_history=None,
                    stream_callback=None
                )
                
                if result.get("success"):
                    analysis = result.get("analysis", {})
                    raw_response = result.get("raw_response", "").lower()
                    # Check if response indicates additional context
                    if "true" in raw_response or "yes" in raw_response:
                        return True
            except Exception:
                pass
        
        # Fallback: Semantic pattern (not keyword-based)
        # Look for semantic indicators of additional information
        text_lower = text.lower()
        # Check for phrases that suggest uncertainty or additional info
        uncertainty_patterns = [
            r'\b(?:not|don\'?t|doesn\'?t)\s+(?:sure|know|certain)',
            r'\b(?:from|located|based)\s+[A-Z]',
            r'\b(?:company|corporation|business)\s+',
        ]
        
        has_uncertainty = any(re.search(pattern, text_lower) for pattern in uncertainty_patterns)
        has_location = bool(re.search(r'\b(?:from|located|based)\s+[A-Z][a-z]+', text))
        has_previous_target = bool(re.search(r'\b[A-Z][a-z]{3,}\b', conversation_context))
        
        return (has_uncertainty or has_location) and has_previous_target
    
    def _extract_search_context(self, text: str, conversation_context: Optional[str] = None) -> Dict[str, Any]:
        """Extract company name and location from text for web search.
        
        Uses AI model if available, otherwise uses flexible patterns (no hardcoded keywords).
        
        Args:
            text: Current text
            conversation_context: Previous conversation
            
        Returns:
            Dictionary with company_name, location, industry, etc.
        """
        # Use AI model if available (preferred method - no hardcode)
        if self.ai_model:
            return self._extract_search_context_with_ai(text, conversation_context)
        
        # Fallback: Pattern-based extraction (flexible patterns, no hardcoded keywords)
        context = {
            "company_name": None,
            "location": None,
            "industry": None
        }
        
        # Extract company name from conversation context using semantic patterns
        if conversation_context:
            # Look for capitalized words after action verbs (semantic pattern)
            words = conversation_context.split()
            for i, word in enumerate(words):
                # Semantic check: capitalized word that looks like a proper noun
                if (word[0].isupper() and len(word) > 3 and 
                    word.replace('-', '').isalnum()):
                    # Check semantic context - is it after a verb-like word?
                    if i > 0:
                        prev_word = words[i-1].lower()
                        # Check if previous word looks like a verb (semantic, not keyword list)
                        verb_like = len(prev_word) > 2 and not prev_word[0].isupper()
                        if verb_like:
                            context["company_name"] = word
                            break
        
        # Extract location using flexible regex patterns (not hardcoded country names)
        # Pattern: "from [Location]" or "located in [Location]"
        location_patterns = [
            r'(?:from|located\s+in|based\s+in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b',  # Multi-word capitalized phrases (like "South Africa")
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Semantic filter: exclude very short or common words
                if len(location) > 3 and len(location.split()) <= 3:
                    context["location"] = location
                    break
        
        return context
    
    def _extract_potential_targets_semantic(self, text: str) -> List[str]:
        """Extract potential targets using semantic patterns (not keyword detection).
        
        Uses context-aware extraction instead of hardcoded keywords.
        
        Args:
            text: Input text
            
        Returns:
            List of potential target names
        """
        potential_targets = []
        
        # Pattern 1: Compound capitalized phrases (semantic pattern, not keyword-based)
        # Match multi-word capitalized phrases (potential company names)
        compound_pattern = re.compile(
            r'\b([A-Z][a-z]+(?:[- ][A-Z]?[a-z]+)+)\b'
        )
        matches = compound_pattern.findall(text)
        for match in matches:
            cleaned = match.strip()
            # Semantic constraints: reasonable length, max 3 words
            if (len(cleaned) > 3 and 
                len(cleaned.split()) <= 3):
                potential_targets.append(cleaned)
        
        # Pattern 2: Standalone capitalized words (potential company names)
        # Use semantic context, not hardcoded keyword lists
        words = text.split()
        for i, word in enumerate(words):
            # Skip very short words (semantic constraint, not keyword list)
            if len(word) <= 2:
                continue
            
            # Check if word is capitalized (potential proper noun)
            if (word[0].isupper() and len(word) > 3 and 
                word.replace('-', '').isalnum()):
                # Check semantic context - is it after a verb-like word?
                # This is semantic pattern matching, not keyword detection
                if i > 0:
                    prev_word = words[i-1].lower()
                    # Check if previous word looks like a verb (semantic pattern)
                    # Verbs typically: 3+ chars, lowercase, not capitalized, alphabetic
                    verb_like = (len(prev_word) > 2 and 
                                not prev_word[0].isupper() and
                                prev_word.isalpha())
                    if verb_like:
                        potential_targets.append(word)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_targets = []
        for target in potential_targets:
            target_lower = target.lower()
            if target_lower not in seen:
                seen.add(target_lower)
                unique_targets.append(target)
        
        return unique_targets
    
    def _check_target_with_ai(self, text: str) -> Optional[Dict[str, Any]]:
        """Use AI model to check if text contains a target mention.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with potential_targets or None
        """
        if not self.ai_model:
            return None
        
        try:
            prompt = f"""Does this text mention a target (company name, domain, IP, URL)?

Text: {text}

If yes, extract the target name(s). Return JSON:
{{"has_target": true/false, "potential_targets": ["target1", "target2"]}}
If no target found, return: {{"has_target": false, "potential_targets": []}}"""
            
            result = self.ai_model.analyze_and_breakdown(
                user_prompt=prompt,
                conversation_history=None,
                stream_callback=None
            )
            
            if result.get("success"):
                analysis = result.get("analysis", {})
                raw_response = result.get("raw_response", "")
                
                try:
                    if isinstance(analysis, dict) and "has_target" in analysis:
                        if analysis.get("has_target"):
                            return {"potential_targets": analysis.get("potential_targets", [])}
                    else:
                        # Try to extract JSON from raw response
                        json_match = re.search(r'\{[^}]+\}', raw_response, re.DOTALL)
                        if json_match:
                            extracted = json.loads(json_match.group())
                            if extracted.get("has_target"):
                                return {"potential_targets": extracted.get("potential_targets", [])}
                except (json.JSONDecodeError, KeyError):
                    pass
        except Exception:
            pass
        
        return None
    
    def _looks_like_has_target(self, text: str) -> bool:
        """Check if text looks like it mentions a target (semantic pattern, not keyword).
        
        Args:
            text: Input text
            
        Returns:
            True if text looks like it has a target mention
        """
        # Pattern: action verb followed by a word (potential target)
        # This is semantic pattern matching, not keyword detection
        words = text.split()
        if len(words) < 2:
            return False
        
        # Check if there's a verb-like word followed by another word
        for i in range(len(words) - 1):
            word1 = words[i].lower()
            word2 = words[i + 1]
            
            # Check if word1 looks like a verb (semantic pattern)
            verb_like = (len(word1) > 2 and 
                        word1.isalpha() and
                        not word1[0].isupper())
            
            # Check if word2 looks like a target (proper noun or significant word)
            target_like = (len(word2) > 3 and 
                          word2.replace('-', '').isalnum())
            
            if verb_like and target_like:
                return True
        
        return False
    
    def _is_ip(self, text: str) -> bool:
        """Check if text is an IP address."""
        return bool(self.ip_pattern.match(text))
    
    def _is_url(self, text: str) -> bool:
        """Check if text is a URL."""
        return bool(self.url_pattern.match(text))
    
    def verify_and_correct_dns(self, domain: str) -> Optional[str]:
        """Verify and correct DNS name using web search.
        
        Args:
            domain: Domain name to verify
            
        Returns:
            Corrected domain name or None if not found
        """
        if not self.search_aggregator:
            return domain
        
        # Check if domain looks suspicious (has unusual characters or patterns)
        if not self._looks_like_valid_domain(domain):
            return self._search_and_correct_domain(domain)
        
        # Try to verify domain exists
        search_query = f'"{domain}" website official'
        search_result = self.search_aggregator.search(
            query=search_query,
            num_results=5,
            fetch_content=False,
            rank_results=True,
            verify_results=False
        )
        
        if search_result.get("success"):
            results = search_result.get("results", [])
            # Look for the domain in search results
            for result in results:
                link = result.get("link", "")
                title = result.get("title", "").lower()
                snippet = result.get("snippet", "").lower()
                
                # Extract domain from URL
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(link)
                    result_domain = parsed.netloc.lower()
                    
                    # Remove www. prefix
                    if result_domain.startswith("www."):
                        result_domain = result_domain[4:]
                    
                    # Check if exact match
                    if result_domain == domain.lower():
                        return domain  # Return original to avoid any modification
                    
                    # Check if result domain is similar to input domain
                    if self._domains_similar(domain, result_domain):
                        # Prevent duplication: check if result ends with original domain
                        domain_lower = domain.lower()
                        if result_domain.endswith('.' + domain_lower) or result_domain == domain_lower + '.za':
                            # Likely duplicate, return original
                            return domain
                        # Check if result has more parts but same base
                        domain_parts = domain_lower.split('.')
                        result_parts = result_domain.split('.')
                        if len(result_parts) > len(domain_parts):
                            # Check if it's just adding the same TLD
                            if result_domain.endswith('.' + '.'.join(domain_parts[-2:])):
                                return domain  # Return original to avoid duplication
                        return result_domain
                    
                    # Check if domain appears in title or snippet
                    if domain in title or domain in snippet:
                        # Try to extract correct domain from context
                        corrected = self._extract_domain_from_text(title + " " + snippet, domain)
                        if corrected and corrected != domain:
                            # Make sure corrected doesn't duplicate
                            if not corrected.endswith('.' + domain.lower()):
                                return corrected
                except:
                    pass
        
        return domain
    
    def _looks_like_valid_domain(self, domain: str) -> bool:
        """Check if domain looks valid (not obviously misspelled).
        
        Args:
            domain: Domain to check
            
        Returns:
            True if looks valid
        """
        # Basic validation
        if not domain or len(domain) < 4:
            return False
        
        # Check for common TLD
        has_tld = any(domain.endswith(f".{tld}") for tld in self.COMMON_TLDS)
        if not has_tld:
            return False
        
        # Check for suspicious patterns (too many consecutive consonants, etc.)
        parts = domain.split(".")
        if len(parts) < 2:
            return False
        
        main_part = parts[0]
        # Check for unusual character patterns
        if re.search(r'[^a-z0-9-]', main_part, re.IGNORECASE):
            return False
        
        return True
    
    def _domains_similar(self, domain1: str, domain2: str) -> bool:
        """Check if two domains are similar (fuzzy match).
        
        Args:
            domain1: First domain
            domain2: Second domain
            
        Returns:
            True if similar
        """
        try:
            from rapidfuzz import fuzz
        except ImportError:
            # Fallback to simple string comparison if rapidfuzz not available
            return domain1.lower() == domain2.lower()
        
        # Extract main parts (without TLD)
        parts1 = domain1.split(".")
        parts2 = domain2.split(".")
        
        if len(parts1) < 2 or len(parts2) < 2:
            return False
        
        main1 = parts1[0].lower()
        main2 = parts2[0].lower()
        
        # Check similarity
        similarity = fuzz.ratio(main1, main2)
        return similarity >= 70
    
    def _extract_domain_from_text(self, text: str, original_domain: str) -> Optional[str]:
        """Extract correct domain from text.
        
        Args:
            text: Text to search
            original_domain: Original domain to match against
            
        Returns:
            Extracted domain or None
        """
        # Look for domain patterns in text
        domain_matches = self.domain_pattern.findall(text)
        for match in domain_matches:
            if self._domains_similar(original_domain, match.lower()):
                return match.lower()
        
        return None
    
    def _search_and_correct_domain(self, domain: str) -> Optional[str]:
        """Search for domain with additional context from user.
        
        Args:
            domain: Domain to search for
            
        Returns:
            Corrected domain or original if not found
        """
        # Ask user for additional information if callback available
        company_info = None
        if self.interactive_callback:
            # Ask for company information
            question = (
                f"I found a potential domain name '{domain}' that might have a typo. "
                f"To help me find the correct domain, could you provide:\n"
                f"1. Company name or industry?\n"
                f"2. Location (city/country)?\n"
                f"3. Any other identifying information?\n"
                f"(Press Enter to skip and use original domain)"
            )
            
            company_info = self.interactive_callback(question)
        
        # Build search query
        if company_info and company_info.strip():
            search_query = f'"{domain}" {company_info} official website'
        else:
            search_query = f'"{domain}" official website company'
        
        if not self.search_aggregator:
            return domain
        
        search_result = self.search_aggregator.search(
            query=search_query,
            num_results=10,
            fetch_content=False,
            rank_results=True,
            verify_results=False
        )
        
        if search_result.get("success"):
            results = search_result.get("results", [])
            
            # Extract domains from results
            found_domains = []
            for result in results:
                link = result.get("link", "")
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(link)
                    result_domain = parsed.netloc.lower()
                    
                    # Remove www. prefix
                    if result_domain.startswith("www."):
                        result_domain = result_domain[4:]
                    
                    # Check if similar to original
                    if self._domains_similar(domain, result_domain):
                        found_domains.append((result_domain, result.get("title", "")))
                except:
                    pass
            
            # Return most common or first result
            if found_domains:
                # Count occurrences
                domain_counts = {}
                for d, _ in found_domains:
                    domain_counts[d] = domain_counts.get(d, 0) + 1
                
                # Get most common
                most_common = max(domain_counts.items(), key=lambda x: x[1])
                return most_common[0]
        
        return domain
    
    def fuzzy_match_tool(self, tool_name: str, threshold: int = 70) -> Optional[str]:
        """Fuzzy match tool name.
        
        Args:
            tool_name: Input tool name (may have typos)
            threshold: Minimum similarity score (0-100)
            
        Returns:
            Matched tool name or None
        """
        return self.fuzzy_matcher.fuzzy_match_tool(tool_name, threshold=threshold)
    
    def normalize_input(self, user_input: str, verify_domains: bool = True) -> Dict[str, Any]:
        """Normalize user input and extract information.
        
        Args:
            user_input: Raw user input
            verify_domains: Whether to verify DNS names with web search
            
        Returns:
            Dictionary with normalized input and extracted information:
            {
                "normalized_text": str,
                "targets": List[str],
                "normalized_targets": List[str],
                "corrected_targets": Dict[str, str],
                "tools_mentioned": List[str],
                "corrected_tools": Dict[str, str]
            }
        """
        normalized_text = user_input
        targets = self.extract_targets(user_input, verify_domains=verify_domains)
        tools_mentioned = []
        corrected_tools = {}
        corrected_targets = {}
        
        # NOTE: We do NOT do keyword-based tool matching here.
        # Models (especially FunctionGemma) use semantic understanding to select tools.
        # This normalizer only handles:
        # 1. Target extraction and normalization (IPs, domains, URLs)
        # 2. Typo correction for explicitly mentioned tool names (if user types "nmap" wrong)
        # 3. DNS verification via web search
        
        # Only correct tool names if user explicitly mentions them with obvious typos
        # This is a safety net, not the primary method
        # We look for patterns like "use nmap", "run whois", "execute dig" etc.
        # IMPORTANT: We do NOT match action verbs like "scan", "test", "assess" - models understand these semantically
        
        explicit_tool_patterns = [
            r'\b(use|run|execute|call|invoke|with)\s+([a-z0-9_-]+)',
            r'\b([a-z0-9_-]+)\s+(tool|command)',
        ]
        
        # Get actual tool names for validation
        actual_tool_names = set(self.fuzzy_matcher._get_tool_names())
        
        for pattern in explicit_tool_patterns:
            matches = re.finditer(pattern, user_input, re.IGNORECASE)
            for match in matches:
                # Extract potential tool name (second group or first group depending on pattern)
                potential_tool = match.group(2) if match.lastindex >= 2 else match.group(1)
                if potential_tool:
                    clean_tool = re.sub(r'[^\w-]', '', potential_tool.lower())
                    # Only match if it's a reasonable length and looks like a tool name
                    if len(clean_tool) >= 3:
                        # First check if it's already a valid tool name (exact match)
                        if clean_tool in actual_tool_names:
                            tools_mentioned.append(clean_tool)
                            continue
                        
                        # Only try fuzzy match if it's likely a tool name (not an action verb)
                        # Action verbs are typically short and common - tool names are more specific
                        matched = self.fuzzy_match_tool(clean_tool, threshold=85)  # Very high threshold
                        if matched and matched != clean_tool:
                            # Only correct if there's a clear typo match AND it's not an action verb
                            # Double-check: if matched tool name contains the original word, it's likely correct
                            if clean_tool in matched or matched in actual_tool_names:
                                corrected_tools[clean_tool] = matched
                                tools_mentioned.append(clean_tool)
        
        # Normalize and verify targets
        normalized_targets = []
        original_targets = self.extract_targets(user_input, verify_domains=False)
        
        for target in original_targets:
            normalized_target = self.normalize_target(target)
            
            # Verify DNS if enabled and target looks like a domain
            if verify_domains and self._is_domain(target):
                verified_domain = self.verify_and_correct_dns(normalized_target)
                if verified_domain and verified_domain != normalized_target:
                    corrected_targets[normalized_target] = verified_domain
                    normalized_target = verified_domain
            
            normalized_targets.append(normalized_target)
            
            # Replace in normalized text
            if normalized_target != target:
                # Replace all occurrences
                normalized_text = normalized_text.replace(target, normalized_target)
        
        return {
            "normalized_text": normalized_text,
            "original_text": user_input,
            "targets": original_targets,
            "normalized_targets": normalized_targets,
            "corrected_targets": corrected_targets,
            "tools_mentioned": tools_mentioned,
            "corrected_tools": corrected_tools
        }
    
    def _is_domain(self, text: str) -> bool:
        """Check if text looks like a domain name.
        
        Args:
            text: Text to check
            
        Returns:
            True if looks like domain
        """
        # Check if it matches domain pattern
        if self.domain_pattern.match(text) or self.potential_domain_pattern.match(text):
            return True
        
        # Check if it has a TLD
        parts = text.split(".")
        if len(parts) >= 2:
            tld = parts[-1].lower()
            if tld in self.COMMON_TLDS:
                return True
        
        return False
