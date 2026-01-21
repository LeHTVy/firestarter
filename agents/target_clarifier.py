"""Target clarifier for handling ambiguous targets."""

import json
from typing import Dict, Any, Optional, Callable, List
from utils.input_normalizer import InputNormalizer
from models.generic_ollama_agent import GenericOllamaAgent
from models.functiongemma_agent import FunctionGemmaAgent
from memory.manager import MemoryManager
from agents.context_manager import ContextManager
from rag.retriever import ConversationRetriever
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


class TargetClarifier:
    """Handles target clarification using FunctionGemma and web search."""
    
    def __init__(self,
                 functiongemma: FunctionGemmaAgent,
                 qwen3: GenericOllamaAgent,
                 memory_manager: MemoryManager,
                 context_manager: ContextManager,
                 stream_callback: Optional[Callable[[str, str, Any], None]] = None):
        """Initialize target clarifier.
        
        Args:
            functiongemma: FunctionGemma agent for tool calling
            qwen3: Generic Ollama agent for AI understanding (e.g., Mistral)
            memory_manager: Memory manager for session state
            context_manager: Context manager for session context
            stream_callback: Optional callback for streaming events
        """
        self.functiongemma = functiongemma
        self.qwen3 = qwen3
        self.memory_manager = memory_manager
        self.context_manager = context_manager
        self.stream_callback = stream_callback
        self.conversation_retriever = ConversationRetriever()
        
        # Initialize InputNormalizer for lexical normalization
        self.input_normalizer = InputNormalizer(ai_model=qwen3)
        
        # Load prompt templates (with fallback if not available)
        template_dir = Path(__file__).parent.parent / "prompts"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        try:
            self.extraction_template = self.env.get_template("target_extraction.jinja2")
        except:
            self.extraction_template = None
        try:
            self.validation_template = self.env.get_template("target_validation.jinja2")
        except:
            self.validation_template = None
    
    def _lookup_entity_candidates(self, 
                                  query: str, 
                                  conversation_id: Optional[str] = None,
                                  session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lookup entity candidates from DB/Vector DB.
        
        Args:
            query: Search query (company name, domain, etc.)
            conversation_id: Conversation ID for namespace isolation
            session_id: Legacy session ID
            
        Returns:
            List of candidate entities with confidence scores
        """
        candidates = []
        
        # 1. Search conversation history in Vector DB
        try:
            conv_id = conversation_id or session_id
            if conv_id:
                # Search in conversation-specific vector store
                context_results = self.conversation_retriever.retrieve_context(
                    query=query,
                    k=5,
                    conversation_id=conversation_id,
                    session_id=session_id
                )
                
                for result in context_results:
                    # Extract potential entity mentions from context
                    content = result.get("content", "") or result.get("text", "")
                    if content:
                        # Simple heuristic: look for domain-like patterns
                        import re
                        domain_pattern = re.compile(r'\b([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.(?:[a-zA-Z]{2,}))\b')
                        domains = domain_pattern.findall(content)
                        
                        for domain in domains[:3]:  # Limit to 3 domains per result
                            candidates.append({
                                "domain": domain.lower(),
                                "source": "conversation_history",
                                "confidence": 0.6,  # Medium confidence from history
                                "context": content[:200]  # First 200 chars
                            })
        except Exception as e:
            # Don't fail if vector search fails
            pass
        
        # 2. Check verified targets database (PostgreSQL)
        try:
            # Get all conversations with verified targets
            conversations = self.memory_manager.conversation_store.list_conversations(limit=100)
            
            for conv in conversations:
                verified_target = conv.get('verified_target')
                if verified_target:
                    # Simple fuzzy match
                    query_lower = query.lower()
                    target_lower = verified_target.lower()
                    
                    # Check if query matches target
                    if query_lower in target_lower or target_lower in query_lower:
                        # Calculate simple similarity
                        from rapidfuzz import fuzz
                        similarity = fuzz.ratio(query_lower, target_lower) / 100.0
                        
                        if similarity > 0.5:  # 50% similarity threshold
                            candidates.append({
                                "domain": verified_target,
                                "source": "verified_targets_db",
                                "confidence": similarity * 0.8,  # Slightly lower than exact match
                                "conversation_id": conv.get('id')
                            })
        except Exception as e:
            # Don't fail if DB lookup fails
            pass
        
        # Remove duplicates and sort by confidence
        seen_domains = set()
        unique_candidates = []
        for candidate in candidates:
            domain = candidate.get("domain", "")
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                unique_candidates.append(candidate)
        
        # Sort by confidence (descending)
        unique_candidates.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        return unique_candidates[:5]  # Return top 5 candidates
    
    def _calculate_ambiguity_score(self, 
                                  candidates: List[Dict[str, Any]], 
                                  company_name: Optional[str] = None,
                                  location: Optional[str] = None) -> float:
        """Calculate ambiguity score (0-1) based on number of candidates and confidence.
        
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
            # Single candidate - score based on confidence
            confidence = candidates[0].get("confidence", 0)
            return 1.0 - confidence  
        
        # Multiple candidates - calculate based on:
        # 1. Number of candidates (more = more ambiguous)
        # 2. Confidence spread (similar confidence = more ambiguous)
        # 3. Whether we have company_name and location (more context = less ambiguous)
        
        num_candidates = len(candidates)
        confidences = [c.get("confidence", 0) for c in candidates]
        max_conf = max(confidences)
        min_conf = min(confidences)
        conf_spread = max_conf - min_conf
        
        # Base ambiguity from number of candidates
        base_ambiguity = min(0.8, 0.3 + (num_candidates - 1) * 0.15)
        
        # Reduce ambiguity if confidence spread is large (one clear winner)
        if conf_spread > 0.3:
            base_ambiguity *= 0.6
        
        # Reduce ambiguity if we have company_name and location
        if company_name and location:
            base_ambiguity *= 0.7
        
        return min(1.0, base_ambiguity)
    
    def _format_multiple_candidates(self, candidates: List[Dict[str, Any]]) -> str:
        """Format multiple candidates for user selection (like ChatGPT).
        
        Args:
            candidates: List of candidate entities
            
        Returns:
            Formatted message showing all candidates
        """
        if not candidates:
            return ""
        
        message = f"Mình tìm thấy {len(candidates)} công ty/tổ chức có thể khớp:\n\n"
        
        for i, candidate in enumerate(candidates, 1):
            domain = candidate.get("domain", "N/A")
            source = candidate.get("source", "unknown")
            confidence = candidate.get("confidence", 0)
            
            # Try to get structured info if available
            legal_name = candidate.get("legal_name", "")
            country = candidate.get("country", "")
            asn = candidate.get("asn")
            ip_ranges = candidate.get("ip_ranges", [])
            
            message += f"{i}. "
            if legal_name:
                message += f"{legal_name}"
            else:
                message += f"{domain}"
            
            if country:
                message += f" – {country}"
            
            message += f" – domain: {domain}"
            
            if asn:
                message += f" – ASN: {asn}"
            
            if ip_ranges:
                message += f" – IP ranges: {', '.join(ip_ranges[:3])}"
            
            message += f" (confidence: {int(confidence * 100)}%)\n"
        
        message += f"\nBạn đang nói tới công ty nào? (Nhập số 1-{len(candidates)} hoặc cung cấp thêm thông tin)"
        
        return message
    
    def _generate_search_queries(self, 
                               company_name: Optional[str],
                               location: Optional[str],
                               user_prompt: str,
                               context: str) -> List[str]:
        """Generate intelligent search queries using LLM.
        
        Args:
            company_name: Company name
            location: Location/country
            user_prompt: Original user prompt
            context: Conversation context
            
        Returns:
            List of suggested search queries
        """
        # Generate queries using LLM
        query_generation_prompt = f"""Generate 3-5 intelligent web search queries to find the official website domain for a company/organization.

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
            result = self.qwen3.analyze_and_breakdown(
                user_prompt=query_generation_prompt,
                conversation_history=None
            )
            
            if result.get("success"):
                response_text = result.get("raw_response", "")
                
                # Extract JSON
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    json_text = response_text
                
                try:
                    parsed = json.loads(json_text)
                    queries = parsed.get("queries", [])
                    if queries:
                        return queries
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        
        # Fallback: Generate simple queries
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
    
    def _extract_structured_info(self, search_results: List[Dict[str, Any]], 
                                 company_name: Optional[str] = None,
                                 location: Optional[str] = None) -> Dict[str, Any]:
        """Extract structured information from web search results using LLM.
        
        Args:
            search_results: List of web search result dicts
            company_name: Optional company name for context
            location: Optional location for context
            
        Returns:
            Structured info dict with legal_name, country, domain, asn, ip_ranges, confidence
        """
        # Format search results for LLM
        formatted_results = []
        for i, result in enumerate(search_results[:10], 1):  # Limit to top 10
            formatted_results.append({
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "link": result.get("link", "")
            })
        
        # Use prompt template if available, otherwise use inline prompt
        if self.extraction_template:
            extraction_prompt = self.extraction_template.render(
                search_results=formatted_results,
                company_name=company_name or "unknown",
                location=location or "unknown"
            )
        else:
            # Fallback inline prompt
            results_text = "\n\n".join([
                f"Result {i}:\nTitle: {r['title']}\nSnippet: {r['snippet']}\nLink: {r['link']}"
                for i, r in enumerate(formatted_results, 1)
            ])
            
            extraction_prompt = f"""Extract structured information about a company/organization from web search results.

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

Only extract information that is clearly stated in the search results. If information is not found, use null for strings or empty arrays for lists."""
        
        try:
            # Use Qwen3 to extract structured info
            result = self.qwen3.analyze_and_breakdown(
                user_prompt=extraction_prompt,
                conversation_history=None
            )
            
            if result.get("success"):
                analysis = result.get("analysis", {})
                
                # Try to parse JSON from response
                response_text = result.get("raw_response", "")
                
                # Extract JSON from markdown code blocks if present
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    json_text = response_text
                
                try:
                    structured_info = json.loads(json_text)
                    
                    # Validate and normalize
                    return {
                        "legal_name": structured_info.get("legal_name") or "",
                        "country": structured_info.get("country") or "",
                        "domain": structured_info.get("domain") or "",
                        "asn": structured_info.get("asn"),
                        "ip_ranges": structured_info.get("ip_ranges") or [],
                        "confidence": min(1.0, max(0.0, float(structured_info.get("confidence", 0.5))))
                    }
                except json.JSONDecodeError:
                    # Fallback: try to extract from raw response
                    pass
            
            # Fallback: extract domain from search results (simple heuristic)
            domain = None
            for result in search_results:
                link = result.get("link", "")
                if link:
                    from urllib.parse import urlparse
                    try:
                        parsed = urlparse(link)
                        domain = parsed.netloc.replace("www.", "").lower()
                        if domain and len(domain) > 3:
                            break
                    except:
                        continue
            
            return {
                "legal_name": company_name or "",
                "country": location or "",
                "domain": domain or "",
                "asn": None,
                "ip_ranges": [],
                "confidence": 0.3  # Low confidence for fallback
            }
            
        except Exception as e:
            # Return minimal structure on error
            return {
                "legal_name": company_name or "",
                "country": location or "",
                "domain": "",
                "asn": None,
                "ip_ranges": [],
                "confidence": 0.0
            }
    
    def _cross_check_entity(self, 
                           extracted_infos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Cross-check extracted entity information for consistency.
        
        Args:
            extracted_infos: List of extracted info dicts from multiple sources
            
        Returns:
            Validation result with confidence, validation flags, and conflicts
        """
        if not extracted_infos:
            return {
                "valid": False,
                "confidence": 0.0,
                "conflicts": [],
                "validated_info": None
            }
        
        # Use prompt template if available
        if self.validation_template:
            validation_prompt = self.validation_template.render(
                extracted_infos=extracted_infos
            )
        else:
            # Fallback inline prompt
            infos_text = "\n\n".join([
                f"Source {i}:\n{json.dumps(info, indent=2)}"
                for i, info in enumerate(extracted_infos, 1)
            ])
            
            validation_prompt = f"""Validate and cross-check entity information from multiple sources.

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
        
        try:
            result = self.qwen3.analyze_and_breakdown(
                user_prompt=validation_prompt,
                conversation_history=None
            )
            
            if result.get("success"):
                response_text = result.get("raw_response", "")
                
                # Extract JSON
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    json_text = response_text
                
                try:
                    validation_result = json.loads(json_text)
                    return validation_result
                except json.JSONDecodeError:
                    pass
            
            # Fallback: simple heuristic validation
            # Take the info with highest confidence
            best_info = max(extracted_infos, key=lambda x: x.get("confidence", 0))
            
            # Simple consistency checks
            conflicts = []
            domains = [info.get("domain") for info in extracted_infos if info.get("domain")]
            if len(set(domains)) > 1:
                conflicts.append("Multiple different domains found")
            
            countries = [info.get("country") for info in extracted_infos if info.get("country")]
            if len(set(countries)) > 1:
                conflicts.append("Multiple different countries found")
            
            return {
                "valid": len(conflicts) == 0,
                "confidence": best_info.get("confidence", 0.5),
                "conflicts": conflicts,
                "validated_info": best_info
            }
            
        except Exception as e:
            # Fallback on error
            best_info = max(extracted_infos, key=lambda x: x.get("confidence", 0)) if extracted_infos else None
            return {
                "valid": best_info is not None,
                "confidence": best_info.get("confidence", 0.3) if best_info else 0.0,
                "conflicts": ["Validation error"],
                "validated_info": best_info
            }
    
    def clarify_target(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Clarify ambiguous target using FunctionGemma and web search.
        
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
        # STEP 1: Lexical Normalize (RapidFuzz) - Normalize user input first
        user_prompt = state["user_prompt"]
        normalized_prompt = self.input_normalizer.normalize_target(user_prompt)
        if normalized_prompt != user_prompt:
            user_prompt = normalized_prompt
            state["user_prompt"] = normalized_prompt
        
        # First check if target already verified
        conversation_id = state.get("conversation_id") or state.get("session_id")
        verified_target = self.memory_manager.get_verified_target(
            session_id=conversation_id,
            conversation_id=conversation_id if state.get("conversation_id") else None
        )
        
        if verified_target:
            # Target already verified, skip clarification
            clarification = state.get("target_clarification", {})
            clarification["is_ambiguous"] = False
            clarification["verified_domain"] = verified_target
            state["target_clarification"] = clarification
            
            # Update session context
            session_context = self.context_manager.get_context()
            if session_context:
                session_context = session_context.merge_with({"target_domain": verified_target})
                state["session_context"] = session_context.to_dict()
            
            # Update user prompt to include verified domain
            state["user_prompt"] = f"{state['user_prompt']} {verified_target}"
            
            return state
        
        clarification = state.get("target_clarification", {})
        potential_targets = clarification.get("potential_targets", [])
        suggested_questions = clarification.get("suggested_questions", [])
        can_search = clarification.get("can_search", False)
        search_context = clarification.get("search_context", {})
        
        # Get conversation context
        conversation_history = state.get("conversation_history", [])
        
        # Build context for AI to understand
        context_text = ""
        if conversation_history:
            recent_messages = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            context_text = " ".join([msg.get("content", "") for msg in recent_messages if isinstance(msg, dict)])
        
        # Extract company name and location from search_context or potential_targets
        company_name = search_context.get("company_name") or (potential_targets[0] if potential_targets else None)
        location = search_context.get("location")
        
        # ALWAYS try to extract company_name and location from user prompt
        # This handles cases like "hellogroup from South Africa" or "My target is company from country"
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
                response_text = result.get("raw_response", "")
                
                # Extract JSON from markdown code blocks if present
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    json_text = response_text
                
                try:
                    extracted = json.loads(json_text)
                    # Update company_name and location if extracted (override existing if better)
                    extracted_company = extracted.get("company_name")
                    extracted_location = extracted.get("location")
                    
                    if extracted_company:
                        company_name = extracted_company
                    if extracted_location:
                        location = extracted_location
                except json.JSONDecodeError:
                    pass  # Fallback to existing values
        except Exception:
            pass  # Fallback to existing values
        
        # STEP 2: Entity Candidates (DB/Vector DB) - Lookup existing entities
        entity_candidates = []
        if company_name or user_prompt:
            search_query = company_name or user_prompt
            entity_candidates = self._lookup_entity_candidates(
                query=search_query,
                conversation_id=conversation_id if state.get("conversation_id") else None,
                session_id=conversation_id
            )
            
            # STEP 3: Ambiguity Scoring - Calculate ambiguity score based on candidates
            ambiguity_score = self._calculate_ambiguity_score(entity_candidates, company_name, location)
            clarification["ambiguity_score"] = ambiguity_score
            
            # If we found high-confidence candidates (>0.8), use them directly
            if entity_candidates and entity_candidates[0].get("confidence", 0) > 0.8:
                best_candidate = entity_candidates[0]
                found_domain = best_candidate.get("domain")
                
                if found_domain:
                    # Use candidate from DB, skip web search
                    if conversation_id:
                        self.memory_manager.save_verified_target(
                            session_id=conversation_id,
                            domain=found_domain,
                            conversation_id=conversation_id if state.get("conversation_id") else None
                        )
                    
                    clarification["is_ambiguous"] = False
                    clarification["verified_domain"] = found_domain
                    state["target_clarification"] = clarification
                    state["user_prompt"] = f"{state['user_prompt']} {found_domain}"
                    
                    if self.stream_callback:
                        self.stream_callback("model_response", "system", 
                            f"Found verified target from database: {found_domain}")
                    
                    return state
            
            # If we have multiple candidates with similar confidence, show all for user selection
            if len(entity_candidates) > 1 and ambiguity_score > 0.5:
                # Multiple candidates found - show all for user to choose
                candidates_message = self._format_multiple_candidates(entity_candidates[:3])  # Top 3
                state["final_answer"] = candidates_message
                
                if self.stream_callback:
                    self.stream_callback("state_update", "clarify_target", None)
                    self.stream_callback("model_response", "system", candidates_message)
                
                return state
        
        # STEP 4: Web Search Tool - If we have company_name OR location, automatically searchrun 
        if company_name or location:
            # Generate intelligent search queries using LLM
            search_queries = self._generate_search_queries(company_name, location, user_prompt, context_text)
            
            # Build prompt for FunctionGemma with explicit query suggestions
            target_verification_prompt = f"""You need to find the official website domain for a company/organization.

Company name: {company_name or 'unknown'}
Location: {location or 'unknown'}
Previous conversation context: {context_text}
Current user message: {user_prompt}

Suggested search queries (use one of these or create similar):
{chr(10).join(f'- {q}' for q in search_queries[:3])}

Your task:
1. Call the web_search tool with an appropriate query to find the official website domain
2. The query should combine company name and location intelligently
3. Use num_results=5 to get multiple search results
4. The goal is to find the most relevant domain that matches the company name and location

Target: Find the official website domain for this company/organization."""
            
            try:
                # Create streaming callbacks
                model_callback = None
                tool_stream_callback = None
                if self.stream_callback:
                    def callback(chunk: str):
                        self.stream_callback("model_response", "functiongemma_verify", chunk)
                    model_callback = callback
                    
                    def tool_callback(tool_name: str, command: str, line: str):
                        self.stream_callback("tool_execution", tool_name, line)
                    tool_stream_callback = tool_callback
                
                # Call FunctionGemma with web_search tool only
                functiongemma_result = self.functiongemma.call_with_tools(
                    user_prompt=target_verification_prompt,
                    tools=["web_search"],
                    session_id=conversation_id,  # Use conversation_id
                    conversation_history=conversation_history,
                    stream_callback=model_callback,
                    tool_stream_callback=tool_stream_callback
                )
                
                # Parse results from FunctionGemma
                web_search_result = None  
                tool_results = [] 
                
                if functiongemma_result.get("success"):
                    tool_results = functiongemma_result.get("tool_results", [])
                    
                    # Check if FunctionGemma called web_search tool
                    if not tool_results:
                        # FunctionGemma didn't call any tool - fallback to asking user
                        if self.stream_callback:
                            self.stream_callback("model_response", "system", 
                                "Note: Could not automatically search for domain. Please provide the domain name.")
                    else:
                        # Find web_search result
                        for tr in tool_results:
                            if tr.get("tool_name") == "web_search":
                                if tr.get("result", {}).get("success"):
                                    web_search_result = tr.get("result", {})
                                    break
                                else:
                                    # Tool was called but failed
                                    if self.stream_callback:
                                        error_msg = tr.get("result", {}).get("error", "Unknown error")
                                        self.stream_callback("model_response", "system", 
                                            f"Note: Web search failed: {error_msg}")
                else:
                    # FunctionGemma call failed
                    if self.stream_callback:
                        error_msg = functiongemma_result.get("error", "Unknown error")
                        self.stream_callback("model_response", "system", 
                            f"Note: Automatic domain search failed: {error_msg}. Please provide the domain name.")
                
                if web_search_result and web_search_result.get("results"):
                        search_results = web_search_result.get("results", [])
                        
                        # NEW: Extract structured information from search results
                        extracted_info = self._extract_structured_info(
                            search_results=search_results,
                            company_name=company_name,
                            location=location
                        )
                        
                        # NEW: Cross-check extracted info (if we have multiple sources, we'd extract from each)
                        # For now, we extract from all search results as one source
                        validation_result = self._cross_check_entity([extracted_info])
                        
                        validated_info = validation_result.get("validated_info") or extracted_info
                        validation_confidence = validation_result.get("confidence", extracted_info.get("confidence", 0.5))
                        conflicts = validation_result.get("conflicts", [])
                        
                        found_domain = validated_info.get("domain", "")
                        legal_name = validated_info.get("legal_name", "")
                        country = validated_info.get("country", "")
                        asn = validated_info.get("asn")
                        ip_ranges = validated_info.get("ip_ranges", [])
                        
                        # Verify domain format is valid
                        if found_domain:
                            temp_normalizer = InputNormalizer(ai_model=self.qwen3)
                            extracted_targets = temp_normalizer.extract_targets(found_domain, verify_domains=False)
                            is_valid_domain = any(temp_normalizer._is_domain(t) for t in extracted_targets)
                        else:
                            is_valid_domain = False
                        
                        if is_valid_domain and validation_confidence > 0.3:
                            # Save structured verified target to memory manager
                            if conversation_id:
                                self.memory_manager.save_verified_target(
                                    session_id=conversation_id,
                                    domain=found_domain,
                                    conversation_id=conversation_id if state.get("conversation_id") else None,
                                    structured_info={
                                        "legal_name": legal_name,
                                        "country": country,
                                        "domain": found_domain,
                                        "asn": asn,
                                        "ip_ranges": ip_ranges,
                                        "confidence": validation_confidence
                                    }
                                )
                            
                            # Update session context
                            session_context = self.context_manager.get_context()
                            if session_context:
                                session_context = session_context.merge_with({"target_domain": found_domain})
                                state["session_context"] = session_context.to_dict()
                            
                            # Found and verified domain! Update user prompt and continue
                            original_prompt = state["user_prompt"]
                            if context_text:
                                updated_prompt = f"{context_text} {found_domain}"
                            else:
                                updated_prompt = f"{original_prompt} {found_domain}"
                            state["user_prompt"] = updated_prompt
                            
                            # NEW: Enhanced confirmation message with structured info
                            confirmation_message = f"Bạn đang nói tới:\n"
                            if legal_name:
                                confirmation_message += f"- Legal Name: {legal_name}\n"
                            if country:
                                confirmation_message += f"- Country: {country}\n"
                            confirmation_message += f"- Domain: {found_domain}\n"
                            if asn:
                                confirmation_message += f"- ASN: {asn}\n"
                            if ip_ranges:
                                confirmation_message += f"- IP Ranges: {', '.join(ip_ranges)}\n"
                            
                            confirmation_message += f"\nConfidence: {int(validation_confidence * 10)}/10\n"
                            
                            if conflicts:
                                confirmation_message += f"\nNote: Found some conflicts: {', '.join(conflicts)}\n"
                            
                            confirmation_message += "\nĐúng không?"
                            
                            state["final_answer"] = confirmation_message
                            
                            # Stream the found domain
                            if self.stream_callback:
                                self.stream_callback("state_update", "clarify_target", None)
                                self.stream_callback("model_response", "system", confirmation_message)
                            
                            # Mark as not ambiguous anymore and continue
                            clarification["is_ambiguous"] = False
                            clarification["verified_domain"] = found_domain
                            state["target_clarification"] = clarification
                            
                            return state
                        else:
                            # Domain found but not valid or score too low - fallback to asking user
                            if self.stream_callback:
                                self.stream_callback("model_response", "system", 
                                    "Note: Could not find a valid domain from search results. Please provide the domain name.")
            except Exception as e:
                # FunctionGemma call failed, fall through to asking user
                # Log error but continue with fallback
                if self.stream_callback:
                    self.stream_callback("model_response", "system", 
                        f"Note: Automatic domain search failed: {str(e)}. Please provide the domain name.")
                pass
        
        # If search didn't work or we don't have enough context, only ask user if we have NO information
        # If we have company_name or location, we should have already tried to search
        if not company_name and not location:
            # No information at all - ask user
            main_target = potential_targets[0] if potential_targets else "the target"
            
            clarification_message = (
                f"I need more information to identify {main_target}.\n\n"
            )
            
            if suggested_questions:
                clarification_message += f"Please provide one of the following:\n"
                for i, question in enumerate(suggested_questions[:3], 1):  
                    clarification_message += f"{i}. {question}\n"
                clarification_message += "\n"
            
            clarification_message += (
                f"Alternatively, you can provide:\n"
                f"- The domain name (e.g., example.com)\n"
                f"- The IP address (e.g., 192.168.1.1)\n"
                f"- The website URL (e.g., https://example.com)\n"
                f"- Additional context like company location or industry"
            )
            
            # Set final answer to clarification message
            state["final_answer"] = clarification_message
            
            # Stream the clarification
            if self.stream_callback:
                self.stream_callback("state_update", "clarify_target", None)
                self.stream_callback("model_response", "system", clarification_message)
        else:
            # We have some information but search failed - inform user
            if self.stream_callback:
                self.stream_callback("model_response", "system", 
                    f"Đang tìm kiếm thông tin về {company_name or 'target'}... Vui lòng cung cấp thêm thông tin nếu có.")
        
        return state
