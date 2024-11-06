import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import logging
import psycopg2
import os
import json
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalyzeManager:
    def __init__(self):
        self.reports_dir = Path('reports')
        self.reports_dir.mkdir(exist_ok=True)
        self._setup_db_indexes()

    def _setup_db_indexes(self):
        """Создание индексов для оптимизации запросов"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return

            with conn.cursor() as cur:
                # Индекс для поиска по уровню
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_responses_level 
                    ON responses (level);
                """)
                
                # Индекс для временных запросов
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_responses_timestamp 
                    ON responses (timestamp);
                """)
                
                # Индекс для JSON данных
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_responses_data_gin 
                    ON responses USING gin (data jsonb_path_ops);
                """)
                
                conn.commit()
                logger.info("Database indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
        finally:
            if conn:
                conn.close()

    def get_db_connection(self):
        """Создание соединения с базой данных"""
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

    @lru_cache(maxsize=32)
    def _get_level_stats(self) -> Dict:
        """Получение статистики по уровням с кэшированием"""
        conn = self.get_db_connection()
        if not conn:
            return {}

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        level,
                        COUNT(*) as count,
                        MIN(timestamp) as first_response,
                        MAX(timestamp) as last_response
                    FROM responses
                    GROUP BY level;
                """)
                results = cur.fetchall()
                return {row[0]: {'count': row[1], 'first': row[2], 'last': row[3]} 
                        for row in results}
        finally:
            conn.close()

    def analyze_survey_data(self):
        """Анализ ответов опроса с оптимизированными запросами"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return

            # Получение данных с оптимизированными запросами
            df = pd.read_sql_query("""
                SELECT 
                    level,
                    data,
                    timestamp
                FROM responses
                WHERE timestamp >= NOW() - INTERVAL '30 days'
            """, conn)
            
            if df.empty:
                logger.info("No data found in database")
                return

            # Анализ по уровням
            level_stats = self._get_level_stats()
            
            # Создание графиков
            plt.figure(figsize=(10, 6))
            level_counts = pd.Series({k: v['count'] for k, v in level_stats.items()})
            level_counts.plot(kind='bar')
            plt.title('Распределение участников по уровням')
            plt.savefig(self.reports_dir / 'level_distribution.png')
            plt.close()

            # Анализ тем с оптимизацией памяти
            topics = []
            for data_json in df['data']:
                if isinstance(data_json, str):
                    data = json.loads(data_json)
                else:
                    data = data_json
                    
                if 'topics' in data:
                    topics.extend([t.strip() for t in data['topics'].split(',')])

            if topics:
                topic_counts = pd.Series(topics).value_counts()
                plt.figure(figsize=(12, 8))
                topic_counts.head(10).plot(kind='pie', autopct='%1.1f%%')
                plt.title('Популярные темы')
                plt.savefig(self.reports_dir / 'topic_distribution.png')
                plt.close()

            # Анализ времени ответов с оптимизацией
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            responses_by_date = df.groupby(df['timestamp'].dt.date).size()
            
            plt.figure(figsize=(12, 6))
            responses_by_date.plot(kind='line')
            plt.title('Ответы по времени')
            plt.savefig(self.reports_dir / 'response_timeline.png')
            plt.close()

            # Создание отчета
            self._generate_report(level_stats, topic_counts, responses_by_date)

            logger.info("Analysis completed successfully")
            
        except Exception as e:
            logger.error(f"Error during analysis: {e}")
        finally:
            if conn:
                conn.close()

    def _generate_report(self, level_stats, topic_counts, responses_by_date):
        """Генерация текстового отчета"""
        with open(self.reports_dir / 'analysis_report.txt', 'w', encoding='utf-8') as f:
            f.write("Отчет по анализу опроса\n")
            f.write("=====================\n\n")
            
            f.write("Статистика по уровням:\n")
            for level, stats in level_stats.items():
                f.write(f"\n{level}:\n")
                f.write(f"  Количество ответов: {stats['count']}\n")
                f.write(f"  Первый ответ: {stats['first']}\n")
                f.write(f"  Последний ответ: {stats['last']}\n")
            
            f.write("\nПопулярные темы:\n")
            for topic, count in topic_counts.head(10).items():
                f.write(f"  {topic}: {count} ({count/sum(topic_counts)*100:.1f}%)\n")
            
            f.write("\nАктивность по датам:\n")
            for date, count in responses_by_date.items():
                f.write(f"  {date}: {count} ответов\n")

    def clear_cache(self):
        """Очистка кэша при необходимости"""
        self._get_level_stats.cache_clear()

# Создание экземпляра менеджера
analyze_manager = AnalyzeManager()

if __name__ == "__main__":
    analyze_manager.analyze_survey_data()
