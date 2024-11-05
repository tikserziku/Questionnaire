import os
import sys
import logging
from flask import Flask, render_template, request, redirect, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import openai
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Проверка наличия OpenAI API ключа
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    logger.error("Ошибка: переменная окружения OPENAI_API_KEY не установлена.")
    sys.exit(1)
else:
    openai.api_key = OPENAI_API_KEY

# Настройка ограничения запросов
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

def get_db_connection():
    # Получение данных для подключения к базе данных из переменных окружения Stackhero
    host = os.getenv('STACKHERO_POSTGRESQL_HOST')
    port = os.getenv('STACKHERO_POSTGRESQL_PORT', '5432')
    dbname = os.getenv('STACKHERO_POSTGRESQL_DATABASE')
    user = os.getenv('STACKHERO_POSTGRESQL_ADMIN_LOGIN')
    password = os.getenv('STACKHERO_POSTGRESQL_ADMIN_PASSWORD')
    sslmode = 'require'

    if not all([host, port, dbname, user, password]):
        logger.error("Переменные окружения для подключения к базе данных не установлены правильно.")
        raise Exception("Переменные окружения для подключения к базе данных не установлены правильно.")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            sslmode=sslmode
        )
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        raise e

# Главная страница
@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            level = request.form['level']
            return redirect(f'/questions/{level}')
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Ошибка на главной странице: {e}")
        return "Произошла ошибка на сервере.", 500

# Страница с вопросами
@app.route('/questions/<level>', methods=['GET', 'POST'])
def questions(level):
    try:
        if request.method == 'POST':
            data = dict(request.form)
            data['level'] = level
            data['timestamp'] = datetime.now()
            data['voice_question'] = request.form.get('voice_question')
            data['chatgpt_questions'] = request.form.get('chatgpt_questions')
            save_to_db(data)
            return redirect('/thank_you')
        return render_template('questions.html', level=level)
    except Exception as e:
        logger.error(f"Ошибка на странице вопросов: {e}")
        return "Произошла ошибка на сервере.", 500

# Страница благодарности
@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')

# Страница политики конфиденциальности
@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

# Обработка запросов к ChatGPT для помощи в формулировке вопросов
@app.route('/chatgpt', methods=['POST'])
@limiter.limit("5 per minute")
def chatgpt():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'reply': 'Сообщение не должно быть пустым.'}), 400
    try:
        response = openai.Completion.create(
            engine='text-davinci-003',
            prompt=user_message,
            max_tokens=150,
            n=1,
            stop=None,
            temperature=0.7,
        )
        bot_reply = response.choices[0].text.strip()
        return jsonify({'reply': bot_reply})
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenAI API: {e}")
        return jsonify({'reply': 'Извините, произошла ошибка при обработке вашего запроса.'}), 500

# Обработка голосового ввода и корректировка через ChatGPT
@app.route('/process_voice', methods=['POST'])
@limiter.limit("5 per minute")
def process_voice():
    voice_input = request.json.get('voice_input')
    if not voice_input:
        return jsonify({'corrected_question': 'Голосовой ввод не должен быть пустым.'}), 400
    prompt = f"Пожалуйста, откорректируйте следующий вопрос, сделав его ясным и понятным:\n\n{voice_input}"
    try:
        response = openai.Completion.create(
            engine='text-davinci-003',
            prompt=prompt,
            max_tokens=150,
            n=1,
            stop=None,
            temperature=0.5,
        )
        corrected_question = response.choices[0].text.strip()
        return jsonify({'corrected_question': corrected_question})
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenAI API: {e}")
        return jsonify({'corrected_question': 'Извините, произошла ошибка при обработке вашего запроса.'}), 500

def save_to_db(data):
    try:
        # Анонимизация данных, удаление чувствительной информации
        sensitive_fields = ['email', 'phone']
        for field in sensitive_fields:
            if field in data:
                data[field] = 'REDACTED'
        conn = get_db_connection()
        if conn is None:
            logger.error("Не удалось установить соединение с базой данных.")
            return
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS responses (
                        id SERIAL PRIMARY KEY,
                        level TEXT,
                        data TEXT,
                        voice_question TEXT,
                        chatgpt_questions TEXT,
                        timestamp TIMESTAMP
                    )''')
        c.execute('INSERT INTO responses (level, data, voice_question, chatgpt_questions, timestamp) VALUES (%s, %s, %s, %s, %s)', 
                  (data.get('level'), str(data), data.get('voice_question'), data.get('chatgpt_questions'), data.get('timestamp')))
        conn.commit()
        c.close()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в базу: {e}")

if __name__ == '__main__':
    try:
        app.run(debug=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {e}")
        sys.exit(1)
