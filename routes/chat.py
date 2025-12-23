import os
import json
from flask import Blueprint, request, jsonify
from typing import Dict

from anthropic import Anthropic

from db.supabase_client import get_supabase_client
from models.chat import Chat, ChatMessage
from utils.logger import setup_logger

logger = setup_logger('chat_route')

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat', methods=['POST'])
def chat_with_person():
    """
    Chat with AI about a person using their aggregated data as context

    Request body:
        {
            "personId": "uuid",
            "messages": [
                {"role": "user", "content": "Tell me about this person"}
            ]
        }

    Response:
        {
            "reply": "AI response here..."
        }
    """
    try:
        # Validate request
        data = request.get_json()
        if not data or 'personId' not in data or 'messages' not in data:
            return jsonify({'error': 'personId and messages are required'}), 400

        person_id = data['personId']
        messages = data['messages']

        if not messages or len(messages) == 0:
            return jsonify({'error': 'At least one message is required'}), 400

        logger.info(f"Received chat request for person: {person_id}")

        # Initialize services
        supabase_client = get_supabase_client()
        anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        # Retrieve person data from database
        logger.info("Retrieving person data from database...")
        person_data = supabase_client.get_person(person_id)

        if not person_data:
            return jsonify({'error': 'Person not found'}), 404

        # Build context from person data
        context = build_person_context(person_data)

        # Get or create chat session
        existing_chats = supabase_client.get_chats_by_person(person_id)

        chat = None
        if existing_chats and len(existing_chats) > 0:
            # Use the most recent chat
            chat = Chat.from_dict(existing_chats[0])
            logger.info(f"Using existing chat: {chat.id}")
        else:
            # Create new chat
            chat = Chat(person_id=person_id)
            logger.info("Creating new chat session")

        # Add new user message to chat
        last_message = messages[-1]
        chat.add_message(role=last_message['role'], content=last_message['content'])

        # Build system prompt
        system_prompt = f"""
            You are an AI assistant helping users understand information about a person.
            You have access to the following information about this person:
            {context}
            Use this information to answer the user's questions accurately. If the user asks about something not in the data, acknowledge that you don't have that information. Support follow-up queries like "show me only Instagram data" or "summarize their professional background".
        """

        # Build messages for Claude API
        claude_messages = []
        for msg in chat.messages:
            claude_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Call Claude API with tool
        logger.info("Calling Claude for chat response...")
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            temperature=0.7,
            system=system_prompt,
            messages=claude_messages,
            tools=[{
                "name": "provide_answer",
                "description": "Provide the answer to the user's question about the person",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "answer": {
                            "type": "string",
                            "description": "The AI's response to the user's question"
                        }
                    },
                    "required": ["answer"]
                }
            }],
            tool_choice={
                "type": "tool",
                "name": "provide_answer"
            }
        )

        logger.info("Claude response received")

        # Extract AI reply from tool use
        tool_use_block = response.content[0]
        ai_reply = tool_use_block.input["answer"]

        # Add AI response to chat
        chat.add_message(role='assistant', content=ai_reply)

        # Save or update chat in database
        if chat.id:
            # Update existing chat
            supabase_client.update_chat(chat.id, [msg.to_dict() for msg in chat.messages])
        else:
            # Create new chat
            stored_chat = supabase_client.create_chat(chat.to_dict())
            if stored_chat:
                chat.id = stored_chat['id']

        logger.info("Chat response generated successfully")

        # Return response
        return jsonify({
            'reply': ai_reply,
            'chatId': chat.id
        }), 200

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

def build_person_context(person_data: Dict) -> str:
    """
    Build a formatted context string from person data for the AI

    Args:
        person_data: Person data from database

    Returns:
        Formatted context string
    """
    context_parts = []

    # Basic Info
    basic_info = person_data.get('basic_info', {})
    if basic_info:
        context_parts.append("BASIC INFORMATION:")
        context_parts.append(json.dumps(basic_info, indent=2))
        context_parts.append("")

    # Social Profiles
    social_profiles = person_data.get('social_profiles', [])
    if social_profiles:
        context_parts.append("SOCIAL MEDIA PROFILES:")
        for profile in social_profiles:
            platform = profile.get('platform', 'Unknown')
            context_parts.append(f"- {platform.upper()}:")
            context_parts.append(f"  {json.dumps(profile, indent=2)}")
        context_parts.append("")

    # Photos
    photos = person_data.get('photos', [])
    if photos:
        context_parts.append(f"PHOTOS: {len(photos)} photos available")
        context_parts.append("")

    # Notable Mentions
    notable_mentions = person_data.get('notable_mentions', [])
    if notable_mentions:
        context_parts.append("NOTABLE MENTIONS:")
        for mention in notable_mentions:
            if isinstance(mention, dict):
                context_parts.append(f"- {json.dumps(mention)}")
            else:
                context_parts.append(f"- {mention}")
        context_parts.append("")

    # Raw Sources
    raw_sources = person_data.get('raw_sources', [])
    if raw_sources:
        context_parts.append(f"DATA SOURCES: Information gathered from {len(raw_sources)} sources")

    return "\n".join(context_parts)
