import os
import json
from anthropic import Anthropic
from typing import Dict, List
from utils.logger import setup_logger

logger = setup_logger('answer_service')

class AnswerService:
    """Service for generating AI-powered answers about persons"""

    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set")
        self.anthropic_client = Anthropic(api_key=api_key)


    def generate_answer(self, person_data: Dict) -> str:
        """
        Generate comprehensive biographical answer about a person

        Args:
            person_data: Dictionary containing person information

        Returns:
            AI-generated biographical text
        """
        try:
            # Extract person info
            query = person_data.get('query', 'this person')
            basic_info = person_data.get('basic_info', {})
            social_profiles = person_data.get('social_profiles', [])
            notable_mentions = person_data.get('notable_mentions', [])

            # Build context from available data
            context = self._build_context(query, basic_info, social_profiles, notable_mentions)

            logger.info(f"Generating answer for query: {query} using responses API")

            system_prompt = f"""
                You are a knowledgeable assistant that provides comprehensive, well-structured biographical information about people. 
                Write in a clear, encyclopedic style similar to Wikipedia. Focus on facts, achievements, and notable information.
            """

            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                temperature=0.7,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                            Provide a biographical summary about {query}. Include their background, major achievements, career, and notable contributions.
                
                            Available information:
                            {context}
                        """
                    }
                ],
                tools=[{
                    "name": "provide_biography",
                    "description": "Provide comprehensive biographical summary about the person",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "biography": {
                                "type": "string",
                                "description": "Comprehensive biographical text about the person including background, achievements, career, and notable contributions"
                            }
                        },
                        "required": ["biography"]
                    }
                }],
                tool_choice={
                    "type": "tool",
                    "name": "provide_biography"
                }
            )
            
            logger.info("Claude response received")
            
            tool_use_block = response.content[0]
            answer = tool_use_block.input["biography"].strip()
            
            # AI Evaluation of Validity
            is_valid = self.evaluate_answer_validity(answer)
            
            if not is_valid:
                candidate_desc = person_data.get('candidate_description')
                if candidate_desc:
                    logger.info(f"AI Evaluator marked answer as INVALID for {query}. Triggering fallback.")
                    # OVERWRITE the answer variable
                    answer = self.generate_fallback_summary(query, candidate_desc)
                else:
                    logger.warning(f"AI Evaluator marked answer as INVALID for {query}, but no candidate description available.")
            
            logger.info(f"Successfully generated answer for {query}")
            return answer

        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}", exc_info=True)
            # Try fallback if we have candidate description even on error
            candidate_desc = person_data.get('candidate_description')
            if candidate_desc:
                try:
                    return self.generate_fallback_summary(query, candidate_desc)
                except:
                    pass
            raise


    def evaluate_answer_validity(self, answer_text: str) -> bool:
        """
        Ask AI if the answer is valid or a refusal.
        Returns True if VALID, False if INVALID/REFUSAL.
        """

        try:
            # Heuristic check for obvious refusals (Safety Net)
            lower_text = answer_text.lower()
            refusal_phrases = [
                "i don't have", "i do not have", "i cannot provide", "i can't provide",
                "no reliable", "no verifiable", "doesn't have information",
                "don't have information", "unable to provide", "cannot fabricate"
            ]
            if any(phrase in lower_text for phrase in refusal_phrases):
                logger.info("Heuristic check detected refusal. Overriding AI Evaluator.")
                return False

            system_prompt = """
                Analyze the following text. Determine if it contains specific biographical facts about the person.

                Rules:
                1. If the text says "I don't have information", "I cannot verify", or similar refusals -> Reply INVALID.
                2. If the text provides ANY specific facts (job, age, works, background) -> Reply VALID.
                3. If the text is a template or asks for more info -> Reply INVALID.

                Reply ONLY with 'VALID' or 'INVALID'.
            """

            response = self.anthropic_client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                temperature=0,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f'"{answer_text}"...'
                    }
                ],
                tools=[{
                    "name": "evaluate_validity",
                    "description": "Evaluate if the answer contains valid biographical information or is a refusal",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "validity": {
                                "type": "string",
                                "enum": ["VALID", "INVALID"],
                                "description": "Whether the answer contains specific biographical facts (VALID) or is a refusal/template (INVALID)"
                            }
                        },
                        "required": ["validity"]
                    }
                }],
                tool_choice={
                    "type": "tool",
                    "name": "evaluate_validity"
                }
            )

            logger.info("Claude response received")
            
            tool_use_block = response.content[0]
            result = tool_use_block.input["validity"].upper()
            logger.info(f"AI Evaluator result: {result}")
            
            return result == "VALID"
        
        except Exception as e:
            logger.error(f"Error in AI evaluation: {e}")
            # Fallback to assuming valid to prevent blocking
            return True


    def generate_fallback_summary(self, query: str, candidate_context: str) -> str:
        """Generate a professional summary from candidate context"""
        try:
            system_prompt = f"Summarize the following known data into a 2-paragraph profile for {query}. Do not add external info, just professionalize this."
            
            response = self.anthropic_client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                temperature=0.5,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Data:\n{candidate_context}"
                    }
                ],
                tools=[{
                    "name": "provide_summary",
                    "description": "Provide professional summary from candidate context data",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Professional 2-paragraph profile summary based on the provided data"
                            }
                        },
                        "required": ["summary"]
                    }
                }],
                tool_choice={
                    "type": "tool",
                    "name": "provide_summary"
                }
            )
            
            logger.info("Claude response received")
            
            tool_use_block = response.content[0]
            return tool_use_block.input["summary"].strip()
        except Exception as e:
            logger.error(f"Error generating fallback summary: {str(e)}")
            return f"{query}: {candidate_context}" # Ultimate fallback


    def generate_related_questions(self, query: str, person_data: Dict) -> List[str]:
        """
        Generate related questions about a person

        Args:
            query: Person's name
            person_data: Person information

        Returns:
            List of related questions
        """
        try:
            basic_info = person_data.get('basic_info', {})
            occupation = basic_info.get('occupation', '')
            company = basic_info.get('company', '')

            logger.info(f"Generating related questions for query: {query}")

            system_prompt = """You are an assistant that generates relevant follow-up questions about people. Return only the questions, one per line, without numbering."""

            response = self.anthropic_client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                temperature=0.8,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                            Generate 6 relevant follow-up questions about {query}. 
                            Consider their role as {occupation or 'a notable person'} {f'at {company}' if company else ''}. 
                            Focus on commonly searched topics like net worth, companies, achievements, personal life, and career milestones.
                        """
                    }
                ],
                tools=[{
                    "name": "provide_questions",
                    "description": "Provide list of relevant follow-up questions about the person",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "questions": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of 6 relevant follow-up questions about the person"
                            }
                        },
                        "required": ["questions"]
                    }
                }],
                tool_choice={
                    "type": "tool",
                    "name": "provide_questions"
                }
            )

            logger.info("Claude response received")
            
            tool_use_block = response.content[0]
            questions = tool_use_block.input["questions"]

            logger.info(f"Generated {len(questions)} related questions for {query}")
            return questions[:6]  # Return max 6 questions

        except Exception as e:
            logger.error(f"Error generating related questions: {str(e)}", exc_info=True)
            return []  # Return empty list on error


    def _build_context(self,query: str,basic_info: Dict,social_profiles: List[Dict],notable_mentions: List[Dict]) -> str:
        """Build context string from available person data"""
        context_parts = []

        # Basic info
        if basic_info:
            if basic_info.get('name'):
                context_parts.append(f"Name: {basic_info['name']}")
            if basic_info.get('occupation'):
                context_parts.append(f"Occupation: {basic_info['occupation']}")
            if basic_info.get('company'):
                context_parts.append(f"Company: {basic_info['company']}")
            if basic_info.get('location'):
                context_parts.append(f"Location: {basic_info['location']}")
            if basic_info.get('education'):
                context_parts.append(f"Education: {', '.join(basic_info['education']) if isinstance(basic_info['education'], list) else basic_info['education']}")

        # Social profiles
        if social_profiles:
            platforms = [p.get('platform') for p in social_profiles if p.get('platform')]
            if platforms:
                context_parts.append(f"Social media: {', '.join(platforms)}")

        # Notable mentions
        if notable_mentions:
            mentions = [m.get('title', '') for m in notable_mentions[:3] if m.get('title')]
            if mentions:
                context_parts.append(f"Notable mentions: {'; '.join(mentions)}")

        return '\n'.join(context_parts) if context_parts else f"Person: {query}"


    def extract_osint_data(self, text_content: str) -> Dict:
        """
        Extract structured OSINT data (relatives, locations) from text using LLM.
        """
        try:
            # Truncate text to avoid token limits (keep first 20000 chars (~5000 tokens) - usually has the header info)
            truncated_text = text_content[:20000]
            
            system_prompt = """
                Extract 'Possible Relatives' and 'Locations' from the following text.
                Text is from a public records site.

                Return a JSON object with keys:
                - relatives: list of strings (names)
                - locations: list of strings (City, State)
            """
            
            response = self.anthropic_client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                temperature=0,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Text:\n{truncated_text}"
                    }
                ],
                tools=[{
                    "name": "extract_osint_data",
                    "description": "Extract relatives and locations from public records text",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "relatives": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of possible relative names extracted from the text"
                            },
                            "locations": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of locations in format 'City, State' extracted from the text"
                            }
                        },
                        "required": ["relatives", "locations"]
                    }
                }],
                tool_choice={
                    "type": "tool",
                    "name": "extract_osint_data"
                }
            )
            
            logger.info("Claude response received")
            
            tool_use_block = response.content[0]
            data = tool_use_block.input
            
            return data
            
        except Exception as e:
            logger.error(f"Error extracting OSINT data via LLM: {e}")
            return {'relatives': [], 'locations': []}


# Singleton instance
_answer_service = None

def get_answer_service() -> AnswerService:
    """Get or create the AnswerService singleton"""
    global _answer_service
    if _answer_service is None:
        _answer_service = AnswerService()
    return _answer_service
