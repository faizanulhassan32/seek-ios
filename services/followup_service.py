import os
from typing import Dict, List
from anthropic import Anthropic
from utils.logger import setup_logger

logger = setup_logger('followup_service')

class FollowUpService:
    """Service for generating fast, focused follow-up answers about persons"""

    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set")
        self.anthropic_client = Anthropic(api_key=api_key)


    def generate_followup_answer(self, person_data: Dict, question: str) -> Dict:
        """
        Generate a concise follow-up answer about a person

        Args:
            person_data: Dictionary containing person information from database
            question: User's follow-up question

        Returns:
            Dictionary with answer, relevant sources/photos, and related questions
        """
        try:
            query = person_data.get('query', 'this person')
            basic_info = person_data.get('basic_info', {})
            social_profiles = person_data.get('social_profiles', [])
            notable_mentions = person_data.get('notable_mentions', [])
            photos = person_data.get('photos', [])
            raw_sources = person_data.get('raw_sources', [])

            # Build focused context for this specific question
            context = self._build_focused_context(
                query, basic_info, social_profiles, notable_mentions, question
            )

            # Generate concise answer using Claude
            logger.info(f"Generating follow-up answer for: {question}")

            system_prompt = f"""
                You are a knowledgeable assistant that provides SHORT, CONCISE answers to specific questions about people. 
                Keep answers to 2-3 sentences maximum. Be direct and factual. Start with the answer immediately without preamble.
            """

            response = self.anthropic_client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                            Question: {question}

                            Context about {query}:
                            {context}

                            Provide a brief, direct answer.
                        """
                    }
                ],
                tools=[{
                    "name": "provide_followup_answer",
                    "description": "Provide a concise follow-up answer to the user's question about the person",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "answer": {
                                "type": "string",
                                "description": "A brief, direct answer (2-3 sentences maximum)"
                            }
                        },
                        "required": ["answer"]
                    }
                }],
                tool_choice={
                    "type": "tool",
                    "name": "provide_followup_answer"
                }
            )

            # Extract answer from tool use
            tool_use_block = response.content[0]
            answer = tool_use_block.input["answer"]
            
            logger.info(f"Successfully generated follow-up answer")

            # Filter relevant photos (max 3)
            relevant_photos = self._filter_relevant_photos(photos, question)[:3]

            # Filter relevant sources (max 4)
            relevant_sources = self._filter_relevant_sources(
                raw_sources, social_profiles, notable_mentions, question
            )[:4]

            # Generate related follow-up questions
            related_questions = self._generate_related_followups(
                query, question, basic_info
            )

            return {
                'question': question,
                'answer': answer,
                'photos': relevant_photos,
                'sources': relevant_sources,
                'related_questions': related_questions
            }

        except Exception as e:
            logger.error(f"Error generating follow-up answer: {str(e)}", exc_info=True)
            raise


    def _build_focused_context(self,query: str,basic_info: Dict,social_profiles: List[Dict],notable_mentions: List[Dict],question: str) -> str:
        """Build focused context relevant to the specific question"""
        context_parts = []

        # Always include basic info
        if basic_info:
            if basic_info.get('name'):
                context_parts.append(f"Name: {basic_info['name']}")
            if basic_info.get('occupation'):
                context_parts.append(f"Occupation: {basic_info['occupation']}")
            if basic_info.get('company'):
                context_parts.append(f"Company: {basic_info['company']}")
            if basic_info.get('location'):
                context_parts.append(f"Location: {basic_info['location']}")
            if basic_info.get('age'):
                context_parts.append(f"Age: {basic_info['age']}")

        # Include notable mentions (most relevant)
        if notable_mentions:
            mentions = [
                f"- {m.get('title', '')}: {m.get('description', '')}"
                for m in notable_mentions[:5]
                if m.get('title')
            ]
            if mentions:
                context_parts.append(f"Notable achievements:\n" + "\n".join(mentions))

        return '\n'.join(context_parts) if context_parts else f"Person: {query}"


    def _filter_relevant_photos(self, photos: List[Dict], question: str) -> List[Dict]:
        """Filter photos that might be relevant to the question"""
        if not photos:
            return []

        # For now, return first few photos
        # In future, could use semantic similarity
        return photos[:3]


    def _filter_relevant_sources(self,raw_sources: List[Dict],social_profiles: List[Dict],notable_mentions: List[Dict],question: str) -> List[Dict]:
        """Filter sources that might be relevant to the question"""
        sources = []

        # Add notable mentions as sources (most relevant)
        for mention in notable_mentions[:2]:
            if mention.get('title'):
                sources.append({
                    'name': mention.get('source', 'Source'),
                    'url': mention.get('url', ''),
                    'type': 'news',
                    'description': mention.get('title')
                })

        # Add social profiles
        for profile in social_profiles[:2]:
            platform = profile.get('platform', '').capitalize()
            sources.append({
                'name': platform,
                'url': profile.get('url', ''),
                'type': 'social',
                'description': profile.get('username', f'@{platform.lower()}')
            })

        return sources[:4]


    def _generate_related_followups(self,query: str,current_question: str,basic_info: Dict) -> List[str]:
        """Generate related follow-up questions based on current question"""
        try:
            occupation = basic_info.get('occupation', 'person')

            system_prompt = """
                You are an assistant that generates relevant follow-up questions. Generate questions users might ask next.
            """

            response = self.anthropic_client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                temperature=0.7,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                            User just asked: '{current_question}' about {query} ({occupation}).
                            Generate 3-4 related follow-up questions they might ask next.
                        """
                    }
                ],
                tools=[{
                    "name": "provide_followup_questions",
                    "description": "Generate a list of relevant follow-up questions the user might ask next",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "questions": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "Array of 3-4 follow-up questions without numbering"
                            }
                        },
                        "required": ["questions"]
                    }
                }],
                tool_choice={
                    "type": "tool",
                    "name": "provide_followup_questions"
                }
            )

            # Extract questions from tool use
            tool_use_block = response.content[0]
            questions = tool_use_block.input["questions"]

            return questions[:4]

        except Exception as e:
            logger.error(f"Error generating related follow-ups: {str(e)}")
            return []


# Singleton instance
_followup_service = None

def get_followup_service() -> FollowUpService:
    """Get or create the FollowUpService singleton"""
    global _followup_service
    if _followup_service is None:
        _followup_service = FollowUpService()
    return _followup_service