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

class TopicAnalyzer:
    def __init__(self):
        self.categories = {
            'technical': [
                'программирование', 'код', 'python', 'javascript',
                'нейронные сети', 'машинное обучение', 'алгоритмы',
                'разработка', 'coding', 'development'
            ],
            'business': [
                'бизнес', 'применение', 'внедрение', 'оптимизация',
                'автоматизация', 'проекты', 'продукты', 'решения',
                'efficiency', 'automation'
            ],
            'theoretical': [
                'теория', 'концепции', 'принципы', 'основы',
                'математика', 'алгоритмы', 'research', 'исследования',
                'методология', 'фундаментальные'
            ]
        }
        
    def categorize_text(self, text):
        """Категоризация текста по трем основным категориям"""
        if not text:
            return {}
            
        text = text.lower()
        scores = {category: 0 for category in self.categories}
        
        for category, keywords in self.categories.items():
            for keyword in keywords:
                if keyword in text:
                    scores[category] += 1
                    
        # Нормализация счета
        max_score = max(scores.values()) if scores.values() else 1
        normalized_scores = {
            category: (score / max_score) * 100 
            for category, score in scores.items()
        }
        
        return normalized_scores

class AnalyzeManager:
    def __init__(self):
        self.reports_dir = Path('reports')
        self.reports_dir.mkdir(exist_ok=True)
        self.topic_analyzer = TopicAnalyzer()
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
            self._create_level_distribution_plot(level_stats)
            self._create_topic_distribution_plot(df)
            self._create_response_timeline_plot(df)
            
            # Анализ категорий
            categorized_data = self.get_categorized_responses()
            self._create_category_analysis_plot(categorized_data)

            # Создание отчета
            self._generate_report(level_stats, categorized_data)

            logger.info("Analysis completed successfully")
            
        except Exception as e:
            logger.error(f"Error during analysis: {e}")
        finally:
            if conn:
                conn.close()

    def _create_level_distribution_plot(self, level_stats):
        plt.figure(figsize=(10, 6))
        level_counts = pd.Series({k: v['count'] for k, v in level_stats.items()})
        level_counts.plot(kind='bar')
        plt.title('Распределение участников по уровням')
        plt.savefig(self.reports_dir / 'level_distribution.png')
        plt.close()

    def _create_topic_distribution_plot(self, df):
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

    def _create_response_timeline_plot(self, df):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        responses_by_date = df.groupby(df['timestamp'].dt.date).size()
        
        plt.figure(figsize=(12, 6))
        responses_by_date.plot(kind='line')
        plt.title('Ответы по времени')
        plt.savefig(self.reports_dir / 'response_timeline.png')
        plt.close()

    def _create_category_analysis_plot(self, categorized_data):
        plt.figure(figsize=(12, 6))
        
        categories = ['technical', 'business', 'theoretical']
        x = np.arange(len(categories))
        width = 0.35

        beginner_values = [categorized_data['all_time']['beginner'][cat] for cat in categories]
        advanced_values = [categorized_data['all_time']['advanced'][cat] for cat in categories]

        plt.bar(x - width/2, beginner_values, width, label='Начинающие')
        plt.bar(x + width/2, advanced_values, width, label='Продвинутые')

        plt.xlabel('Категории')
        plt.ylabel('Проценты')
        plt.title('Распределение по категориям')
        plt.xticks(x, categories)
        plt.legend()

        plt.savefig(self.reports_dir / 'category_analysis.png')
        plt.close()

    def get_categorized_responses(self, time_range='all'):
        """Получение категоризированных ответов за указанный период"""
        conn = self.get_db_connection()
        if not conn:
            return {}

        try:
            with conn.cursor() as cur:
                query = """
                    SELECT level, data, timestamp 
                    FROM responses 
                    WHERE 1=1
                """
                if time_range == 'month':
                    query += " AND timestamp >= NOW() - INTERVAL '30 days'"
                
                cur.execute(query)
                responses = cur.fetchall()

                categorized_data = {
                    'beginner': [],
                    'advanced': []
                }

                for level, data, timestamp in responses:
                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    # Анализ текстовых ответов
                    text_to_analyze = ' '.join([
                        str(data.get('expectations', '')),
                        str(data.get('experience', '')),
                        str(data.get('interests', '')),
                        str(data.get('topics', ''))
                    ])
                    
                    categories = self.topic_analyzer.categorize_text(text_to_analyze)
                    
                    categorized_data[level].append({
                        'timestamp': timestamp,
                        'categories': categories,
                        'raw_text': text_to_analyze
                    })

                return categorized_data

        except Exception as e:
            logger.error(f"Error categorizing responses: {e}")
            return {}
        finally:
            conn.close()

    def generate_topic_analysis(self):
        """Генерация анализа тем для API"""
        try:
            all_time_data = self.get_categorized_responses('all')
            monthly_data = self.get_categorized_responses('month')
            
            analysis = {
                'all_time': self._aggregate_categories(all_time_data),
                'monthly': self._aggregate_categories(monthly_data)
            }
            
            # Сохранение результатов анализа
            with open(self.reports_dir / 'topic_analysis.json', 'w', encoding='utf-8') as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
                
            return analysis
            
        except Exception as e:
            logger.error(f"Error generating topic analysis: {e}")
            return {}

    def _aggregate_categories(self, categorized_data):
        """Агрегация категоризированных данных"""
        result = {
            'beginner': {
                'technical': 0,
                'business': 0,
                'theoretical': 0
            },
            'advanced': {
                'technical': 0,
                'business': 0,
                'theoretical': 0
            }
        }
        
        for level in ['beginner', 'advanced']:
            if not categorized_data.get(level):
                continue
                
            responses = categorized_data[level]
            if not responses:
                continue
                
            # Вычисление средних значений по категориям
            for category in ['technical', 'business', 'theoretical']:
                values = [r['categories'].get(category, 0) for r in responses]
                result[level][category] = sum(values) / len(values)
                
        return result

    def _generate_report(self, level_stats, categorized_data):
        """Генерация текстового отчета"""
        with open(self.reports_dir / 'analysis_report.txt', 'w', encoding='utf-8') as f:
            f.write("Отчет по анализу опроса\n")
            f.write("=====================\n\n")
            
            # Статистика по уровням
            f.write("Статистика по уровням:\n")
            for level, stats in level_stats.items():
                f.write(f"\n{level}:\n")
                f.write(f"  Количество ответов: {stats['count']}\n")
                f.write(f"  Первый ответ: {stats['first']}\n")
                f.write(f"  Последний ответ: {stats['last']}\n")
            
            # Анализ категорий
            f.write("\nРаспределение по категориям:\n")
            for level in ['beginner', 'advanced']:
                f.write(f"\n{level}:\n")
                categories = categorized_data['all_time'][level]
                for category, value in categories.items():
                    f.write(f"  {category}: {value:.1f}%\n")

# Создание экземпляра менеджера
analyze_manager = AnalyzeManager()

if __name__ == "__main__":
    analyze_manager.analyze_survey_data()
