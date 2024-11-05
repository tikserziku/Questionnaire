import os
import sys
import logging
from flask import Flask, render_template, request, redirect, jsonify, flash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import openai
import psycopg2
from datetime import datetime
from whitenoise import WhiteNoise
from datetime import datetime

# Настройка логирования
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')

# Настройка секретного ключа
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Проверка наличия необходимых переменных окружения
required_env_vars = [
    'OPENAI_API_KEY',
    'STACKHERO_POSTGRESQL_ADMIN_PASSWORD',
    'STACKHERO_POSTGRESQL_HOST',
    'STACKHERO_POSTGRESQL_PORT'
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    # В продакшене лучше продолжить работу без отсутствующих сервисов
    # sys.exit(1)

# Настройка OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Настройка лимитера
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

def get_db_connection():
    """Create database connection with error handling"""
    try:
        if not all([
            os.getenv('STACKHERO_POSTGRESQL_ADMIN_PASSWORD'),
            os.getenv('STACKHERO_POSTGRESQL_HOST'),
            os.getenv('STACKHERO_POSTGRESQL_PORT')
        ]):
            logger.warning("Database credentials not found in environment")
            return None

        conn = psycopg2.connect(
            dbname='postgres',
            user='postgres',
            password=os.environ['STACKHERO_POSTGRESQL_ADMIN_PASSWORD'],
            host=os.environ['STACKHERO_POSTGRESQL_HOST'],
            port=os.environ['STACKHERO_POSTGRESQL_PORT']
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None
@app.context_processor
def utility_processor():
    return {'year': datetime.now().year}

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
        return "Internal Server Error", 500

# Настройка CORS и безопасности
@app.after_request
def after_request(response):
    """Добавление заголовков безопасности"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    response.headers.add('X-Frame-Options', 'DENY')
    response.headers.add('X-Content-Type-Options', 'nosniff')
    response.headers.add('X-XSS-Protection', '1; mode=block')
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
