import os
import sys
import logging
from flask import Flask, render_template, request, redirect, jsonify, flash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import openai
import psycopg2
from urllib.parse import urlparse
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "generate_a_strong_random_key_here") #  IMPORTANT!  Generate a secure random key for production

openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logger.error("Ошибка: переменная окружения OPENAI_API_KEY не установлена.")
    sys.exit(1)


limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

def get_db_connection():
    url = urlparse(os.environ['DATABASE_URL'])

    conn = psycopg2.connect(
        dbname=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    return conn



@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            level = request.form['level']
            return redirect(f'/questions/{level}')
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Ошибка на главной странице: {e}")
        flash("Произошла ошибка на сервере. Попробуйте позже.", "error")  # User-friendly error message
        return render_template('index.html'), 500 # Return the index template with the error message


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

        # Sample Questions: Adapt these to your actual questions
        beginner_questions = [
            {"text": "Что вы ожидаете узнать на этом курсе?", "name": "expectations", "type": "text"},
            {"text": "Имеете ли вы опыт в программировании? Если да, то на каких языках?", "name": "programming_experience", "type": "text"}
        ]

        advanced_questions = [
             {"text": "Какой у вас опыт работы с искусственным интеллектом?", "name": "ai_experience", "type": "text"},
            {"text": "С какими инструментами и фреймворками вы работали?", "name": "tools", "type": "text"}
        ]
        questions = beginner_questions if level == 'beginner' else advanced_questions
        return render_template('questions.html', level=level, questions=questions)

    except Exception as e:
        logger.error(f"Ошибка на странице вопросов: {e}")
        flash("Произошла ошибка на сервере. Попробуйте позже.", "error")  # User-friendly message
        return redirect('/'), 500  # Redirect to the main page on error



@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')


@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')


@app.route('/chatgpt', methods=['POST'])
@limiter.limit("5 per minute")
def chatgpt():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'reply': 'Сообщение не должно быть пустым.'}), 400
    try:
        response = openai.Completion.create(
            engine='text-davinci-003',  # Or a suitable engine
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
        conn = get_db_connection()
        if conn is None:
            flash("Ошибка: Не удалось подключиться к базе данных.", "error")
            return redirect('/') # redirect after the error
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
        flash("Ошибка: Возникла проблема при сохранении вашего ответа.", "error")
        return redirect('/') # Redirect after the database error

if __name__ == '__main__':
    try:
        app.run(debug=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {e}")
        sys.exit(1)
