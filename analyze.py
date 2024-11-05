import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# Получение данных из базы
conn = sqlite3.connect('database.db')
df = pd.read_sql_query('SELECT * FROM responses', conn)
conn.close()

# Преобразование строки в словарь
df['data'] = df['data'].apply(eval)

# Создание DataFrame из словарей
data = pd.json_normalize(df['data'])

# Анализ голосовых вопросов
voice_questions = df['voice_question'].dropna()
print("Голосовые вопросы:")
print(voice_questions)

# Анализ вопросов, сформулированных через ChatGPT
chatgpt_questions = df['chatgpt_questions'].dropna()
print("Вопросы, сформулированные через ChatGPT:")
print(chatgpt_questions)

# Пример анализа интересующих тем
if 'topics' in data.columns:
    topics = data['topics'].value_counts()
    topics.plot(kind='pie', autopct='%1.1f%%')
    plt.title('Интересующие темы участников')
    plt.ylabel('')
    plt.show()
else:
    print("Нет данных по темам для анализа.")
