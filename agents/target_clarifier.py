"""Target clarifier for handling ambiguous targets.

Pipeline: Lexical Normalize → Entity Candidates → Ambiguity Scoring → 
          Web Search → Extract → Cross-check → Ask User
"""

import logging
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

from utils.input_normalizer import InputNormalizer
from utils.llm_response_parser import parse_llm_json_response, parse_to_dataclass
from models.generic_ollama_agent import GenericOllamaAgent
from models.entity_info import (
    EntityCandidate, EntityInfo, ValidationResult, 
    ExtractedQuery, ClarificationResult
)
from memory.manager import MemoryManager
# from agents.context_manager import ContextManager # Removed as requested
from agents.messages import ClarificationMessages
from rag.retriever import ConversationRetriever

logger = logging.getLogger(__name__)


class TargetClarifier:
    """Handles target clarification using tool calling and web search.
    
    Implements a clean pipeline:
    1. Lexical Normalize - Normalize user input
    2. Entity Candidates - Lookup from DB/Vector DB
    3. Ambiguity Scoring - Calculate ambiguity score
    4. Web Search - Search for entity if ambiguous
    5. Extract - Extract structured info from results
    6. Cross-check - Validate extracted info
    7. Ask User - Confirm with user if needed
    """
    
    def __init__(
        self,
        analysis_agent: GenericOllamaAgent,
        memory_manager: MemoryManager,
        stream_callback: Optional[Callable[[str, str, Any], None]] = None
    ):
        """Initialize target clarifier.
        
        Args:
            analysis_agent: Generic Ollama agent for AI understanding
            memory_manager: Memory manager for session state
            stream_callback: Optional callback for streaming events
        """
        self.analysis_agent = analysis_agent
        self.memory_manager = memory_manager
        self.stream_callback = stream_callback
        self.conversation_retriever = ConversationRetriever()
        
        # Initialize tool calling registry
        from models.tool_calling_registry import get_tool_calling_registry
        self.tool_calling_registry = get_tool_calling_registry()
        
        # Initialize InputNormalizer for lexical normalization
        self.input_normalizer = InputNormalizer(ai_model=analysis_agent)
        
        # Load prompt templates
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load Jinja2 prompt templates."""
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        
        try:
            self.extraction_template = self.env.get_template("target_extraction.jinja2")
        except Exception as e:
            logger.warning(f"Failed to load extraction template: {e}")
            self.extraction_template = None
            
        try:
            self.validation_template = self.env.get_template("target_validation.jinja2")
        except Exception as e:
            logger.warning(f"Failed to load validation template: {e}")
            self.validation_template = None
    
    def _stream(self, event_type: str, source: str, data: Any) -> None:
        """Send streaming event if callback is configured."""
        if self.stream_callback:
            self.stream_callback(event_type, source, data)
    
    # =========================================================================
    # STEP 1: Lexical Normalize
    # =========================================================================
    
    def _step_normalize(self, user_prompt: str) -> str:
        """Normalize user input using RapidFuzz.
        
        Args:
            user_prompt: Raw user input
            
        Returns:
            Normalized prompt
        """
        try:
            normalized = self.input_normalizer.normalize_target(user_prompt)
            if normalized != user_prompt:
                logger.debug(f"Normalized prompt: '{user_prompt}' -> '{normalized}'")
            return normalized
        except Exception as e:
            logger.warning(f"Normalization failed: {e}")
            return user_prompt
    
    # =========================================================================
    # STEP 2: Entity Candidates (DB/Vector DB Lookup)
    # =========================================================================
    
    def _step_lookup_candidates(
        self, 
        query: str, 
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> List[EntityCandidate]:
        """Lookup entity candidates from DB/Vector DB.
        
        Args:
            query: Search query (company name, domain, etc.)
            conversation_id: Conversation ID for namespace isolation
            session_id: Legacy session ID
            
        Returns:
            List of EntityCandidate objects sorted by confidence
        """
        candidates: List[EntityCandidate] = []
        
        # Search conversation history in Vector DB
        candidates.extend(
            self._search_conversation_history(query, conversation_id, session_id)
        )
        
        # Search verified targets from database
        candidates.extend(
            self._search_verified_targets(query, conversation_id)
        )
        
        # Deduplicate and sort by confidence
        return self._deduplicate_candidates(candidates)
    
    def _search_conversation_history(
        self,
        query: str,
        conversation_id: Optional[str],
        session_id: Optional[str]
    ) -> List[EntityCandidate]:
        """Search conversation history for entity candidates."""
        candidates = []
        conv_id = conversation_id or session_id
        
        if not conv_id:
            return candidates
        
        try:
            context_results = self.conversation_retriever.retrieve_context(
                query=query,
                k=5,
                conversation_id=conversation_id,
                session_id=session_id
            )
            
            import re
            domain_pattern = re.compile(
                r'\b([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
                r'\.(?:[a-zA-Z]{2,}))\b'
            )
            
            for result in context_results:
                content = result.get("content", "") or result.get("text", "")
                if not content:
                    continue
                    
                domains = domain_pattern.findall(content)
                for domain in domains[:3]:
                    candidates.append(EntityCandidate(
                        domain=domain.lower(),
                        source="conversation_history",
                        confidence=0.6,
                        context=content[:200]
                    ))
                    
        except Exception as e:
            logger.debug(f"Conversation history search failed: {e}")
        
        return candidates
    
    def _search_verified_targets(
        self,
        query: str,
        conversation_id: Optional[str]
    ) -> List[EntityCandidate]:
        """Search verified targets from database."""
        candidates = []
        
        try:
            from rapidfuzz import fuzz
            
            conversations = self.memory_manager.conversation_store.list_conversations(
                limit=100
            )
            
            query_lower = query.lower()
            
            for conv in conversations:
                verified_target = conv.get('verified_target')
                if not verified_target:
                    continue
                    
                target_lower = verified_target.lower()
                
                if query_lower in target_lower or target_lower in query_lower:
                    similarity = fuzz.ratio(query_lower, target_lower) / 100.0
                    
                    if similarity > 0.5:
                        candidates.append(EntityCandidate(
                            domain=verified_target,
                            source="verified_targets_db",
                            confidence=similarity * 0.8,
                            conversation_id=conv.get('id')
                        ))
                        
        except Exception as e:
            logger.debug(f"Verified targets search failed: {e}")
        
        return candidates
    
    def _deduplicate_candidates(
        self, 
        candidates: List[EntityCandidate]
    ) -> List[EntityCandidate]:
        """Remove duplicate candidates and sort by confidence."""
        seen_domains = set()
        unique = []
        
        for candidate in candidates:
            if candidate.domain and candidate.domain not in seen_domains:
                seen_domains.add(candidate.domain)
                unique.append(candidate)
        
        unique.sort(key=lambda x: x.confidence, reverse=True)
        return unique[:5]
    
    # =========================================================================
    # STEP 3: Ambiguity Scoring
    # =========================================================================
    
    def _step_calculate_ambiguity(
        self, 
        candidates: List[EntityCandidate], 
        company_name: Optional[str] = None,
        location: Optional[str] = None
    ) -> float:
        """Calculate ambiguity score (0-1).
        
        Args:
            candidates: List of entity candidates
            company_name: Optional company name
            location: Optional location
            
        Returns:
            Ambiguity score (0 = clear, 1 = highly ambiguous)
        """
        if not candidates:
            return 1.0
        
        if len(candidates) == 1:
            return 1.0 - candidates[0].confidence
        
        # Multiple candidates - calculate based on spread
        confidences = [c.confidence for c in candidates]
        max_conf = max(confidences)
        min_conf = min(confidences)
        conf_spread = max_conf - min_conf
        
        base_ambiguity = min(0.8, 0.3 + (len(candidates) - 1) * 0.15)
        
        # Large confidence spread reduces ambiguity
        if conf_spread > 0.3:
            base_ambiguity *= 0.6
        
        # Having both name and location reduces ambiguity
        if company_name and location:
            base_ambiguity *= 0.7
        
        return min(1.0, base_ambiguity)
    
    # =========================================================================
    # STEP 4: Web Search
    # =========================================================================
    
    def _step_web_search(
        self,
        company_name: Optional[str],
        location: Optional[str],
        user_prompt: str,
        context: str,
        conversation_id: Optional[str],
        conversation_history: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute web search for entity.
        
        Args:
            company_name: Company name to search
            location: Location/country
            user_prompt: Original user prompt
            context: Conversation context
            conversation_id: Current conversation ID
            conversation_history: Conversation history
            
        Returns:
            List of search results or None if search failed
        """
        # Generate search queries
        search_queries = self._generate_search_queries(
            company_name, location, user_prompt, context
        )
        
        # Build prompt for tool calling
        target_verification_prompt = self._build_search_prompt(
            company_name, location, context, user_prompt, search_queries
        )
        
        try:
            # Create streaming callbacks
            model_callback = None
            tool_stream_callback = None
            
            if self.stream_callback:
                def callback(chunk: str):
                    self._stream("model_response", "tool_calling_verify", chunk)
                model_callback = callback
                
                def tool_callback(tool_name: str, command: str, line: str):
                    self._stream("tool_execution", tool_name, line)
                tool_stream_callback = tool_callback
            
            # Execute tool calling
            tool_calling_agent = self.tool_calling_registry.get_model()
            result = tool_calling_agent.call_with_tools(
                user_prompt=target_verification_prompt,
                tools=["web_search"],
                session_id=conversation_id,
                conversation_history=conversation_history,
                stream_callback=model_callback,
                tool_stream_callback=tool_stream_callback
            )
            
            return self._extract_search_results(result)
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            self._stream(
                "model_response", "system",
                ClarificationMessages.AUTO_SEARCH_FAILED.format(error=str(e))
            )
            return None
    
    def _generate_search_queries(
        self,
        company_name: Optional[str],
        location: Optional[str],
        user_prompt: str,
        context: str
    ) -> List[str]:
        """Generate intelligent search queries using LLM."""
        query_prompt = f"""Generate 3-5 intelligent web search queries to find the official website domain for a company/organization.

Company name: {company_name or 'unknown'}
Location: {location or 'unknown'}
User message: {user_prompt}
Context: {context}

Generate queries that:
1. Combine company name and location intelligently
2. Include terms like "official website", "domain", "company website"
3. Use variations like "(Pty) Ltd", "Corp", "Inc" for company names
4. Include country-specific terms if location is provided

Return a JSON array of query strings:
{{"queries": ["query1", "query2", "query3"]}}"""
        
        try:
            result = self.analysis_agent.analyze_and_breakdown(
                user_prompt=query_prompt,
                conversation_history=None
            )
            
            if result.get("success"):
                parsed = parse_llm_json_response(result.get("raw_response", ""))
                if parsed and "queries" in parsed:
                    return parsed["queries"]
                    
        except Exception as e:
            logger.debug(f"Query generation failed: {e}")
        
        # Fallback queries
        queries = []
        if company_name and location:
            queries.append(f"{company_name} {location} official website domain")
            queries.append(f"{company_name} {location} company website")
            queries.append(f"{company_name} (Pty) Ltd {location}")
        elif company_name:
            queries.append(f"{company_name} official website domain")
            queries.append(f"{company_name} company website")
        else:
            queries.append(f"{user_prompt} official website")
        
        return queries[:5]
    
    def _build_search_prompt(
        self,
        company_name: Optional[str],
        location: Optional[str],
        context: str,
        user_prompt: str,
        search_queries: List[str]
    ) -> str:
        """Build prompt for tool calling with search queries."""
        queries_text = "\n".join(f"- {q}" for q in search_queries[:3])
        
        return f"""You need to find the official website domain for a company/organization.

Company name: {company_name or 'unknown'}
Location: {location or 'unknown'}
Previous conversation context: {context}
Current user message: {user_prompt}

Suggested search queries (use one of these or create similar):
{queries_text}

Your task:
1. Call the web_search tool with an appropriate query to find the official website domain
2. The query should combine company name and location intelligently
3. Use num_results=5 to get multiple search results
4. The goal is to find the most relevant domain that matches the company name and location

Target: Find the official website domain for this company/organization."""
    
    def _extract_search_results(
        self, 
        tool_result: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Extract search results from tool calling result."""
        if not tool_result.get("success"):
            error = tool_result.get("error", "Unknown error")
            self._stream(
                "model_response", "system",
                ClarificationMessages.AUTO_SEARCH_FAILED.format(error=error)
            )
            return None
        
        tool_results = tool_result.get("tool_results", [])
        
        if not tool_results:
            self._stream(
                "model_response", "system",
                ClarificationMessages.NO_TOOL_CALL
            )
            return None
        
        for tr in tool_results:
            if tr.get("tool_name") == "web_search":
                result = tr.get("result", {})
                if result.get("success"):
                    return result.get("results", [])
                else:
                    error = result.get("error", "Unknown error")
                    self._stream(
                        "model_response", "system",
                        ClarificationMessages.SEARCH_FAILED.format(error=error)
                    )
        
        return None
    
    # =========================================================================
    # STEP 5: Extract Structured Info
    # =========================================================================
    
    def _step_extract_info(
        self, 
        search_results: List[Dict[str, Any]], 
        company_name: Optional[str] = None,
        location: Optional[str] = None
    ) -> EntityInfo:
        """Extract structured information from web search results.
        
        Args:
            search_results: List of web search result dicts
            company_name: Optional company name for context
            location: Optional location for context
            
        Returns:
            EntityInfo with extracted data
        """
        formatted_results = [
            {
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "link": r.get("link", "")
            }
            for r in search_results[:10]
        ]
        
        # Build extraction prompt
        if self.extraction_template:
            extraction_prompt = self.extraction_template.render(
                search_results=formatted_results,
                company_name=company_name or "unknown",
                location=location or "unknown"
            )
        else:
            extraction_prompt = self._build_extraction_prompt(
                formatted_results, company_name, location
            )
        
        try:
            result = self.analysis_agent.analyze_and_breakdown(
                user_prompt=extraction_prompt,
                conversation_history=None
            )
            
            if result.get("success"):
                parsed = parse_llm_json_response(result.get("raw_response", ""))
                if parsed:
                    return EntityInfo.from_dict(parsed)
            
            # Fallback: extract domain from search results heuristically
            return self._extract_domain_fallback(
                search_results, company_name, location
            )
            
        except Exception as e:
            logger.error(f"Info extraction failed: {e}")
            return EntityInfo.empty()
    
    def _build_extraction_prompt(
        self,
        formatted_results: List[Dict[str, str]],
        company_name: Optional[str],
        location: Optional[str]
    ) -> str:
        """Build inline extraction prompt when template not available."""
        results_text = "\n\n".join([
            f"Result {i}:\nTitle: {r['title']}\nSnippet: {r['snippet']}\nLink: {r['link']}"
            for i, r in enumerate(formatted_results, 1)
        ])
        
        return f"""Extract structured information about a company/organization from web search results.

Company name (if known): {company_name or 'unknown'}
Location (if known): {location or 'unknown'}

Search Results:
{results_text}

Extract the following information in JSON format:
{{
    "legal_name": "Official legal company name",
    "country": "Country/region",
    "domain": "Primary domain name",
    "asn": "ASN number if found, or null",
    "ip_ranges": ["IP range or CIDR if found, or empty array"],
    "confidence": 0.0-1.0
}}

Only extract information that is clearly stated in the search results."""
    
    def _extract_domain_fallback(
        self,
        search_results: List[Dict[str, Any]],
        company_name: Optional[str],
        location: Optional[str]
    ) -> EntityInfo:
        """Fallback domain extraction using heuristics."""
        domain = None
        
        for result in search_results:
            link = result.get("link", "")
            if link:
                try:
                    parsed = urlparse(link)
                    extracted = parsed.netloc.replace("www.", "").lower()
                    if extracted and len(extracted) > 3:
                        domain = extracted
                        break
                except Exception:
                    continue
        
        return EntityInfo(
            legal_name=company_name or "",
            country=location or "",
            domain=domain or "",
            confidence=0.3  # Low confidence for fallback
        )
    
    # =========================================================================
    # STEP 6: Cross-check Entity
    # =========================================================================
    
    def _step_cross_check(
        self, 
        extracted_infos: List[EntityInfo]
    ) -> ValidationResult:
        """Cross-check extracted entity information for consistency.
        
        Args:
            extracted_infos: List of extracted EntityInfo from multiple sources
            
        Returns:
            ValidationResult with confidence and conflicts
        """
        if not extracted_infos:
            return ValidationResult.failed("No extracted information")
        
        # Convert to dicts for template
        infos_dicts = [info.to_dict() for info in extracted_infos]
        
        # Build validation prompt
        if self.validation_template:
            validation_prompt = self.validation_template.render(
                extracted_infos=infos_dicts
            )
        else:
            validation_prompt = self._build_validation_prompt(infos_dicts)
        
        try:
            result = self.analysis_agent.analyze_and_breakdown(
                user_prompt=validation_prompt,
                conversation_history=None
            )
            
            if result.get("success"):
                parsed = parse_llm_json_response(result.get("raw_response", ""))
                if parsed:
                    return self._parse_validation_result(parsed)
            
            # Fallback: simple heuristic validation
            return self._validate_fallback(extracted_infos)
            
        except Exception as e:
            logger.error(f"Cross-check failed: {e}")
            return self._validate_fallback(extracted_infos)
    
    def _build_validation_prompt(self, infos_dicts: List[Dict[str, Any]]) -> str:
        """Build inline validation prompt when template not available."""
        import json
        infos_text = "\n\n".join([
            f"Source {i}:\n{json.dumps(info, indent=2)}"
            for i, info in enumerate(infos_dicts, 1)
        ])
        
        return f"""Validate and cross-check entity information from multiple sources.

Extracted Information:
{infos_text}

Check for:
1. Consistency of legal name across sources
2. Country matches domain TLD (e.g., .co.za → South Africa)
3. ASN and IP ranges are consistent with domain
4. Any conflicts or inconsistencies

Return JSON:
{{
    "valid": true/false,
    "confidence": 0.0-1.0,
    "conflicts": ["list of conflicts if any"],
    "validated_info": {{
        "legal_name": "best legal name",
        "country": "best country",
        "domain": "best domain",
        "asn": "best ASN or null",
        "ip_ranges": ["best IP ranges"]
    }}
}}"""
    
    def _parse_validation_result(self, parsed: Dict[str, Any]) -> ValidationResult:
        """Parse validation result from LLM response."""
        validated_info = None
        if parsed.get("validated_info"):
            validated_info = EntityInfo.from_dict(parsed["validated_info"])
        
        return ValidationResult(
            valid=bool(parsed.get("valid", False)),
            confidence=float(parsed.get("confidence", 0.0)),
            conflicts=parsed.get("conflicts", []),
            validated_info=validated_info
        )
    
    def _validate_fallback(
        self, 
        extracted_infos: List[EntityInfo]
    ) -> ValidationResult:
        """Fallback validation using simple heuristics."""
        best_info = max(extracted_infos, key=lambda x: x.confidence)
        
        conflicts = []
        
        # Check domain consistency
        domains = [info.domain for info in extracted_infos if info.domain]
        if len(set(domains)) > 1:
            conflicts.append("Multiple different domains found")
        
        # Check country consistency
        countries = [info.country for info in extracted_infos if info.country]
        if len(set(countries)) > 1:
            conflicts.append("Multiple different countries found")
        
        return ValidationResult(
            valid=len(conflicts) == 0,
            confidence=best_info.confidence,
            conflicts=conflicts,
            validated_info=best_info
        )
    
    # =========================================================================
    # STEP 7: Ask User / Format Response
    # =========================================================================
    
    def _step_ask_user(
        self,
        candidates: List[EntityCandidate],
        entity_info: Optional[EntityInfo] = None,
        validation: Optional[ValidationResult] = None,
        potential_targets: Optional[List[str]] = None,
        suggested_questions: Optional[List[str]] = None
    ) -> str:
        """Format response for user confirmation or selection.
        
        Args:
            candidates: List of entity candidates
            entity_info: Extracted entity info (if available)
            validation: Validation result (if available)
            potential_targets: Potential target names from classification
            suggested_questions: Suggested clarification questions
            
        Returns:
            Formatted message for user
        """
        # Multiple candidates - show selection
        if len(candidates) > 1:
            candidates_dicts = [c.to_dict() for c in candidates[:3]]
            return ClarificationMessages.format_candidates_found(candidates_dicts)
        
        # Single validated entity - show confirmation
        if entity_info and entity_info.is_valid():
            conflicts = validation.conflicts if validation else []
            confidence = validation.confidence if validation else entity_info.confidence
            
            return ClarificationMessages.format_confirmation(
                legal_name=entity_info.legal_name,
                country=entity_info.country,
                domain=entity_info.domain,
                asn=entity_info.asn,
                ip_ranges=entity_info.ip_ranges,
                confidence=confidence,
                conflicts=conflicts
            )
        
        # No valid info - ask for more details
        target = potential_targets[0] if potential_targets else "the target"
        return ClarificationMessages.format_need_more_info(
            target=target,
            suggested_questions=suggested_questions
        )
    
    # =========================================================================
    # Extract Query Info (Company Name / Location)
    # =========================================================================
    
    def _extract_query_info(
        self, 
        user_prompt: str, 
        context_text: str
    ) -> ExtractedQuery:
        """Extract company name and location from user prompt using LLM."""
        extraction_prompt = f"""Extract company name and location from the following user message.
User message: {user_prompt}
Previous context: {context_text}

Return a JSON object with:
- "company_name": The company/organization name (or null if not found)
- "location": The country/region/location (or null if not found)

Examples:
- "hellogroup from South Africa" -> {{"company_name": "hellogroup", "location": "South Africa"}}
- "My target is hellogroup from South Africa" -> {{"company_name": "hellogroup", "location": "South Africa"}}
- "assess hello group" -> {{"company_name": "hello group", "location": null}}
- "My target is example.com" -> {{"company_name": null, "location": null}}

Return only valid JSON:"""
        
        try:
            result = self.qwen3.analyze_and_breakdown(
                user_prompt=extraction_prompt,
                conversation_history=None
            )
            
            if result.get("success"):
                parsed = parse_llm_json_response(result.get("raw_response", ""))
                if parsed:
                    return ExtractedQuery.from_dict(parsed)
                    
        except Exception as e:
            logger.debug(f"Query info extraction failed: {e}")
        
        return ExtractedQuery()
    
    # =========================================================================
    # Main Pipeline Entry Point
    # =========================================================================
    
    def clarify_target(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Clarify ambiguous target using the full pipeline.
        
        Pipeline:
        1. Lexical Normalize (RapidFuzz) - normalize user input
        2. Entity Candidates (DB/Vector DB) - lookup existing entities
        3. Ambiguity Detection & Scoring - check if ambiguous and score
        4. Web Search Tool - if ambiguous, search for entity
        5. Structured Extraction - extract legal_name, country, domain, ASN, IP ranges
        6. LLM Reasoning + Cross-check - validate and cross-check extracted info
        7. Ask User (Confirm) - show candidates (multiple if ambiguous) for confirmation
        
        Args:
            state: GraphState dictionary
            
        Returns:
            Updated state dictionary
        """
        # STEP 1: Lexical Normalize
        user_prompt = state["user_prompt"]
        user_prompt = self._step_normalize(user_prompt)
        state["user_prompt"] = user_prompt
        
        # Check if target already verified
        conversation_id = state.get("conversation_id") or state.get("session_id")
        verified_target = self.memory_manager.get_verified_target(
            session_id=conversation_id,
            conversation_id=conversation_id if state.get("conversation_id") else None
        )
        
        if verified_target:
            return self._handle_verified_target(state, verified_target)
        
        # Get existing clarification state
        clarification = state.get("target_clarification", {})
        potential_targets = clarification.get("potential_targets", [])
        suggested_questions = clarification.get("suggested_questions", [])
        search_context = clarification.get("search_context", {})
        
        # Build conversation context
        conversation_history = state.get("conversation_history", [])
        context_text = self._build_context_text(conversation_history)
        
        # Extract company name and location
        company_name = search_context.get("company_name")
        location = search_context.get("location")
        
        if potential_targets and not company_name:
            company_name = potential_targets[0]
        
        # Use LLM to extract query info
        query_info = self._extract_query_info(user_prompt, context_text)
        if query_info.company_name:
            company_name = query_info.company_name
        if query_info.location:
            location = query_info.location
        
        # STEP 2: Entity Candidates
        candidates = []
        if company_name or user_prompt:
            search_query = company_name or user_prompt
            candidates = self._step_lookup_candidates(
                query=search_query,
                conversation_id=conversation_id if state.get("conversation_id") else None,
                session_id=conversation_id
            )
            
            # STEP 3: Ambiguity Scoring
            ambiguity_score = self._step_calculate_ambiguity(
                candidates, company_name, location
            )
            clarification["ambiguity_score"] = ambiguity_score
            
            # High-confidence candidate from DB
            if candidates and candidates[0].confidence > 0.8:
                return self._handle_high_confidence_candidate(
                    state, candidates[0], clarification, conversation_id
                )
            
            # Multiple candidates with similar confidence
            if len(candidates) > 1 and ambiguity_score > 0.5:
                return self._handle_multiple_candidates(
                    state, candidates[:3], clarification
                )
        
        # STEP 4: Web Search
        if company_name or location:
            search_results = self._step_web_search(
                company_name=company_name,
                location=location,
                user_prompt=user_prompt,
                context=context_text,
                conversation_id=conversation_id,
                conversation_history=conversation_history
            )
            
            if search_results:
                # STEP 5: Extract Structured Info
                extracted_info = self._step_extract_info(
                    search_results=search_results,
                    company_name=company_name,
                    location=location
                )
                
                # STEP 6: Cross-check
                validation = self._step_cross_check([extracted_info])
                validated_info = validation.validated_info or extracted_info
                
                # Verify domain is valid
                if validated_info.is_valid() and validation.confidence > 0.3:
                    return self._handle_validated_entity(
                        state, validated_info, validation, clarification,
                        conversation_id, context_text
                    )
                else:
                    self._stream(
                        "model_response", "system",
                        ClarificationMessages.NO_VALID_DOMAIN
                    )
        
        # STEP 7: Ask User (no valid info found)
        if not company_name and not location:
            message = self._step_ask_user(
                candidates=[],
                potential_targets=potential_targets,
                suggested_questions=suggested_questions
            )
            state["final_answer"] = message
            self._stream("state_update", "clarify_target", None)
            self._stream("model_response", "system", message)
        else:
            self._stream(
                "model_response", "system",
                ClarificationMessages.SEARCHING.format(
                    target=company_name or "target"
                )
            )
        
        return state
    
    # =========================================================================
    # Helper Methods for Main Pipeline
    # =========================================================================
    
    def _build_context_text(
        self, 
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """Build context text from conversation history."""
        if not conversation_history:
            return ""
        
        recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
        return " ".join([
            msg.get("content", "") 
            for msg in recent 
            if isinstance(msg, dict)
        ])
    
    def _handle_verified_target(
        self, 
        state: Dict[str, Any], 
        verified_target: str
    ) -> Dict[str, Any]:
        """Handle case where target is already verified."""
        clarification = state.get("target_clarification", {})
        clarification["is_ambiguous"] = False
        clarification["verified_domain"] = verified_target
        state["target_clarification"] = clarification
        
        session_context = self.memory_manager.get_agent_context()
        if session_context:
            session_context.domain = verified_target
            state["session_context"] = session_context.to_dict()
        
        state["user_prompt"] = f"{state['user_prompt']} {verified_target}"
        return state
    
    def _handle_high_confidence_candidate(
        self,
        state: Dict[str, Any],
        candidate: EntityCandidate,
        clarification: Dict[str, Any],
        conversation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Handle high-confidence candidate from database."""
        if conversation_id:
            self.memory_manager.save_verified_target(
                session_id=conversation_id,
                domain=candidate.domain,
                conversation_id=conversation_id if state.get("conversation_id") else None
            )
        
        clarification["is_ambiguous"] = False
        clarification["verified_domain"] = candidate.domain
        state["target_clarification"] = clarification
        state["user_prompt"] = f"{state['user_prompt']} {candidate.domain}"
        
        self._stream(
            "model_response", "system",
            ClarificationMessages.FOUND_FROM_DB.format(domain=candidate.domain)
        )
        
        # Stream target info card
        self._stream("target_info", "clarify_target", {
            "domain": candidate.domain,
            "company_info": {"additional_info": f"Found from {candidate.source} with {int(candidate.confidence*100)}% confidence"}
        })
        
        return state
    
    def _handle_multiple_candidates(
        self,
        state: Dict[str, Any],
        candidates: List[EntityCandidate],
        clarification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle multiple candidates requiring user selection."""
        message = self._step_ask_user(candidates=candidates)
        state["final_answer"] = message
        state["target_clarification"] = clarification
        
        self._stream("state_update", "clarify_target", None)
        self._stream("model_response", "system", message)
        
        return state
    
    def _handle_validated_entity(
        self,
        state: Dict[str, Any],
        entity_info: EntityInfo,
        validation: ValidationResult,
        clarification: Dict[str, Any],
        conversation_id: Optional[str],
        context_text: str
    ) -> Dict[str, Any]:
        """Handle validated entity from web search."""
        # Save to memory
        if conversation_id:
            self.memory_manager.save_verified_target(
                session_id=conversation_id,
                domain=entity_info.domain,
                conversation_id=conversation_id if state.get("conversation_id") else None,
                structured_info=entity_info.to_dict()
            )
        
        # Update session context
        session_context = self.memory_manager.get_agent_context()
        if session_context:
            session_context.domain = entity_info.domain
            state["session_context"] = session_context.to_dict()
        
        # Update user prompt
        original_prompt = state["user_prompt"]
        if context_text:
            state["user_prompt"] = f"{context_text} {entity_info.domain}"
        else:
            state["user_prompt"] = f"{original_prompt} {entity_info.domain}"
        
        # Format confirmation message
        message = self._step_ask_user(
            candidates=[],
            entity_info=entity_info,
            validation=validation
        )
        state["final_answer"] = message
        
        self._stream("state_update", "clarify_target", None)
        
        # Stream target info card
        self._stream("target_info", "clarify_target", {
            "domain": entity_info.domain,
            "company_info": entity_info.to_dict()
        })
        
        self._stream("model_response", "system", message)
        
        # Mark as resolved
        clarification["is_ambiguous"] = False
        clarification["verified_domain"] = entity_info.domain
        state["target_clarification"] = clarification
        
        return state
