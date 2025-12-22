"""
Оптимизированный PostgreSQL connection manager с пулом соединений

Этот модуль обеспечивает эффективное управление соединениями с PostgreSQL
для повышения производительности при частых запросах.
"""

import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import threading
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv
from utils.logging_setup import get_logger

# Загружаем переменные окружения с явной кодировкой UTF-8
load_dotenv(encoding='utf-8')

logger = get_logger(__name__)

class PostgreSQLConnectionPool:
    """Пул соединений PostgreSQL с мониторингом производительности"""
    
    def __init__(self, min_connections=2, max_connections=10):
        """
        Инициализация пула соединений
        
        Args:
            min_connections: Минимальное количество соединений в пуле
            max_connections: Максимальное количество соединений в пуле
        """
        # Получаем параметры подключения с явной обработкой кодировки
        password = os.getenv('POSTGRES_PASSWORD', 'simplepassword')
        
        # Если пароль содержит специальные символы, кодируем его корректно
        if isinstance(password, bytes):
            password = password.decode('utf-8', errors='ignore')
        
        self.conn_params = {
            'host': os.getenv('POSTGRES_HOST', '127.0.0.1'),
            'port': int(os.getenv('POSTGRES_PORT', '5432')),
            'database': os.getenv('POSTGRES_DB', 'postgres'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': password,
            'client_encoding': 'UTF8'
        }
        
        self.min_connections = min_connections
        self.max_connections = max_connections
        self._pool = None
        self._lock = threading.Lock()
        
        # Статистика производительности
        self._stats = {
            'total_connections_created': 0,
            'total_queries_executed': 0,
            'total_query_time': 0.0,
            'active_connections': 0,
            'pool_hits': 0,
            'pool_misses': 0,
            'slow_queries': 0,  # Запросы > 100ms
            'errors': 0
        }
        
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Создание пула соединений"""
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=self.min_connections,
                maxconn=self.max_connections,
                **self.conn_params
            )
            self._stats['total_connections_created'] = self.min_connections
            logger.info(f"PostgreSQL pool создан: {self.min_connections}-{self.max_connections} соединений")
            logger.info(f"PostgreSQL connection pool инициализирован ({self.min_connections}-{self.max_connections})")
            
        except Exception as e:
            logger.error(f"Ошибка создания пула соединений: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для получения соединения из пула"""
        connection = None
        start_time = time.time()
        
        try:
            with self._lock:
                if self._pool:
                    connection = self._pool.getconn()
                    self._stats['active_connections'] += 1
                    
                    if connection:
                        self._stats['pool_hits'] += 1
                    else:
                        self._stats['pool_misses'] += 1
                        
            if not connection:
                raise Exception("Не удалось получить соединение из пула")
            
            yield connection
            
        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"Ошибка соединения с БД: {e}")
            raise
            
        finally:
            if connection:
                try:
                    with self._lock:
                        if self._pool:
                            self._pool.putconn(connection)
                            self._stats['active_connections'] -= 1
                            
                    # Статистика времени выполнения
                    query_time = time.time() - start_time
                    self._stats['total_query_time'] += query_time
                    self._stats['total_queries_executed'] += 1
                    
                    if query_time > 0.1:  # Медленные запросы > 100ms
                        self._stats['slow_queries'] += 1
                        logger.warning(f"⚠️ Медленный запрос: {query_time:.3f}s")
                        
                except Exception as e:
                    logger.error(f"Ошибка возврата соединения в пул: {e}")
    
    @contextmanager 
    def get_cursor(self, cursor_factory=RealDictCursor):
        """Контекстный менеджер для получения курсора"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Получить статистику пула соединений"""
        avg_query_time = (
            self._stats['total_query_time'] / max(self._stats['total_queries_executed'], 1)
        )
        
        pool_usage = (self._stats['active_connections'] / self.max_connections) * 100
        
        return {
            'pool_config': {
                'min_connections': self.min_connections,
                'max_connections': self.max_connections,
                'active_connections': self._stats['active_connections'],
                'pool_usage_percent': round(pool_usage, 1)
            },
            'performance': {
                'total_queries': self._stats['total_queries_executed'],
                'total_query_time': round(self._stats['total_query_time'], 3),
                'average_query_time': round(avg_query_time * 1000, 2),  # в миллисекундах
                'slow_queries': self._stats['slow_queries'],
                'slow_query_rate': round((self._stats['slow_queries'] / max(self._stats['total_queries_executed'], 1)) * 100, 2)
            },
            'pool_efficiency': {
                'pool_hits': self._stats['pool_hits'],
                'pool_misses': self._stats['pool_misses'],
                'hit_rate': round((self._stats['pool_hits'] / max(self._stats['pool_hits'] + self._stats['pool_misses'], 1)) * 100, 2)
            },
            'errors': {
                'total_errors': self._stats['errors'],
                'error_rate': round((self._stats['errors'] / max(self._stats['total_queries_executed'], 1)) * 100, 2)
            }
        }
    
    def print_pool_stats(self):
        """Вывести статистику пула в консоль"""
        stats = self.get_pool_stats()
        stats_block = (
            "\nСТАТИСТИКА POSTGRESQL CONNECTION POOL\n"
            + "=" * 55 + "\n"
            " Конфигурация пула:\n"
            f"   • Диапазон соединений: {stats['pool_config']['min_connections']}-{stats['pool_config']['max_connections']}\n"
            f"   • Активные соединения: {stats['pool_config']['active_connections']}\n"
            f"   • Использование пула: {stats['pool_config']['pool_usage_percent']}%\n\n"
            "⚡ Производительность:\n"
            f"   • Всего запросов: {stats['performance']['total_queries']}\n"
            f"   • Среднее время запроса: {stats['performance']['average_query_time']}ms\n"
            f"   • Медленных запросов: {stats['performance']['slow_queries']} ({stats['performance']['slow_query_rate']}%)\n\n"
            " Эффективность пула:\n"
            f"   • Попадания в пул: {stats['pool_efficiency']['pool_hits']}\n"
            f"   • Промахи пула: {stats['pool_efficiency']['pool_misses']}\n"
            f"   • Hit Rate: {stats['pool_efficiency']['hit_rate']}%\n\n"
            "Ошибки:\n"
            f"   • Всего ошибок: {stats['errors']['total_errors']} ({stats['errors']['error_rate']}%)\n"
            + "=" * 55
        )

        if stats['errors']['total_errors'] > 0:
            logger.warning(stats_block)
        else:
            logger.info(stats_block)
    
    def close_pool(self):
        """Закрыть пул соединений"""
        if self._pool:
            self._pool.closeall()
            print(" PostgreSQL connection pool закрыт")
            logger.info("PostgreSQL connection pool closed")

# Глобальный экземпляр пула соединений
_connection_pool = None

def get_connection_pool() -> PostgreSQLConnectionPool:
    """Получить глобальный экземпляр пула соединений"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = PostgreSQLConnectionPool(
            min_connections=3,  # Оптимальное количество для Discord bot
            max_connections=8   # Достаточно для пиковых нагрузок
        )
    return _connection_pool

def get_pool_statistics() -> Dict[str, Any]:
    """Получить статистику пула соединений"""
    pool = get_connection_pool()
    return pool.get_pool_stats()

def print_connection_pool_status():
    """Вывести статистику пула соединений"""
    pool = get_connection_pool()
    pool.print_pool_stats()

# Convenience функции для использования в существующем коде
@contextmanager
def get_db_connection():
    """Получить соединение с БД через пул"""
    pool = get_connection_pool()
    with pool.get_connection() as conn:
        yield conn

@contextmanager
def get_db_cursor(cursor_factory=RealDictCursor):
    """Получить курсор БД через пул"""
    pool = get_connection_pool()
    with pool.get_cursor(cursor_factory=cursor_factory) as cursor:
        yield cursor