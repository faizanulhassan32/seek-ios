import os
import json
from typing import Dict, List
from anthropic import Anthropic
from utils.logger import setup_logger

logger = setup_logger('websearch_service')

class WebSearchService:
    """Service for searching the web using Claude's web search tool"""

    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set in environment variables")

        self.anthropic_client = Anthropic(api_key=api_key)


    def search_person(self, query: str) -> Dict:
        """
        Search for information about a person using Claude's web search tool

        Args:
            query: The search query (name, email, username, etc.)

        Returns:
            Dictionary containing search results
        """
        logger.info(f"Performing websearch for query: {query}")

        try:
            system_prompt = """
                You are a person search assistant with web search capabilities. Use the web search tool to find current information about people.

                After searching, provide structured information with these keys:
                - basic_info: object with name, age, location, occupation, education, company
                - social_profiles: array of objects with platform, username, url, followers, verified
                - photos: array of objects with url, source, caption
                - notable_mentions: array of objects with title, description, url, source. IMPORTANT: Include ONLY items that are directly about this specific person. Exclude general news about their company, industry, or unrelated people with similar names.

                If information is not found, use empty objects/arrays.
            """

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                temperature=0,
                system=system_prompt,
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 5
                    },
                    {
                        "name": "provide_person_info",
                        "description": "Provide structured information about a person after web search",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "basic_info": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "age": {"type": ["string", "null"]},
                                        "location": {"type": ["string", "null"]},
                                        "occupation": {"type": ["string", "null"]},
                                        "education": {"type": ["string", "null"]},
                                        "company": {"type": ["string", "null"]}
                                    }
                                },
                                "social_profiles": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "platform": {"type": "string"},
                                            "username": {"type": ["string", "null"]},
                                            "url": {"type": "string"},
                                            "followers": {"type": ["string", "null"]},
                                            "verified": {"type": ["boolean", "null"]}
                                        }
                                    }
                                },
                                "photos": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "url": {"type": "string"},
                                            "source": {"type": ["string", "null"]},
                                            "caption": {"type": ["string", "null"]}
                                        }
                                    }
                                },
                                "notable_mentions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "description": {"type": ["string", "null"]},
                                            "url": {"type": ["string", "null"]},
                                            "source": {"type": ["string", "null"]}
                                        }
                                    }
                                }
                            },
                            "required": ["basic_info", "social_profiles", "photos", "notable_mentions"]
                        }
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": f"Search the web for comprehensive information about: {query}"
                    }
                ]
            )

            # Process the response - Claude may use web_search tool multiple times
            result_text = ""
            web_search_results = []
            structured_data = {}
            
            for content_block in response.content:
                if content_block.type == "text":
                    result_text += content_block.text
                elif content_block.type == "tool_use":
                    if content_block.name == "web_search":
                        logger.info(f"Web search executed with query: {content_block.input.get('query', '')}")
                        web_search_results.append(content_block.input)
                    elif content_block.name == "provide_person_info":
                        structured_data = content_block.input

            # If Claude used tools, we need to continue the conversation
            if response.stop_reason == "tool_use" and not structured_data:
                # Continue conversation with tool results
                messages = [
                    {
                        "role": "user",
                        "content": f"Search the web for comprehensive information about: {query}"
                    },
                    {
                        "role": "assistant",
                        "content": response.content
                    }
                ]

                # Get final structured response
                final_response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=4096,
                    temperature=0,
                    system=system_prompt,
                    tools=[
                        {
                            "name": "provide_person_info",
                            "description": "Provide structured information about a person after web search",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "basic_info": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "age": {"type": ["string", "null"]},
                                            "location": {"type": ["string", "null"]},
                                            "occupation": {"type": ["string", "null"]},
                                            "education": {"type": ["string", "null"]},
                                            "company": {"type": ["string", "null"]}
                                        }
                                    },
                                    "social_profiles": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "platform": {"type": "string"},
                                                "username": {"type": ["string", "null"]},
                                                "url": {"type": "string"},
                                                "followers": {"type": ["string", "null"]},
                                                "verified": {"type": ["boolean", "null"]}
                                            }
                                        }
                                    },
                                    "photos": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "url": {"type": "string"},
                                                "source": {"type": ["string", "null"]},
                                                "caption": {"type": ["string", "null"]}
                                            }
                                        }
                                    },
                                    "notable_mentions": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "title": {"type": "string"},
                                                "description": {"type": ["string", "null"]},
                                                "url": {"type": ["string", "null"]},
                                                "source": {"type": ["string", "null"]}
                                            }
                                        }
                                    }
                                },
                                "required": ["basic_info", "social_profiles", "photos", "notable_mentions"]
                            }
                        }
                    ],
                    tool_choice={
                        "type": "tool",
                        "name": "provide_person_info"
                    },
                    messages=messages
                )

                result_text = ""
                for content_block in final_response.content:
                    if content_block.type == "text":
                        result_text += content_block.text
                    elif content_block.type == "tool_use" and content_block.name == "provide_person_info":
                        structured_data = content_block.input

            if not structured_data:
                structured_data = {
                    'basic_info': {},
                    'social_profiles': [],
                    'photos': [],
                    'notable_mentions': []
                }

            logger.info(f"Websearch completed for query: {query}\n")

            return {
                'source': 'claude_websearch',
                'query': query,
                'content': result_text,
                'raw_response': result_text,
                'structured_data': structured_data,
                'web_searches_performed': len(web_search_results)
            }

        except Exception as e:
            logger.error(f"Error performing websearch: {str(e)}")
            return {
                'source': 'claude_websearch',
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
        Use Claude to extract structured information from websearch results

        Args:
            query: The original search query
            websearch_result: The raw websearch result text

        Returns:
            Structured dictionary with categorized information
        """

        logger.info(f"Extracting structured information for query: {query}")
        try:
            system_prompt = """
                You are a data extraction assistant. Extract and structure information about a person into these categories:
                1. basic_info: name, age, location, occupation, education
                2. social_profiles: list of social media profiles with platform and URL
                3. photos: list of photo URLs if found
                4. notable_mentions: list of notable achievements, news, or mentions. MUST be directly about this person. Ignore unrelated news.

                Provide structured information with these exact keys. If information is not found, use empty objects/arrays.
            """

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                temperature=0,
                system=system_prompt,
                tools=[{
                    "name": "provide_extracted_info",
                    "description": "Provide extracted structured information about a person",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "basic_info": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": ["string", "null"]},
                                    "age": {"type": ["string", "null"]},
                                    "location": {"type": ["string", "null"]},
                                    "occupation": {"type": ["string", "null"]},
                                    "education": {"type": ["string", "null"]}
                                }
                            },
                            "social_profiles": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "platform": {"type": "string"},
                                        "url": {"type": "string"}
                                    }
                                }
                            },
                            "photos": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "notable_mentions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": "string"},
                                        "description": {"type": ["string", "null"]},
                                        "url": {"type": ["string", "null"]},
                                        "source": {"type": ["string", "null"]}
                                    }
                                }
                            }
                        },
                        "required": ["basic_info", "social_profiles", "photos", "notable_mentions"]
                    }
                }],
                tool_choice={
                    "type": "tool",
                    "name": "provide_extracted_info"
                },
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                            Query: {query}
            
                            Websearch results:
                            {websearch_result}
                        """
                    }
                ]
            )

            # Extract structured data from tool use
            tool_use_block = response.content[0]
            structured_data = tool_use_block.input
            
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
        Find potential person candidates based on a query using web search.
        Returns a list of candidates with basic info.
        """
        logger.info(f"Finding candidates for query: {query}")

        try:
            system_prompt = """
                You are a person search assistant. Use web search to find potential candidates matching the query.
            
                After searching, return a JSON object with a key "candidates" containing a list of objects.
                Each candidate object must have:
                - id: A unique string identifier (can be the name)
                - name: Full name (Cleaned: remove titles like "Dr." or prefixes like "20+ profiles")
                - description: A concise summary in the format "Occupation • Location" (e.g. "Software Engineer • New York, NY" or "Actor • Los Angeles, CA").
                - imageUrl: A URL to a profile photo if found (or null)

                If no specific person is found, try to return the most likely best match.
                If multiple people match (e.g. "Michael Jordan"), return the top 5 most relevant ones.
            """

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                temperature=0,
                system=system_prompt,
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 3
                    },
                    {
                        "name": "provide_candidates",
                        "description": "Provide a list of person candidates found from web search",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "candidates": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                            "description": {"type": "string"},
                                            "imageUrl": {"type": ["string", "null"]}
                                        },
                                        "required": ["id", "name", "description"]
                                    }
                                }
                            },
                            "required": ["candidates"]
                        }
                    }
                ],
                tool_choice={
                    "type": "tool",
                    "name": "provide_candidates"
                },
                messages=[
                    {
                        "role": "user",
                        "content": f'Find candidates for: "{query}"'
                    }
                ]
            )

            # Process response
            result_text = ""
            candidates = []
            
            for content_block in response.content:
                if content_block.type == "text":
                    result_text += content_block.text
                elif content_block.type == "tool_use" and content_block.name == "provide_candidates":
                    candidates = content_block.input.get("candidates", [])

            # If Claude used tools, continue conversation
            if response.stop_reason == "tool_use" and not candidates:
                messages = [
                    {
                        "role": "user",
                        "content": f'Find candidates for: "{query}"'
                    },
                    {
                        "role": "assistant",
                        "content": response.content
                    }
                ]

                final_response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=2048,
                    temperature=0,
                    system=system_prompt,
                    tools=[{
                        "name": "provide_candidates",
                        "description": "Provide a list of person candidates found from web search",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "candidates": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                            "description": {"type": "string"},
                                            "imageUrl": {"type": ["string", "null"]}
                                        },
                                        "required": ["id", "name", "description"]
                                    }
                                }
                            },
                            "required": ["candidates"]
                        }
                    }],
                    tool_choice={
                        "type": "tool",
                        "name": "provide_candidates"
                    },
                    messages=messages
                )

                for content_block in final_response.content:
                    if content_block.type == "tool_use" and content_block.name == "provide_candidates":
                        candidates = content_block.input.get("candidates", [])

            return candidates

        except Exception as e:
            logger.error(f"Error finding candidates: {str(e)}")
            return []


    def deduplicate_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """
        Deduplicate candidates using Claude to identify same people.
        """
        if not candidates:
            return []
            
        logger.info(f"Deduplicating {len(candidates)} candidates via Claude")
        
        try:
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
            
            system_prompt = """
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

                Provide the deduplicated list.
                Each candidate MUST have at minimum: id, name, description, imageUrl (can be null).
            """
            
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                temperature=0,
                system=system_prompt,
                tools=[{
                    "name": "provide_deduplicated_candidates",
                    "description": "Provide a deduplicated list of candidates",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "candidates": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "imageUrl": {"type": ["string", "null"]}
                                    },
                                    "required": ["id", "name", "description", "imageUrl"]
                                }
                            }
                        },
                        "required": ["candidates"]
                    }
                }],
                tool_choice={
                    "type": "tool",
                    "name": "provide_deduplicated_candidates"
                },
                messages=[
                    {
                        "role": "user",
                        "content": f"Candidates:\n{candidates_json}"
                    }
                ]
            )
            
            # Extract deduplicated candidates from tool use
            tool_use_block = response.content[0]
            deduplicated = tool_use_block.input.get("candidates", [])
            
            # Restore original descriptions
            for candidate in deduplicated:
                candidate_id = candidate.get('id', '')
                if candidate_id in original_descriptions:
                    candidate['description'] = original_descriptions[candidate_id]
            
            logger.info(f"Deduplication complete. Reduced from {len(candidates)} to {len(deduplicated)}")
            return deduplicated
                
        except Exception as e:
            logger.error(f"Error in deduplication: {e}")
            return candidates # Fallback to original list


    def fetch_candidates_from_web(self, query: str, max_candidates: int = 6) -> List[Dict]:
        """
        Find potential person candidates using Claude's web search tool.
        Returns a list of candidates with basic info, limited to max_candidates.
        """
        logger.info(f"Finding candidates via Claude web search for query: {query}")

        try:
            system_prompt = f"""
                You are a person search assistant. Use web search to find potential candidates matching the query.

                CRITICAL: Find {max_candidates} UNIQUE INDIVIDUALS - not the same person with different job titles.
                - If you find "Nathan Lytle - Flight Nurse" and "Nathan Lytle - Surgeon", verify these are DIFFERENT people before including both
                - Look for distinguishing information (different companies, different locations, different LinkedIn profiles, etc.)
                - If uncertain whether two results are the same person, only include ONE of them

                For each candidate, try to find a profile photo URL from their LinkedIn, company website, or professional profile.

                After searching, provide a list of candidate objects (maximum {max_candidates} candidates).
                Each candidate object must have:
                - id: A unique string identifier (can be the name + occupation)
                - name: Full name (Cleaned: remove titles like "Dr." or prefixes like "20+ profiles")
                - description: A concise summary in the format "Occupation • Location"
                - imageUrl: A direct URL to their profile photo (if found, otherwise null)

                Return ONLY the most relevant {max_candidates} UNIQUE INDIVIDUALS.
            """

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                temperature=0,
                system=system_prompt,
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 10
                    },
                    {
                        "name": "provide_candidates",
                        "description": "Provide a list of person candidates found from web search",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "candidates": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                            "description": {"type": "string"},
                                            "imageUrl": {"type": ["string", "null"], "description": "URL to profile photo or null if not found"}
                                        },
                                        "required": ["id", "name", "description", "imageUrl"
                                        ]
                                    }
                                }
                            },
                            "required": ["candidates"]
                        }
                    }
                ],
                messages=[
                    {
                        "role": "user",
                        "content": f'Find candidates for: "{query}"'
                    }
                ]
            )

            candidates = []
            
            for content_block in response.content:
                if content_block.type == "tool_use" and content_block.name == "provide_candidates":
                    candidates = content_block.input.get("candidates", [])

            if response.stop_reason == "tool_use" and not candidates:
                messages = [
                    {
                        "role": "user",
                        "content": f'Find candidates for: "{query}"'
                    },
                    {
                        "role": "assistant",
                        "content": response.content
                    }
                ]

                final_response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=4096,
                    temperature=0,
                    system=system_prompt,
                    tools=[{
                        "name": "provide_candidates",
                        "description": "Provide a list of person candidates found from web search",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "candidates": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"},
                                            "description": {"type": "string"},
                                            "imageUrl": {"type": ["string", "null"], "description": "URL to profile photo or null if not found"}
                                        },
                                        "required": ["id", "name", "description", "imageUrl"]
                                    }
                                }
                            },
                            "required": ["candidates"]
                        }
                    }
                    ],
                    tool_choice={
                        "type": "tool",
                        "name": "provide_candidates"
                    },
                    messages=messages
                )

                for content_block in final_response.content:
                    if content_block.type == "tool_use" and content_block.name == "provide_candidates":
                        candidates = content_block.input.get("candidates", [])
            
            logger.info(f"Claude web search returned {len(candidates)} candidates")
            return candidates

        except Exception as e:
            logger.error(f"Error finding candidates via Claude web search: {str(e)}")
            return []


# Singleton instance
_websearch_service = None

def get_websearch_service() -> WebSearchService:
    """Get or create the WebSearchService singleton"""
    global _websearch_service
    if _websearch_service is None:
        _websearch_service = WebSearchService()
    return _websearch_service