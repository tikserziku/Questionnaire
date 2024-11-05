import os
import sys
import logging
import json
from flask import Flask, render_template, request, redirect, jsonify, flash, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import openai
import psycopg2
from datetime import datetime
from functools import wraps
import bleach
from werkzeug.security import generate_password_hash, check_password_hash
from whitenoise import WhiteNoise

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Инициализация Flask приложения
app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='static/')
app.secret_key = os.urandom(24)

# Конфигурация OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    logger.error("OpenAI API key not found")
    sys.exit(1)

# Настройка лимитера запросов
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

def get_db_connection():
    """Создание подключения к базе данных"""
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user='postgres',
            password=os.environ['STACKHERO_POSTGRESQL_ADMIN_PASSWORD'],
            host=os.environ['STACKHERO_POSTGRESQL_HOST'],
            port=os.environ['STACKHERO_POSTGRESQL_PORT']
        )
        logger.info("Database connection established successfully")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def init_db():
    """Инициализация базы данных"""
    try:
        conn = get_db_connection()
        if conn is None:
            return

        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS responses (
                    id SERIAL PRIMARY KEY,
                    level TEXT NOT NULL,
                    data JSONB NOT NULL,
                    voice_question TEXT,
                    chatgpt_questions TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    ip_address TEXT
                )
            ''')
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.close()

def sanitize_input(data):
    """Очистка пользовательского ввода"""
    if isinstance(data, str):
        return bleach.clean(data)
    elif isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(x) for x in data]
    return data

@app.before_first_request
def setup():
    """Настройка перед первым запросом"""
    init_db()

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/questions/<level>', methods=['GET', 'POST'])
def questions(level):
    """Обработка вопросов"""
    if level not in ['beginner', 'advanced']:
        flash('Invalid level specified', 'error')
        return redirect('/')

    if request.method == 'POST':
        try:
            form_data = sanitize_input(request.form.to_dict())
            form_data.update({
                'level': level,
                'timestamp': datetime.utcnow().isoformat(),
                'ip_address': request.remote_addr
            })
            save_to_db(form_data)
            return redirect('/thank_you')
        except Exception as e:
            logger.error(f"Error processing form: {e}")
            flash("An error occurred. Please try again.", "error")
            return redirect('/questions/' + level)

    questions_data = {
        'beginner': [
            {"text": "Что вы ожидаете узнать на этом курсе?", "name": "expectations"},
            {"text": "Имеете ли вы опыт в программировании?", "name": "programming_experience"}
        ],
        'advanced': [
            {"text": "Какой у вас опыт работы с ИИ?", "name": "ai_experience"},
            {"text": "С какими инструментами вы работали?", "name": "tools"}
        ]
    }

    return render_template('questions.html', 
                         level=level, 
                         questions=questions_data[level])

@app.route('/chatgpt', methods=['POST'])
@limiter.limit("5 per minute")
def chatgpt():
    """Обработка запросов к ChatGPT"""
    try:
        message = sanitize_input(request.json.get('message', ''))
        if not message:
            return jsonify({'error': 'Empty message'}), 400

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": message}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        return jsonify({'reply': response.choices[0].message.content})
    except Exception as e:
        logger.error(f"ChatGPT API error: {e}")
        return jsonify({'error': 'Service temporarily unavailable'}), 503

@app.route('/process_voice', methods=['POST'])
@limiter.limit("5 per minute")
def process_voice():
    """Обработка голосового ввода"""
    try:
        voice_input = sanitize_input(request.json.get('voice_input', ''))
        if not voice_input:
            return jsonify({'error': 'Empty voice input'}), 400

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Please correct and clarify the following question:"},
                {"role": "user", "content": voice_input}
            ],
            max_tokens=150,
            temperature=0.5
        )
        
        return jsonify({'corrected_question': response.choices[0].message.content})
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        return jsonify({'error': 'Service temporarily unavailable'}), 503

@app.route('/thank_you')
def thank_you():
    """Страница благодарности"""
    return render_template('thank_you.html')

@app.route('/privacy_policy')
def privacy_policy():
    """Страница политики конфиденциальности"""
    return render_template('privacy_policy.html')

def save_to_db(data):
    """Сохранение данных в базу"""
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            raise Exception("Could not connect to database")

        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO responses (level, data, voice_question, chatgpt_questions, timestamp, ip_address) '
                'VALUES (%s, %s::jsonb, %s, %s, %s, %s)',
                (
                    data['level'],
                    json.dumps(data),
                    data.get('voice_question'),
                    data.get('chatgpt_questions'),
                    data['timestamp'],
                    data.get('ip_address')
                )
            )
            conn.commit()
            logger.info(f"Data saved successfully for level: {data['level']}")
    except Exception as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

@app.errorhandler(404)
def not_found_error(error):
    """Обработка ошибки 404"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Обработка ошибки 500"""
    logger.error(f"Internal server error: {error}")
    return render_template('500.html'), 500

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
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
