from openai import OpenAI
import os
from typing import Dict, List
from utils.logger import setup_logger

logger = setup_logger('websearch_service')

class WebSearchService:
    """Service for searching the web using OpenAI's websearch capabilities"""

    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")

        self.client = OpenAI(api_key=api_key)

    def search_person(self, query: str) -> Dict:
        """
        Search for information about a person using OpenAI's built-in websearch

        Args:
            query: The search query (name, email, username, etc.)

        Returns:
            Dictionary containing search results
        """
        logger.info(f"Performing websearch for query: {query}")

        try:
            input_prompt = f"""
            You are a person search assistant with web search capabilities. Search the web for information about: {query}
            
            Return structured JSON with these keys:
            - basic_info: object with name, age, location, occupation, education, company
            - social_profiles: array of objects with platform, username, url, followers, verified
            - photos: array of objects with url, source, caption
            - notable_mentions: array of objects with title, description, url, source. IMPORTANT: Include ONLY items that are directly about this specific person. Exclude general news about their company, industry, or unrelated people with similar names.

            If information is not found, use empty objects/arrays. Return only valid JSON.
            """

            response = self.client.responses.create(
                model="gpt-5-mini",
                input=input_prompt,
                reasoning={ "effort": "low" },
                text={ "verbosity": "low" }
            )

            result = response.output_text

            import json
            try:
                structured_data = json.loads(result) if result else {}
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response, using raw content")
                structured_data = {'raw_content': result}

            logger.info(f"Websearch completed for query: {query}\n")

            return {
                'source': 'openai_websearch',
                'query': query,
                'content': result,
                'raw_response': result,
                'structured_data': structured_data
            }

        except Exception as e:
            logger.error(f"Error performing websearch: {str(e)}")
            return {
                'source': 'openai_websearch',
                'query': query,
                'content': None,
                'error': str(e),
                'structured_data': {
                    'basic_info': {},
                    'social_profiles': [],
                    'photos': [],
                    'notable_mentions': []
                }
            }

    def extract_structured_info(self, query: str, websearch_result: str) -> Dict:
        """
        Use GPT to extract structured information from websearch results

        Args:
            query: The original search query
            websearch_result: The raw websearch result text

        Returns:
            Structured dictionary with categorized information
        """

        logger.info(f"Extracting structured information for query: {query}")
        try:
            input_prompt = f"""
            You are a data extraction assistant. Extract and structure information about a person into these categories:
            1. basic_info: name, age, location, occupation, education
            2. social_profiles: list of social media profiles with platform and URL
            3. photos: list of photo URLs if found
            4. notable_mentions: list of notable achievements, news, or mentions. MUST be directly about this person. Ignore unrelated news.

            Query: {query}
            
            Websearch results:
            {websearch_result}
            
            Return ONLY a valid JSON object with these keys. If information is not found, use empty objects/arrays.
            """

            response = self.client.responses.create(
                model="gpt-5-mini",
                input=input_prompt,
                reasoning={ "effort": "low" },
                text={ "verbosity": "low" }
            )

            import json
            structured_data = json.loads(response.output_text)
            logger.info(f"Structured information extracted for query: {query}\n")
            return structured_data

        except Exception as e:
            logger.error(f"Error extracting structured info: {str(e)}")
            return {
                'basic_info': {},
                'social_profiles': [],
                'photos': [],
                'notable_mentions': []
            }
    def find_candidates(self, query: str) -> List[Dict]:
        """
        Find potential person candidates based on a query.
        Returns a list of candidates with basic info.
        """
        logger.info(f"Finding candidates for query: {query}")

        try:
            input_prompt = f"""
            You are a person search assistant. Find potential candidates matching the query: "{query}".
            
            Return a JSON object with a key "candidates" containing a list of objects.
            Each candidate object must have:
            - id: A unique string identifier (can be the name)
            - name: Full name (Cleaned: remove titles like "Dr." or prefixes like "20+ profiles")
            - description: A concise summary in the format "Occupation • Location" (e.g. "Software Engineer • New York, NY" or "Actor • Los Angeles, CA").
            - imageUrl: A URL to a profile photo if found (or null)
            
            If no specific person is found, try to return the most likely best match.
            If multiple people match (e.g. "Michael Jordan"), return the top 5 most relevant ones.
            """

            response = self.client.responses.create(
                model="gpt-5-mini",
                input=input_prompt,
                reasoning={ "effort": "low" },
                text={ "verbosity": "low" }
            )

            import json
            try:
                data = json.loads(response.output_text)
                candidates = data.get("candidates", [])
                return candidates
            except json.JSONDecodeError:
                logger.error("Failed to parse candidates JSON")
                return []

        except Exception as e:
            logger.error(f"Error finding candidates: {str(e)}")
            return []

    def deduplicate_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """
        Deduplicate candidates using LLM to identify same people.
        """
        if not candidates:
            return []
            
        logger.info(f"Deduplicating {len(candidates)} candidates via LLM")
        
        try:
            import json
            
            # Store original descriptions and truncate for LLM processing
            original_descriptions = {}
            truncated_candidates = []
            
            for candidate in candidates:
                candidate_copy = candidate.copy()
                original_desc = candidate.get('description', '')
                original_descriptions[candidate.get('id', '')] = original_desc
                
                # Truncate description to first 500 characters
                if len(original_desc) > 500:
                    candidate_copy['description'] = original_desc[:500] + '...'
                
                truncated_candidates.append(candidate_copy)
            
            candidates_json = json.dumps(truncated_candidates, indent=2)
            input_prompt = f"""
            You are a data deduplication expert. I have a list of person candidates found from search results.
            Some of them refer to the same real-world person but might have slightly different names or descriptions.
            
            Your task is to merge duplicates into a single entry ONLY if they are definitely the same person.
            - If two entries refer to the same person (e.g. "Elon Musk" and "Elon Reeve Musk"), merge them.
            - If they have the same name but different descriptions (e.g. "John Smith (Actor)" vs "John Smith (Doctor)"), KEEP THEM SEPARATE.
            - Do NOT merge if you are unsure. Better to show duplicates than to hide a valid candidate.
            
            When merging duplicates:
            - Pick the most complete/common name (Cleaned: remove titles/prefixes).
            - Pick the most descriptive description (Format: "Occupation • Location").
            - Pick the best image URL (prefer non-null). CRITICAL: You MUST include the "imageUrl" field in every output candidate, even if null.
            - Keep the ID of the primary entry.
            - PRESERVE ALL OTHER FIELDS from the original candidates (like link, snippet, etc).
            
            Candidates:
            {candidates_json}
            
            Return a JSON object with a key "candidates" containing the deduplicated list.
            Each candidate MUST have at minimum: id, name, description, imageUrl (can be null).
            """
            
            response = self.client.responses.create(
                model="gpt-5-mini",
                input=input_prompt,
                reasoning={ "effort": "low" },
                text={ "verbosity": "low" }
            )
            
            try:
                data = json.loads(response.output_text)
                deduplicated = data.get("candidates", [])
                
                # Restore original descriptions
                for candidate in deduplicated:
                    candidate_id = candidate.get('id', '')
                    if candidate_id in original_descriptions:
                        candidate['description'] = original_descriptions[candidate_id]
                
                logger.info(f"Deduplication complete. Reduced from {len(candidates)} to {len(deduplicated)}")
                return deduplicated
            except json.JSONDecodeError:
                logger.error("Failed to parse deduplication JSON")
                return candidates
                
        except Exception as e:
            logger.error(f"Error in deduplication: {e}")
            return candidates # Fallback to original list

# Singleton instance
_websearch_service = None

def get_websearch_service() -> WebSearchService:
    """Get or create the WebSearchService singleton"""
    global _websearch_service
    if _websearch_service is None:
        _websearch_service = WebSearchService()
    return _websearch_service
