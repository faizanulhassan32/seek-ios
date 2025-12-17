from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

from routes.search import search_bp
from routes.chat import chat_bp
from routes.answer import answer_bp
from routes.followup import followup_bp
from routes.candidates import candidates_bp
from routes.auth import auth_bp
from utils.logger import setup_logger
from utils.cleanup_scheduler import start_cleanup_scheduler

load_dotenv()

app = Flask(__name__)
CORS(app)

# Start background cleanup scheduler for reference photos
cleanup_scheduler = start_cleanup_scheduler()

logger = setup_logger()

app.register_blueprint(search_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(answer_bp)
app.register_blueprint(followup_bp)
app.register_blueprint(candidates_bp)
app.register_blueprint(auth_bp)

@app.route('/health', methods=['GET'])
def health_check():
    return {'status': 'healthy'}, 200
    
# Temporary route map inspector to debug routing in deployed envs
@app.route('/debug/routes', methods=['GET'])
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'rule': str(rule),
            'endpoint': rule.endpoint,
            'methods': sorted(list(rule.methods - {'HEAD', 'OPTIONS'}))
        })
    return {'routes': routes}, 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
