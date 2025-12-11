from typing import Dict, List, Optional
from datetime import datetime

class ChatMessage:
    """Represents a single message in a conversation"""

    def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None):
        self.role = role  # 'user' or 'assistant'
        self.content = content
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> Dict:
        """Convert message to dictionary"""
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat()
        }

    @staticmethod
    def from_dict(data: Dict) -> 'ChatMessage':
        """Create ChatMessage from dictionary"""
        timestamp = None
        if 'timestamp' in data and data['timestamp']:
            if isinstance(data['timestamp'], str):
                timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            else:
                timestamp = data['timestamp']

        return ChatMessage(
            role=data.get('role', 'user'),
            content=data.get('content', ''),
            timestamp=timestamp
        )


class Chat:
    """
    Chat model representing a conversation about a person
    Matches the Supabase schema and Swift model structure
    """

    def __init__(
        self,
        person_id: str,
        messages: Optional[List[ChatMessage]] = None,
        chat_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = chat_id
        self.person_id = person_id
        self.messages = messages or []
        self.created_at = created_at
        self.updated_at = updated_at

    def add_message(self, role: str, content: str):
        """Add a new message to the conversation"""
        message = ChatMessage(role=role, content=content)
        self.messages.append(message)

    def to_dict(self) -> Dict:
        """Convert Chat object to dictionary for database storage"""
        data = {
            'person_id': self.person_id,
            'messages': [msg.to_dict() for msg in self.messages]
        }

        if self.id:
            data['id'] = self.id
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()

        return data

    def to_response(self) -> Dict:
        """Convert Chat object to API response format"""
        return {
            'chatId': self.id,
            'personId': self.person_id,
            'messages': [msg.to_dict() for msg in self.messages]
        }

    def get_messages_for_openai(self) -> List[Dict]:
        """Get messages in OpenAI API format"""
        return [
            {'role': msg.role, 'content': msg.content}
            for msg in self.messages
        ]

    @staticmethod
    def from_dict(data: Dict) -> 'Chat':
        """Create Chat object from dictionary"""
        messages = []
        if 'messages' in data and data['messages']:
            messages = [ChatMessage.from_dict(msg) for msg in data['messages']]

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

        return Chat(
            person_id=data.get('person_id', ''),
            messages=messages,
            chat_id=data.get('id'),
            created_at=created_at,
            updated_at=updated_at
        )
