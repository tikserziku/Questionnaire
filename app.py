import os
import sys
import logging
import json
import random
from flask import Flask, render_template, request, redirect, jsonify, flash, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import openai
import psycopg2
from datetime import datetime
from whitenoise import WhiteNoise

# Настройка логирования
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')

# Настройка секретного ключа
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Список доступных фонов
BACKGROUNDS = [
    'background01.png',
    'background02.png',
    'background03.png',
    'background04.png'
]

# Конфигурация вопросов
SURVEY_QUESTIONS = {
    'beginner': [
        {
            "id": "expectations",
            "text": "Что вы ожидаете получить от курса по ИИ?",
            "type": "textarea",
            "placeholder": "Опишите ваши цели и ожидания...",
            "required": True
        },
        {
            "id": "experience",
            "text": "Есть ли у вас опыт программирования? На каком языке?",
            "type": "textarea",
            "placeholder": "Расскажите о вашем опыте...",
            "required": True
        },
        {
            "id": "learning_style",
            "text": "Как вы предпочитаете учиться?",
            "type": "checkbox",
            "options": [
                "Практические задания",
                "Теоретические материалы",
                "Видео-уроки",
                "Работа в группе",
                "Индивидуальные консультации"
            ],
            "required": True
        },
        {
            "id": "interests",
            "text": "Какие области ИИ вас интересуют больше всего?",
            "type": "checkbox",
            "options": [
                "Машинное обучение",
                "Нейронные сети",
                "Обработка естественного языка",
                "Компьютерное зрение",
                "Чат-боты",
                "Автоматизация процессов"
            ],
            "required": True
        }
    ],
    'advanced': [
        {
            "id": "ai_experience",
            "text": "Опишите ваш опыт работы с ИИ",
            "type": "textarea",
            "placeholder": "Проекты, технологии, фреймворки...",
            "required": True
        },
        {
            "id": "challenges",
            "text": "С какими сложностями вы сталкивались при работе с ИИ?",
            "type": "textarea",
            "placeholder": "Опишите проблемы и как вы их решали...",
            "required": True
        },
        {
            "id": "tools",
            "text": "Какие инструменты ИИ вы использовали?",
            "type": "checkbox",
            "options": [
                "TensorFlow",
                "PyTorch",
                "Scikit-learn",
                "OpenAI API",
                "Hugging Face",
                "Keras",
                "Другое (укажите в комментарии)"
            ],
            "required": True
        },
        {
            "id": "interests",
            "text": "Какие продвинутые темы вас интересуют?",
            "type": "checkbox",
            "options": [
                "Глубокое обучение",
                "Трансформеры",
                "Reinforcement Learning",
                "GANs",
                "MLOps",
                "Оптимизация моделей",
                "Другое (укажите в комментарии)"
            ],
            "required": True
        }
    ]
}

# Проверка наличия необходимых переменных окружения
required_env_vars = [
    'OPENAI_API_KEY',
    'STACKHERO_POSTGRESQL_ADMIN_PASSWORD',
    'STACKHERO_POSTGRESQL_HOST',
    'STACKHERO_POSTGRESQL_PORT'
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")

# Настройка OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    logger.warning("OpenAI API key not found")

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
        conn = psycopg2.connect(
            dbname='postgres',
            user='postgres',
            password=os.environ['STACKHERO_POSTGRESQL_ADMIN_PASSWORD'],
            host=os.environ['STACKHERO_POSTGRESQL_HOST'],
            port=os.environ['STACKHERO_POSTGRESQL_PORT'],
            connect_timeout=5
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

@app.context_processor
def utility_processor():
    """Add utility functions to template context"""
    def get_random_background():
        return random.choice(BACKGROUNDS)
    return {
        'year': datetime.now().year,
        'get_random_background': get_random_background
    }

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main page route"""
    try:
        if request.method == 'POST':
            level = request.form.get('level')
            if level in ['beginner', 'advanced']:
                return redirect(url_for('questions', level=level))
            else:
                flash('Пожалуйста, выберите уровень', 'error')
                return redirect(url_for('index'))
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error on index page: {e}")
        return "Internal Server Error", 500

@app.route('/questions/<level>', methods=['GET', 'POST'])
def questions(level):
    """Survey questions route"""
    if level not in ['beginner', 'advanced']:
        flash('Неверный уровень', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            form_data = request.form.to_dict()
            form_data['level'] = level
            form_data['timestamp'] = datetime.utcnow().isoformat()
            form_data['ip_address'] = request.remote_addr
            
            questions = SURVEY_QUESTIONS[level]
            required_fields = [q['id'] for q in questions if q.get('required')]
            
            missing_fields = [field for field in required_fields if not form_data.get(field)]
            if missing_fields:
                flash('Пожалуйста, заполните все обязательные поля', 'error')
                return render_template('questions.html', 
                                    level=level, 
                                    questions=questions)

            save_to_db(form_data)
            return redirect(url_for('thank_you'))
            
        except Exception as e:
            logger.error(f"Error processing form: {e}")
            flash("Произошла ошибка при сохранении данных. Попробуйте еще раз.", "error")
            return redirect(url_for('questions', level=level))

    return render_template(
        'questions.html',
        level=level,
        questions=SURVEY_QUESTIONS[level]
    )

@app.route('/chatgpt', methods=['POST'])
@limiter.limit("5 per minute")
def chatgpt():
    """ChatGPT API endpoint"""
    if not openai.api_key:
        return jsonify({'error': 'OpenAI API not configured'}), 503

    try:
        message = request.json.get('message', '')
        if not message:
            return jsonify({'error': 'Empty message'}), 400

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for an AI course survey."},
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
    """Voice processing endpoint"""
    if not openai.api_key:
        return jsonify({'error': 'OpenAI API not configured'}), 503

    try:
        voice_input = request.json.get('voice_input', '')
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
        
        return jsonify({'processed_question': response.choices[0].message.content})
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        return jsonify({'error': 'Service temporarily unavailable'}), 503

@app.route('/thank_you')
def thank_you():
    """Thank you page route"""
    return render_template('thank_you.html')

@app.route('/privacy_policy')
def privacy_policy():
    """Privacy policy page route"""
    return render_template('privacy_policy.html')

def save_to_db(data):
    """Save form data to database"""
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            raise Exception("Could not connect to database")

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
    """404 error handler"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    logger.error(f"Internal server error: {error}")
    return render_template('500.html'), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    """Rate limit error handler"""
    return jsonify(error="Слишком много запросов. Пожалуйста, подождите немного."), 429

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
