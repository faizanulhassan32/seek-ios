from typing import Dict, List, Optional
from datetime import datetime

class Person:
    """
    Person model representing aggregated information about an individual
    Matches the Supabase schema and Swift model structure
    """

    def __init__(
        self,
        query: str,
        basic_info: Optional[Dict] = None,
        social_profiles: Optional[List[Dict]] = None,
        photos: Optional[List[Dict]] = None,
        notable_mentions: Optional[List[Dict]] = None,
        raw_sources: Optional[List[Dict]] = None,
        person_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        answer: Optional[str] = None,
        related_questions: Optional[List[str]] = None,
        answer_generated_at: Optional[datetime] = None
    ):
        self.id = person_id
        self.query = query
        self.basic_info = basic_info or {}
        self.social_profiles = social_profiles or []
        self.photos = photos or []
        self.notable_mentions = notable_mentions or []
        self.raw_sources = raw_sources or []
        self.created_at = created_at
        self.updated_at = updated_at
        self.answer = answer
        self.related_questions = related_questions or []
        self.answer_generated_at = answer_generated_at

    def to_dict(self) -> Dict:
        """Convert Person object to dictionary for database storage"""
        data = {
            'query': self.query,
            'basic_info': self.basic_info,
            'social_profiles': self.social_profiles,
            'photos': self.photos,
            'notable_mentions': self.notable_mentions,
            'raw_sources': self.raw_sources
        }

        if self.id:
            data['id'] = self.id
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        if self.answer:
            data['answer'] = self.answer
        if self.related_questions:
            data['related_questions'] = self.related_questions
        if self.answer_generated_at:
            data['answer_generated_at'] = self.answer_generated_at.isoformat()

        return data

    def to_response(self) -> Dict:
        """Convert Person object to API response format"""
        response = {
            'personId': self.id,
            'query': self.query.split('::')[0] if self.query else '',
            'basic_info': self.basic_info,
            'social_profiles': self.social_profiles,
            'photos': self.photos,
            'notable_mentions': self.notable_mentions,
            'raw_sources': self.raw_sources
        }

        if self.answer:
            response['answer'] = self.answer
        if self.related_questions:
            response['related_questions'] = self.related_questions
        if self.answer_generated_at:
            response['answer_generated_at'] = self.answer_generated_at.isoformat() if isinstance(self.answer_generated_at, datetime) else self.answer_generated_at

        return response

    @staticmethod
    def from_dict(data: Dict) -> 'Person':
        """Create Person object from dictionary"""
        created_at = None
        if 'created_at' in data and data['created_at']:
            if isinstance(data['created_at'], str):
                created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
            else:
                created_at = data['created_at']

        updated_at = None
        if 'updated_at' in data and data['updated_at']:
            if isinstance(data['updated_at'], str):
                updated_at = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
            else:
                updated_at = data['updated_at']

        answer_generated_at = None
        if 'answer_generated_at' in data and data['answer_generated_at']:
            if isinstance(data['answer_generated_at'], str):
                answer_generated_at = datetime.fromisoformat(data['answer_generated_at'].replace('Z', '+00:00'))
            else:
                answer_generated_at = data['answer_generated_at']

        return Person(
            query=data.get('query', ''),
            basic_info=data.get('basic_info'),
            social_profiles=data.get('social_profiles'),
            photos=data.get('photos'),
            notable_mentions=data.get('notable_mentions'),
            raw_sources=data.get('raw_sources'),
            person_id=data.get('id'),
            created_at=created_at,
            updated_at=updated_at,
            answer=data.get('answer'),
            related_questions=data.get('related_questions'),
            answer_generated_at=answer_generated_at
        )
