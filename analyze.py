import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import logging
import psycopg2
import os
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Create database connection"""
    try:
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

def analyze_survey_data():
    """Analyze survey responses and generate visualizations"""
    try:
        conn = get_db_connection()
        if not conn:
            return

        # Получение данных
        df = pd.read_sql_query('SELECT * FROM responses', conn)
        
        if df.empty:
            logger.info("No data found in database")
            return

        # Создание директории для отчетов
        reports_dir = Path('reports')
        reports_dir.mkdir(exist_ok=True)

        # Анализ по уровням
        level_counts = df['level'].value_counts()
        plt.figure(figsize=(10, 6))
        level_counts.plot(kind='bar')
        plt.title('Distribution of Participant Levels')
        plt.savefig(reports_dir / 'level_distribution.png')
        plt.close()

        # Анализ тем
        topics = []
        for data in df['data']:
            if isinstance(data, str):
                data = json.loads(data)
            if 'topics' in data:
                topics.extend([t.strip() for t in data['topics'].split(',')])

        if topics:
            topic_counts = pd.Series(topics).value_counts()
            plt.figure(figsize=(12, 8))
            topic_counts.plot(kind='pie', autopct='%1.1f%%')
            plt.title('Popular Topics')
            plt.savefig(reports_dir / 'topic_distribution.png')
            plt.close()

        # Анализ времени ответов
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        responses_by_date = df.groupby(df['timestamp'].dt.date).size()
        plt.figure(figsize=(12, 6))
        responses_by_date.plot(kind='line')
        plt.title('Responses Over Time')
        plt.savefig(reports_dir / 'response_timeline.png')
        plt.close()

        # Создание текстового отчета
        with open(reports_dir / 'analysis_report.txt', 'w') as f:
            f.write("Survey Analysis Report\n")
            f.write("===================\n\n")
            f.write(f"Total Responses: {len(df)}\n")
            f.write(f"\nLevel Distribution:\n{level_counts}\n")
            f.write(f"\nMost Popular Topics:\n{topic_counts.head()}\n")
            f.write(f"\nDate Range: {df['timestamp'].min()} to {df['timestamp'].max()}\n")

        logger.info("Analysis completed successfully")
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    analyze_survey_data()

# static/styles.css
body {
    font-family: 'Arial', sans-serif;
    margin: 0;
    padding: 0;
    color: #ffffff;
    background: linear-gradient(135deg, #1a1a1a 0%, #2c2c2c 100%);
    min-height: 100vh;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.header {
    text-align: center;
    padding: 40px 0;
}

h1, h2 {
    margin: 0;
    padding: 20px 0;
    color: #ffffff;
}

.form-container {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 30px;
    margin: 20px 0;
}

.question-group {
    margin-bottom: 25px;
}

label {
    display: block;
    margin-bottom: 10px;
    color: #ffffff;
}

input, textarea {
    width: 100%;
    padding: 12px;
    border: 1px solid #444;
    border-radius: 5px;
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    margin-top: 5px;
}

button {
    background: #4CAF50;
    color: white;
    padding: 12px 24px;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    transition: background 0.3s;
}

button:hover {
    background: #45a049;
}

button:disabled {
    background: #cccccc;
    cursor: not-allowed;
}

.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
}

.modal-content {
    background: #2c2c2c;
    margin: 5% auto;
    padding: 20px;
    width: 90%;
    max-width: 600px;
    border-radius: 10px;
    position: relative;
}

.close {
    position: absolute;
    right: 20px;
    top: 10px;
    font-size: 28px;
    cursor: pointer;
    color: #ffffff;
}

#loading-indicator {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(0, 0, 0, 0.8);
    padding: 20px;
    border-radius: 5px;
    z-index: 2000;
    display: none;
}

#chatgpt-chat {
    height: 300px;
    overflow-y: auto;
    padding: 10px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 5px;
    margin-bottom: 10px;
}

.user-message {
    background: rgba(76, 175, 80, 0.2);
    padding: 10px;
    margin: 5px;
    border-radius: 5px;
    text-align: right;
}

.bot-message {
    background: rgba(33, 150, 243, 0.2);
    padding: 10px;
    margin: 5px;
    border-radius: 5px;
    text-align: left;
}

footer {
    text-align: center;
    padding: 20px;
    margin-top: 40px;
    background: rgba(0, 0, 0, 0.3);
}

footer a {
    color: #ffffff;
    text-decoration: none;
}

footer a:hover {
    text-decoration: underline;
}

@media (max-width: 768px) {
    .container {
        padding: 10px;
    }
    
    .modal-content {
        width: 95%;
        margin: 10% auto;
    }
}
