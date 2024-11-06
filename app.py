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
from analyze import analyze_manager

# Настройка логирования
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')
compress = Compress(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# [Оставьте здесь все константы BACKGROUNDS и SURVEY_QUESTIONS как есть]

# Проверка переменных окружения
required_env_vars = [
    'OPENAI_API_KEY',
    'STACKHERO_POSTGRESQL_ADMIN_PASSWORD',
    'STACKHERO_POSTGRESQL_HOST',
    'STACKHERO_POSTGRESQL_PORT'
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")

openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    logger.warning("OpenAI API key not found")

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

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

# [Оставьте здесь функции get_file_hash и get_versioned_filename как есть]

@app.context_processor
def utility_processor():
    """Add utility functions to template context"""
    def get_random_background():
        return random.choice(BACKGROUNDS)
    return {
        'year': datetime.now().year,
        'get_random_background': get_random_background
    }

# [Оставьте здесь все маршруты index, questions, chatgpt, process_voice, thank_you, privacy_policy как есть]

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
        logger.info("Attempting database connection")
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            flash("Ошибка подключения к базе данных", "error")
            return redirect(url_for('index'))

        with conn.cursor() as cur:
            # Создаем индексы
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_responses_level ON responses(level);
                CREATE INDEX IF NOT EXISTS idx_responses_timestamp ON responses(timestamp);
            """)
            
            # Общая статистика
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

            # Статистика по интересам
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

            # Данные об опыте
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

        # Анализ тем
        analysis = analyze_manager.generate_topic_analysis()
        logger.info("Topic analysis generated")

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
