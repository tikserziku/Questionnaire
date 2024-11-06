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
from datetime import datetime, timedelta
from whitenoise import WhiteNoise
from functools import lru_cache
from flask_compress import Compress
import hashlib
from werkzeug.middleware.proxy_fix import ProxyFix
from analyze import analyze_manager  # Добавляем импорт analyze_manager

# Настройка логирования
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')
compress = Compress(app)  # Добавляем компрессию

# Настройка прокси
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

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

# Настройка кэширования
def get_file_hash(filename):
    """Получение хэша файла для версионирования"""
    try:
        hasher = hashlib.md5()
        with open(filename, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()[:8]
    except Exception as e:
        logger.error(f"Error generating file hash: {e}")
        return ""

@lru_cache(maxsize=100)
def get_versioned_filename(filename):
    """Получение версионированного имени файла"""
    try:
        full_path = os.path.join(app.static_folder, filename)
        if os.path.exists(full_path):
            file_hash = get_file_hash(full_path)
            name, ext = os.path.splitext(filename)
            return f"{name}.{file_hash}{ext}"
        return filename
    except Exception as e:
        logger.error(f"Error versioning filename: {e}")
        return filename

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
                {"role": "system", "content": "Ты помощник, который должен ответить на вопрос пользователя. Дай краткий и точный ответ."},
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

@app.route('/analytics')
def analytics():
    """Analytics dashboard route"""
    logger.info("Starting analytics page load")
    conn = None
    try:
        # Логируем попытку подключения к БД
        logger.info("Attempting database connection")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed - get_db_connection returned None")
            flash("Ошибка подключения к базе данных", "error")
            return redirect(url_for('index'))

        logger.info("Database connection successful")
        
        with conn.cursor() as cur:
            logger.info("Executing overall stats query")
            # Создаем необходимые индексы, если их нет
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_responses_level ON responses(level);
                CREATE INDEX IF NOT EXISTS idx_responses_timestamp ON responses(timestamp);
            """)
            
            # Получаем общую статистику
            cur.execute("""
                SELECT 
                    level,
                    COUNT(*) as count,
                    MIN(timestamp) as first_response,
                    MAX(timestamp) as last_response
                FROM responses 
                GROUP BY level
            """)
            overall_stats = cur.fetchall()
            logger.info(f"Retrieved overall stats: {overall_stats}")

            logger.info("Executing topic stats query")
            # Получаем статистику по интересам из JSON данных
            cur.execute("""
                SELECT 
                    jsonb_array_elements_text(
                        CASE 
                            WHEN jsonb_typeof(data->'interests') = 'array' 
                            THEN data->'interests'
                            ELSE '[]'::jsonb 
                        END
                    ) as topic,
                    COUNT(*) as count
                FROM responses
                GROUP BY topic
                ORDER BY count DESC
                LIMIT 10
            """)
            topic_stats = dict(cur.fetchall())
            logger.info(f"Retrieved topic stats: {topic_stats}")

            logger.info("Executing experience data query")
            # Получаем данные об опыте
            cur.execute("""
                SELECT 
                    level,
                    data->>'experience' as exp,
                    data->>'programming_experience' as prog_exp,
                    data->>'ai_experience' as ai_exp
                FROM responses
                ORDER BY timestamp DESC
                LIMIT 10
            """)
            experience_data = cur.fetchall()
            logger.info(f"Retrieved experience data: {experience_data}")

            conn.commit()

        # Получаем данные анализа категорий
        logger.info("Generating topic analysis")
        analysis = analyze_manager.generate_topic_analysis()
        logger.info("Topic analysis generated successfully")

        logger.info("Rendering analytics template")
        return render_template('analytics.html',
                             overall_stats=overall_stats,
                             topic_stats=topic_stats,
                             experience_data=experience_data,
                             analysis=analysis)

    except Exception as e:
        logger.error(f"Error loading analytics: {str(e)}", exc_info=True)
        flash("Ошибка при загрузке аналитики", "error")
        return redirect(url_for('index'))

    finally:
        if conn:
            logger.info("Closing database connection")
            conn.close()

@app.route('/api/topic-analysis')
def topic_analysis():
    """API endpoint for topic analysis data"""
    try:
        analysis = analyze_manager.generate_topic_analysis()
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"Error generating topic analysis: {e}")
        return jsonify({'error': 'Failed to generate analysis'}), 500

@app.route('/api/public-insights')
def public_insights():
    """Public insights page"""
    try:
        analysis = analyze_manager.generate_topic_analysis()
        categorized_responses = analyze_manager.get_categorized_responses()
        return render_template('public_insights.html', 
                             analysis=analysis,
                             responses=categorized_responses)
    except Exception as e:
        logger.error(f"Error loading public insights: {e}")
        return jsonify({'error': 'Failed to load insights'}), 500

def get_db_connection():
    """Создание соединения с базой данных PostgreSQL"""
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

@app.route('/analytics')
def analytics():
    """Analytics dashboard route"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to connect to database")
            flash("Ошибка подключения к базе данных", "error")
            return redirect(url_for('index'))

        with conn.cursor() as cur:
            # Получаем общую статистику
            cur.execute("""
                SELECT 
                    level,
                    COUNT(*) as count,
                    MIN(timestamp) as first_response,
                    MAX(timestamp) as last_response
                FROM responses 
                GROUP BY level
            """)
            overall_stats = cur.fetchall()

            # Получаем статистику по интересам
            cur.execute("""
                SELECT 
                    unnest(string_to_array(data->>'topics', ',')) as topic,
                    COUNT(*) as count
                FROM responses
                GROUP BY topic
                ORDER BY count DESC
                LIMIT 10
            """)
            topic_stats = dict(cur.fetchall())

            # Получаем данные об опыте
            cur.execute("""
                SELECT 
                    level,
                    data->>'experience' as exp,
                    data->>'programming_experience' as prog_exp,
                    data->>'ai_experience' as ai_exp
                FROM responses
                ORDER BY timestamp DESC
                LIMIT 10
            """)
            experience_data = cur.fetchall()

        # Получаем данные анализа категорий
        analysis = analyze_manager.generate_topic_analysis()

        return render_template('analytics.html',
                             overall_stats=overall_stats,
                             topic_stats=topic_stats,
                             experience_data=experience_data,
                             analysis=analysis)

    except Exception as e:
        logger.error(f"Error loading analytics: {e}")
        flash("Ошибка при загрузке аналитики", "error")
        return redirect(url_for('index'))
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
