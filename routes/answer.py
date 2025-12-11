from flask import Blueprint, request, jsonify
from db.supabase_client import get_supabase_client
from services.answer_service import get_answer_service
from utils.logger import setup_logger

logger = setup_logger('answer_route')

answer_bp = Blueprint('answer', __name__)


@answer_bp.route('/answer/generate', methods=['POST'])
def generate_answer():
    """
    Generate AI answer for a person

    Request body:
        {
            "personId": "uuid"
        }

    Response:
        {
            "personId": "uuid",
            "answer": "AI-generated biographical text...",
            "relatedQuestions": ["Q1", "Q2", ...],
            "answerGeneratedAt": "ISO timestamp"
        }
    """
    try:
        # Validate request
        data = request.get_json()
        if not data or 'person_id' not in data:
            return jsonify({'error': 'person_id parameter is required'}), 400

        person_id = data['person_id']
        logger.info(f"Received answer generation request for person ID: {person_id}")

        # Get person from database
        supabase_client = get_supabase_client()
        person_data = supabase_client.get_person(person_id)

        if not person_data:
            logger.error(f"Person not found: {person_id}")
            return jsonify({'error': 'Person not found'}), 404

        # Check if answer already exists
        if person_data.get('answer'):
            logger.info(f"Answer already exists for person: {person_id}")
            return jsonify({
                'personId': person_id,
                'answer': person_data['answer'],
                'relatedQuestions': person_data.get('related_questions', []),
                'answerGeneratedAt': person_data.get('answer_generated_at')
            }), 200

        # Generate answer
        answer_service = get_answer_service()

        logger.info("Generating answer...")
        answer = answer_service.generate_answer(person_data)

        logger.info("Generating related questions...")
        related_questions = answer_service.generate_related_questions(
            person_data.get('query', ''),
            person_data
        )

        # Update person in database
        from datetime import datetime
        updates = {
            'answer': answer,
            'related_questions': related_questions,
            'answer_generated_at': datetime.utcnow().isoformat()
        }

        updated_person = supabase_client.update_person(person_id, updates)

        if not updated_person:
            logger.error(f"Failed to update person with answer: {person_id}")
            # Still return the answer even if DB update fails
            return jsonify({
                'personId': person_id,
                'answer': answer,
                'relatedQuestions': related_questions,
                'answerGeneratedAt': updates['answer_generated_at']
            }), 200

        logger.info(f"Successfully generated and stored answer for person: {person_id}")

        return jsonify({
            'personId': person_id,
            'answer': answer,
            'relatedQuestions': related_questions,
            'answerGeneratedAt': updates['answer_generated_at']
        }), 200

    except Exception as e:
        logger.error(f"Error in generate_answer endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


@answer_bp.route('/answer/<person_id>', methods=['GET'])
def get_answer(person_id: str):
    """
    Get existing answer for a person (without generating)

    Response:
        {
            "personId": "uuid",
            "answer": "...",
            "relatedQuestions": [...],
            "answerGeneratedAt": "..."
        }
    """
    try:
        logger.info(f"Fetching answer for person: {person_id}")

        supabase_client = get_supabase_client()
        person_data = supabase_client.get_person(person_id)

        if not person_data:
            return jsonify({'error': 'Person not found'}), 404

        if not person_data.get('answer'):
            return jsonify({'error': 'Answer not generated yet'}), 404

        return jsonify({
            'personId': person_id,
            'answer': person_data['answer'],
            'relatedQuestions': person_data.get('related_questions', []),
            'answerGeneratedAt': person_data.get('answer_generated_at')
        }), 200

    except Exception as e:
        logger.error(f"Error in get_answer endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
