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

load_dotenv()

app = Flask(__name__)
CORS(app)

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

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
