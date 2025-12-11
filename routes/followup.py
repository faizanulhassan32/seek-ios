from flask import Blueprint, request, jsonify
from db.supabase_client import get_supabase_client
from services.followup_service import get_followup_service
from utils.logger import setup_logger

logger = setup_logger('followup_route')

followup_bp = Blueprint('followup', __name__)


@followup_bp.route('/followup', methods=['POST'])
def ask_followup():
    """
    Generate a fast, focused follow-up answer about a person

    Request body:
        {
            "person_id": "uuid",
            "question": "What was his first film cameo?"
        }

    Response:
        {
            "question": "What was his first film cameo?",
            "answer": "His first film cameo was in...",
            "photos": [...],
            "sources": [...],
            "relatedQuestions": [...]
        }
    """
    try:
        # Validate request
        data = request.get_json()
        if not data or 'person_id' not in data or 'question' not in data:
            return jsonify({'error': 'person_id and question parameters are required'}), 400

        person_id = data['person_id']
        question = data['question'].strip()

        if not question:
            return jsonify({'error': 'question cannot be empty'}), 400

        logger.info(f"Received follow-up question for person {person_id}: {question}")

        # Get person from database (reuse existing data - no new scraping)
        supabase_client = get_supabase_client()
        person_data = supabase_client.get_person(person_id)

        if not person_data:
            logger.error(f"Person not found: {person_id}")
            return jsonify({'error': 'Person not found'}), 404

        # Generate follow-up answer using lightweight service
        followup_service = get_followup_service()
        result = followup_service.generate_followup_answer(person_data, question)

        logger.info(f"Successfully generated follow-up answer for: {question}")

        # Return response in format matching frontend expectations
        return jsonify({
            'question': result['question'],
            'answer': result['answer'],
            'photos': result['photos'],
            'sources': result['sources'],
            'relatedQuestions': result.get('related_questions', [])
        }), 200

    except Exception as e:
        logger.error(f"Error in followup endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500
