import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, jsonify
import openai
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

# Настройка OpenAI API
openai.api_key = os.getenv('OPENAI_API_KEY')

# Настройка ограничения запросов
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

# Главная страница
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        level = request.form['level']
        return redirect(f'/questions/{level}')
    return render_template('index.html')

# Страница с вопросами
@app.route('/questions/<level>', methods=['GET', 'POST'])
def questions(level):
    if request.method == 'POST':
        data = dict(request.form)
        data['level'] = level
        data['timestamp'] = datetime.now()
        data['voice_question'] = request.form.get('voice_question')
        data['chatgpt_questions'] = request.form.get('chatgpt_questions')
        save_to_db(data)
        return redirect('/thank_you')
    return render_template('questions.html', level=level)

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
    user_message = request.json['message']
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
    except openai.error.OpenAIError as e:
        print(f"Ошибка OpenAI API: {e}")
        return jsonify({'reply': 'Извините, произошла ошибка при обработке вашего запроса.'}), 500

# Обработка голосового ввода и корректировка через ChatGPT
@app.route('/process_voice', methods=['POST'])
@limiter.limit("5 per minute")
def process_voice():
    voice_input = request.json['voice_input']
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
    except openai.error.OpenAIError as e:
        print(f"Ошибка OpenAI API: {e}")
        return jsonify({'corrected_question': 'Извините, произошла ошибка при обработке вашего запроса.'}), 500

def save_to_db(data):
    # Анонимизация данных, удаление чувствительной информации
    sensitive_fields = ['email', 'phone']
    for field in sensitive_fields:
        if field in data:
            data[field] = 'REDACTED'
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT,
                    data TEXT,
                    voice_question TEXT,
                    chatgpt_questions TEXT,
                    timestamp DATETIME
                )''')
    c.execute('INSERT INTO responses (level, data, voice_question, chatgpt_questions, timestamp) VALUES (?, ?, ?, ?, ?)', 
              (data.get('level'), str(data), data.get('voice_question'), data.get('chatgpt_questions'), data.get('timestamp')))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    app.run(debug=True)
