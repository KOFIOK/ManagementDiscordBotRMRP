"""
User Data Caching System

Безопасная система кэширования данных пользователей для оптимизации
запросов к PostgreSQL и предотвращения таймаутов Discord.

Features:
- Временное кэширование в памяти с TTL
- Предзагрузка данных для часто используемых операций
- Безопасная обработка ошибок с fallback
- Статистика использования кэша
- BULK PRELOAD - массовая предзагрузка всего листа при старте бота
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple, List
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class UserDataCache:
    """Система кэширования данных пользователей"""
    
    def __init__(self):
        # Кэш данных пользователей: {user_id: user_data}
        self._cache: Dict[int, Dict[str, Any]] = {}
        
        # Время истечения кэша: {user_id: expiry_datetime}
        self._expiry: Dict[int, datetime] = {}
        
        # Защита от рекурсивных вызовов
        self._loading: Dict[int, bool] = {}
        
        # Флаг предзагрузки всего листа
        self._bulk_preloaded = False
        self._bulk_preload_time = None
        self._bulk_preload_lock = asyncio.Lock()
        
        # Статистика кэша
        self._stats = {
            'hits': 0,
            'misses': 0,
            'total_requests': 0,
            'cache_size': 0,
            'last_cleanup': datetime.now(),
            'bulk_preload_count': 0,
            'bulk_preload_time': None
        }
        
        # Настройки (оптимизированные)
        self.CACHE_TTL = 300  # 5 минут TTL - баланс между актуальностью и производительностью
        self.MAX_CACHE_SIZE = 1000  # Достаточно для роста (текущие 281 + запас)
        self.CLEANUP_INTERVAL = 300  # Очистка каждые 5 минут
        self.BULK_PRELOAD_TTL = 1800  # Перезагрузка всего листа каждые 30 минут
    
    async def get_user_info(self, user_id: int, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о пользователе с кэшированием
        
        Args:
            user_id: Discord ID пользователя
            force_refresh: Принудительно обновить данные из БД
            
        Returns:
            Dict с данными пользователя или None если не найден
        """
        self._stats['total_requests'] += 1
        
        # АВТОМАТИЧЕСКАЯ ПРЕДЗАГРУЗКА только при первом запросе (оптимизировано)
        if not self._bulk_preloaded and not self._loading.get('__bulk_preload__', False):
            logger.info("AUTO BULK PRELOAD: Запускаем автоматическую предзагрузку (только первый раз)")
            self._loading['__bulk_preload__'] = True
            try:
                # Запускаем предзагрузку в фоне (не блокируем текущий запрос)
                asyncio.create_task(self._auto_bulk_preload())
            except Exception as e:
                logger.error("AUTO BULK PRELOAD ERROR: %s", e)
            finally:
                self._loading.pop('__bulk_preload__', None)
        
        # Защита от рекурсивных вызовов
        if self._loading.get(user_id, False):
            logger.info("RECURSIVE PROTECTION: Обнаружен рекурсивный вызов для %s, возвращаем None", user_id)
            return None
        
        # Проверяем, нужно ли принудительное обновление
        if not force_refresh and self._is_cached(user_id):
            self._stats['hits'] += 1
            logger.info("CACHE HIT: Данные пользователя %s получены из кэша", user_id)
            cached_data = self._cache[user_id]
            return cached_data.copy() if cached_data is not None else None
        
        # Кэш пропуск - загружаем данные
        self._stats['misses'] += 1
        logger.info("CACHE MISS: Загружаем данные пользователя %s из базы", user_id)
        
        # Устанавливаем флаг загрузки
        self._loading[user_id] = True
        
        try:            
            # Если предзагрузка прошла, но пользователь не найден - это может быть новый пользователь
            # Поэтому загружаем из PostgreSQL, а не возвращаем None
            if self._bulk_preloaded and user_id not in self._cache:
                logger.info("BULK MISS: Пользователь %s не найден в предзагруженных данных, загружаем из PostgreSQL", user_id)
            
            # Пытаемся использовать оптимизированный запрос только если он не будет вызывать рекурсию
            user_data = None
            
            # Используем database_manager для получения данных
            try:
                # Lazy import to avoid circular dependency
                from utils.database_manager import personnel_manager
                user_data = await personnel_manager.get_personnel_summary(user_id)
                if user_data:
                    # Данные уже в правильном формате, не нужно переопределять с fallback значениями
                    logger.info(f"DATABASE_MANAGER: Получены ПОЛНЫЕ данные для {user_id} - {user_data.get('rank', 'N/A')} {user_data.get('full_name', 'N/A')} ({user_data.get('department', 'N/A')})")
                else:
                    logger.info("DATABASE_MANAGER: Данные для %s не найдены", user_id)
            except Exception as e:
                logger.info("DATABASE_MANAGER FALLBACK: %s", e)
                user_data = None
            
            if user_data:
                # Сохраняем в кэш
                self._store_in_cache(user_id, user_data)
                logger.info("CACHE STORE: Данные пользователя %s сохранены в кэш", user_id)
                return user_data.copy() if user_data is not None else None
            else:
                # Сохраняем отрицательный результат (чтобы не запрашивать повторно)
                self._store_in_cache(user_id, None)
                logger.info("CACHE STORE: Пользователь %s не найден, сохранен отрицательный результат", user_id)
                return None
                
        except Exception as e:
            logger.error("CACHE ERROR: Ошибка загрузки данных пользователя %s: %s", user_id, e)
            # Возвращаем устаревшие данные из кэша, если есть
            if user_id in self._cache:
                logger.info("CACHE FALLBACK: Используем устаревшие данные для %s", user_id)
                return self._cache[user_id].copy()
            return None
        finally:
            # Всегда очищаем флаг загрузки
            self._loading.pop(user_id, None)
    
    async def _auto_bulk_preload(self):
        """Автоматическая предзагрузка в фоне"""
        try:
            logger.info("AUTO BULK PRELOAD: Запуск фоновой предзагрузки")
            result = await self.bulk_preload_all_users()
            if result.get('success', False):
                logger.info("AUTO BULK PRELOAD: Фоновая предзагрузка завершена успешно")
            else:
                logger.error(f"AUTO BULK PRELOAD: Фоновая предзагрузка не удалась: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error("AUTO BULK PRELOAD ERROR: %s", e)
    
    def _is_cached(self, user_id: int) -> bool:
        """Проверить, есть ли действительные данные в кэше"""
        if user_id not in self._cache:
            return False
        
        if user_id not in self._expiry:
            return False
        
        return datetime.now() < self._expiry[user_id]
    
    async def _get_user_info_internal(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Внутренняя функция получения данных БЕЗ увеличения счетчика запросов
        Используется для избежания рекурсивных проблем в fallback логике
        """
        # Проверяем кэш без увеличения счетчика
        if self._is_cached(user_id):
            logger.info("INTERNAL CACHE HIT: Данные пользователя %s получены из кэша", user_id)
            cached_data = self._cache[user_id]
            return cached_data.copy() if cached_data is not None else None
        
        # Защита от рекурсивных вызовов
        if self._loading.get(user_id, False):
            logger.info("INTERNAL RECURSIVE PROTECTION: Обнаружен рекурсивный вызов для %s", user_id)
            return None
        
        # Устанавливаем флаг загрузки
        self._loading[user_id] = True
        
        try:
            # Используем database_manager для получения ПОЛНЫХ данных
            # Lazy import to avoid circular dependency
            from utils.database_manager import personnel_manager
            user_data = await personnel_manager.get_personnel_summary(user_id)
            
            if user_data:
                # Данные уже в правильном формате от PersonnelManager, не переопределяем
                logger.info(f"INTERNAL DATABASE_MANAGER: Получены ПОЛНЫЕ данные для {user_id} - {user_data.get('rank', 'N/A')} {user_data.get('full_name', 'N/A')} ({user_data.get('department', 'N/A')})")
            else:
                logger.info("INTERNAL DATABASE_MANAGER: Данные для %s не найдены", user_id)
                user_data = None
            
            if user_data:
                # Сохраняем в кэш
                self._store_in_cache(user_id, user_data)
                logger.info("INTERNAL CACHE STORE: Данные пользователя %s сохранены в кэш", user_id)
                return user_data.copy()
            else:
                # Сохраняем отрицательный результат
                self._store_in_cache(user_id, None)
                logger.info("INTERNAL CACHE STORE: Пользователь %s не найден", user_id)
                return None
                
        except Exception as e:
            logger.error("INTERNAL CACHE ERROR: %s", e)
            return None
        finally:
            # Всегда очищаем флаг загрузки
            self._loading.pop(user_id, None)
    
    def _store_in_cache(self, user_id: int, user_data: Optional[Dict[str, Any]]):
        """Сохранить данные в кэш"""
        # Проверяем размер кэша
        if len(self._cache) >= self.MAX_CACHE_SIZE:
            self._cleanup_expired()
            
            # Если все еще переполнен, удаляем самые старые записи
            if len(self._cache) >= self.MAX_CACHE_SIZE:
                self._remove_oldest_entries(self.MAX_CACHE_SIZE // 4)  # Удаляем 25%
        
        # Сохраняем данные
        self._cache[user_id] = user_data
        self._expiry[user_id] = datetime.now() + timedelta(seconds=self.CACHE_TTL)
        self._stats['cache_size'] = len(self._cache)
    
    def _cleanup_expired(self):
        """Очистить истекшие записи кэша"""
        now = datetime.now()
        expired_keys = [
            user_id for user_id, expiry_time in self._expiry.items()
            if expiry_time <= now
        ]
        
        for user_id in expired_keys:
            self._cache.pop(user_id, None)
            self._expiry.pop(user_id, None)
        
        if expired_keys:
            logger.info(f"CACHE CLEANUP: Удалено {len(expired_keys)} истекших записей")
        
        self._stats['cache_size'] = len(self._cache)
        self._stats['last_cleanup'] = now
    
    def _remove_oldest_entries(self, count: int):
        """Удалить самые старые записи"""
        if not self._expiry:
            return
        
        # Сортируем по времени истечения (самые старые первыми)
        sorted_entries = sorted(self._expiry.items(), key=lambda x: x[1])
        
        for i in range(min(count, len(sorted_entries))):
            user_id = sorted_entries[i][0]
            self._cache.pop(user_id, None)
            self._expiry.pop(user_id, None)
        
        logger.info(f"CACHE EVICTION: Удалено {min(count, len(sorted_entries))} старых записей")
        self._stats['cache_size'] = len(self._cache)
    
    def invalidate_user(self, user_id: int):
        """Принудительно удалить пользователя из кэша"""
        self._cache.pop(user_id, None)
        self._expiry.pop(user_id, None)
        self._stats['cache_size'] = len(self._cache)
        logger.info("CACHE INVALIDATE: Данные пользователя %s удалены из кэша", user_id)
    
    def clear_cache(self):
        """Полностью очистить кэш"""
        self._cache.clear()
        self._expiry.clear()
        self._stats['cache_size'] = 0
        # ВАЖНО: Сбрасываем флаг bulk preload при очистке кэша
        self._bulk_preloaded = False
        self._bulk_preload_time = None
        logger.info("CACHE CLEAR: Кэш полностью очищен, bulk preload сброшен")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        self._stats['cache_size'] = len(self._cache)
        
        # Вычисляем hit rate
        total_requests = self._stats['total_requests']
        if total_requests > 0:
            hit_rate = (self._stats['hits'] / total_requests) * 100
        else:
            hit_rate = 0
        
        return {
            **self._stats,
            'hit_rate_percent': round(hit_rate, 2),
            'expired_entries': self._count_expired_entries(),
            'memory_usage_estimate': len(self._cache) * 500  # Примерная оценка в байтах
        }
    
    def _count_expired_entries(self) -> int:
        """Подсчитать количество истекших записей"""
        now = datetime.now()
        return sum(1 for expiry_time in self._expiry.values() if expiry_time <= now)
    
    async def preload_users(self, user_ids: list) -> Dict[int, Optional[Dict[str, Any]]]:
        """
        Предзагрузить данные для списка пользователей
        
        Args:
            user_ids: Список Discord ID пользователей
            
        Returns:
            Dict {user_id: user_data} с результатами предзагрузки
        """
        logger.info(f"CACHE PRELOAD: Предзагрузка данных для {len(user_ids)} пользователей")
        
        results = {}
        tasks = []
          # Создаем задачи для параллельной загрузки
        for user_id in user_ids:
            if not self._is_cached(user_id):  # Загружаем только отсутствующие
                tasks.append(self.get_user_info(user_id))
            else:
                results[user_id] = self._cache[user_id].copy()
        
        # Выполняем задачи параллельно или batch-запросом
        if tasks:
            try:
                # Пробуем использовать batch-запрос для оптимизации
                missing_user_ids = [uid for uid in user_ids if uid not in results]
                
                # Batch-оптимизация удалена после миграции на PostgreSQL
                # Используем стандартную параллельную загрузку
                batch_error = Exception("Batch optimization not available with PostgreSQL")
                logger.error("BATCH FALLBACK: %s", batch_error)
                logger.info("STANDARD PRELOAD: Используем стандартные параллельные запросы")
                # Fallback на стандартную параллельную загрузку
                # Ограничиваем количество одновременных запросов
                semaphore = asyncio.Semaphore(5)  # Максимум 5 одновременных запросов
                
                async def limited_get_user_info(user_id):
                    async with semaphore:
                        return await self.get_user_info(user_id)
                
                limited_tasks = [limited_get_user_info(uid) for uid in missing_user_ids]
                task_results = await asyncio.gather(*limited_tasks, return_exceptions=True)
                
                # Обрабатываем результаты
                for i, result in enumerate(task_results):
                    user_id = missing_user_ids[i]
                    if isinstance(result, Exception):
                        logger.error("PRELOAD ERROR для %s: %s", user_id, result)
                        results[user_id] = None
                    else:
                        results[user_id] = result
                        
            except Exception as e:
                logger.error("PRELOAD BATCH ERROR: %s", e)
        
        logger.info(f"CACHE PRELOAD завершена: {len(results)} пользователей обработано")
        return results
    
    async def bulk_preload_all_users(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        МАССОВАЯ ПРЕДЗАГРУЗКА всех пользователей из PostgreSQL в кэш
        
        Загружает ВСЕ данные пользователей одним запросом к PostgreSQL
        и кэширует их для быстрого доступа.
        
        Args:
            force_refresh: Принудительно обновить даже если данные свежие
            
        Returns:
            Dict[str, Any]: Результат предзагрузки с информацией о пользователях
        """
        async with self._bulk_preload_lock:
            # Проверяем, нужна ли предзагрузка
            if not force_refresh and self._is_bulk_preload_valid():
                logger.info("BULK PRELOAD: Данные свежие, пропускаем предзагрузку")
                return {
                    'success': True,
                    'users_loaded': len(self._cache),
                    'from_cache': True,
                    'message': 'Данные свежие, пропускаем предзагрузку'
                }
            
            logger.info("BULK PRELOAD: Начинаем массовую предзагрузку из PostgreSQL")
            start_time = datetime.now()
            
            try:
                # Получаем ВСЕ полные данные из database_manager используя get_all_personnel
                # Lazy import to avoid circular dependency
                from utils.database_manager import personnel_manager
                all_users_raw = await personnel_manager.get_all_personnel()
                
                # Преобразуем в ожидаемый формат для leave_requests
                all_users = []
                for user_data in all_users_raw:
                    if user_data.get('discord_id'):
                        formatted_user = {
                            'discord_id': user_data.get('discord_id'),
                            'full_name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                            'static': user_data.get('static', ''),
                            'position': user_data.get('position', 'Не указано'),
                            'rank': user_data.get('rank', 'Не указано'),
                            'department': user_data.get('subdivision', 'Не определено'),
                            # Добавляем дополнительные поля для совместимости
                            'first_name': user_data.get('first_name', ''),
                            'last_name': user_data.get('last_name', ''),
                            'employee_status': 'active' if user_data.get('rank') else None
                        }
                        all_users.append(formatted_user)
                
                if not all_users:
                    logger.info("BULK PRELOAD: Нет пользователей в database_manager")
                    return {
                        'success': False,
                        'users_loaded': 0,
                        'error': 'Нет пользователей в database_manager'
                    }
                
                # Кэшируем все записи
                preloaded_count = 0
                error_count = 0
                
                for user_data in all_users:
                    try:
                        discord_id = user_data.get('discord_id')
                        if not discord_id:
                            continue
                        
                        # Сохраняем в кэш (с продленным TTL для bulk данных)
                        self._store_in_cache_bulk(discord_id, user_data)
                        preloaded_count += 1
                        
                    except Exception as record_error:
                        error_count += 1
                        continue
                
                # Отмечаем успешную предзагрузку
                self._bulk_preloaded = True
                self._bulk_preload_time = datetime.now()
                self._stats['bulk_preload_count'] = preloaded_count
                self._stats['bulk_preload_time'] = self._bulk_preload_time
                
                load_time = (datetime.now() - start_time).total_seconds()
                
                # Логируем статистику одним многострочным сообщением без лишних уровней
                preload_summary = (
                    "\nBULK PRELOAD: Завершена"
                    f" за {load_time:.2f}s\n"
                    f"   • Предзагружено: {preloaded_count} пользователей\n"
                    f"   • Ошибок: {error_count}\n"
                    f"   • Размер кэша: {len(self._cache)} записей"
                )
                if error_count > 0:
                    logger.warning(preload_summary)
                else:
                    logger.info(preload_summary)
                
                return {
                    'success': True,
                    'users_loaded': preloaded_count,
                    'errors': error_count,
                    'load_time': load_time,
                    'cache_size': len(self._cache)
                }
                
            except Exception as e:
                logger.error("BULK PRELOAD ERROR: %s", e)
                import traceback
                traceback.print_exc()
                return {
                    'success': False,
                    'users_loaded': 0,
                    'error': str(e)
                }
    
    def _is_bulk_preload_valid(self) -> bool:
        """Проверить, актуальна ли массовая предзагрузка"""
        if not self._bulk_preloaded or not self._bulk_preload_time:
            return False
        
        # Проверяем TTL предзагрузки
        age = datetime.now() - self._bulk_preload_time
        return age.total_seconds() < self.BULK_PRELOAD_TTL
    
    def _store_in_cache_bulk(self, user_id: int, user_data: Optional[Dict[str, Any]]):
        """Сохранить данные в кэш при массовой предзагрузке (с продленным TTL)"""
        # Для bulk данных используем более длительный TTL
        bulk_ttl = max(self.CACHE_TTL, self.BULK_PRELOAD_TTL)
        
        # Сохраняем данные
        self._cache[user_id] = user_data
        self._expiry[user_id] = datetime.now() + timedelta(seconds=bulk_ttl)
        self._stats['cache_size'] = len(self._cache)
    
    async def background_cleanup_task(self):
        """Фоновая задача для периодической очистки кэша"""
        while True:
            try:
                await asyncio.sleep(self.CLEANUP_INTERVAL)
                
                # Проверяем, нужна ли очистка
                now = datetime.now()
                if (now - self._stats['last_cleanup']).total_seconds() >= self.CLEANUP_INTERVAL:
                    self._cleanup_expired()
                    
            except asyncio.CancelledError:
                logger.info("CACHE CLEANUP TASK: Задача очистки остановлена")
                break
            except Exception as e:
                logger.error("CACHE CLEANUP ERROR: %s", e)


# Глобальный экземпляр кэша
user_cache = UserDataCache()


# =================== УНИВЕРСАЛЬНЫЕ ФУНКЦИИ ДЛЯ ВСЕХ МОДУЛЕЙ ===================

# Глобальный экземпляр кэша для использования во всех модулях
_global_cache = UserDataCache()


async def initialize_user_cache(force_refresh: bool = False) -> bool:
    """
    Инициализация кэша пользователей
    
    Args:
        force_refresh: Принудительно обновить даже если данные свежие
        
    Returns:
        bool: True если инициализация прошла успешно
    """
    logger.info("CACHE INIT: Инициализация кэша пользователей")
    result = await _global_cache.bulk_preload_all_users(force_refresh)
    return result.get('success', False)


async def refresh_user_cache() -> bool:
    """
    Принудительное обновление всего кэша
    
    Returns:
        bool: True если обновление прошло успешно
    """
    logger.info("CACHE REFRESH: Принудительное обновление кэша")
    result = await _global_cache.bulk_preload_all_users(force_refresh=True)
    return result.get('success', False)


def is_cache_initialized() -> bool:
    """
    Проверить, инициализирован ли кэш
    
    Returns:
        bool: True если кэш инициализирован
    """
    return _global_cache._bulk_preloaded and _global_cache._is_bulk_preload_valid()


async def get_cached_user_info(user_id: int, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """
    Универсальная функция для получения данных пользователя с кэшированием
    
    Используется во всех модулях бота для автоматического кэширования
    
    Args:
        user_id: Discord ID пользователя
        force_refresh: Принудительно обновить данные из БД
        
    Returns:
        Dict с данными пользователя или None если не найден
    """
    return await _global_cache.get_user_info(user_id, force_refresh)


def get_cache_statistics() -> Dict[str, Any]:
    """
    Получить статистику использования кэша
    
    Returns:
        Dict со статистикой кэша
    """
    return _global_cache.get_cache_stats()


def clear_user_cache() -> None:
    """
    Очистить весь кэш
    """
    _global_cache.clear_cache()


def invalidate_user_cache(user_id: int) -> None:
    """
    Удалить конкретного пользователя из кэша
    
    Args:
        user_id: Discord ID пользователя для удаления
    """
    if user_id in _global_cache._cache:
        del _global_cache._cache[user_id]
        del _global_cache._expiry[user_id]
        _global_cache._stats['cache_size'] = len(_global_cache._cache)
        logger.info("CACHE INVALIDATE: Пользователь %s удален из кэша", user_id)


async def preload_user_data(user_ids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
    """
    Предзагрузить данные нескольких пользователей в кэш
    
    Args:
        user_ids: Список Discord ID пользователей
        
    Returns:
        Dict с результатами загрузки
    """
    results = {}
    for user_id in user_ids:
        user_data = await _global_cache.get_user_info(user_id)
        results[user_id] = user_data
    
    logger.info(f"CACHE PRELOAD: Предзагружено {len(user_ids)} пользователей")
    return results


async def get_user_name_fast(user_id: int) -> str:
    """
    Быстро получить полное имя пользователя
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Полное имя пользователя или "Не найден"
    """
    user_data = await get_cached_user_info(user_id)
    if user_data:
        return user_data.get('full_name', 'Не указано')
    return "Не найден"


async def get_user_static_fast(user_id: int) -> str:
    """
    Быстро получить статик пользователя
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Статик пользователя или "Не найден"
    """
    user_data = await get_cached_user_info(user_id)
    if user_data:
        return user_data.get('static', 'Не указано')
    return "Не найден"


async def get_user_department_fast(user_id: int) -> str:
    """
    Быстро получить подразделение пользователя
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Подразделение пользователя или "Не определено"
    """
    user_data = await get_cached_user_info(user_id)
    if user_data:
        return user_data.get('department', 'Не определено')
    return "Не определено"


async def get_user_rank_fast(user_id: int) -> str:
    """
    Быстро получить звание пользователя
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Звание пользователя или "Не указано"
    """
    user_data = await get_cached_user_info(user_id)
    if user_data:
        return user_data.get('rank', 'Не указано')
    return "Не указано"


async def get_user_position_fast(user_id: int) -> str:
    """
    Быстро получить должность пользователя
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Должность пользователя или "Не указано"
    """
    user_data = await get_cached_user_info(user_id)
    if user_data:
        return user_data.get('position', 'Не указано')
    return "Не указано"


# =================== СОВМЕСТИМОСТЬ СО СТАРЫМ КОДОМ ===================

def get_cached_user_info_sync(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Синхронное получение данных пользователя ТОЛЬКО из кэша
    Используется для быстрого автозаполнения форм
    """
    try:
        if _global_cache._is_cached(user_id):
            cached_data = _global_cache._cache.get(user_id)
            if cached_data and cached_data != "NOT_FOUND":
                return cached_data.copy()
        return None
    except Exception:
        return None

# Алиасы для совместимости с существующим кодом warehouse
async def get_warehouse_user_data(user_id: int) -> Dict[str, str]:
    """Совместимость с warehouse_user_data модулем"""
    user_data = await get_cached_user_info(user_id)
    if user_data:
        return {
            'name_value': user_data.get('full_name', ''),
            'static_value': user_data.get('static', ''),
            'source': 'universal_cache'
        }
    return {
        'name_value': '',
        'static_value': '',
        'source': 'not_found'
    }

async def prepare_modal_data(user_id: int) -> Dict[str, str]:
    """
    Подготовить данные пользователя для автозаполнения модального окна
    (замена warehouse_user_data.prepare_modal_data)
    """
    try:
        user_data = await get_cached_user_info(user_id)
        
        if user_data:
            name_value = user_data.get('full_name', '')
            static_value = user_data.get('static', '')
            
            return {
                'name_value': name_value,
                'static_value': static_value,
                'name_placeholder': f"Данные из кэша: {name_value}" if name_value else "Введите ваше имя и фамилию",
                'static_placeholder': f"Данные из кэша: {static_value}" if static_value else "Например: 123-456",
                'has_data': bool(name_value or static_value),
                'source': 'cache'
            }
        else:
            return {
                'name_value': '',
                'static_value': '',
                'name_placeholder': "Введите ваше имя и фамилию",
                'static_placeholder': "Например: 123-456",
                'has_data': False,
                'source': 'none'
            }
            
    except Exception as e:
        logger.error("MODAL PREP ERROR: %s", e)
        return {
            'name_value': '',
            'static_value': '',
            'name_placeholder': "Введите ваше имя и фамилию (ошибка загрузки данных)",
            'static_placeholder': "Например: 123-456",
            'has_data': False,
            'source': 'error'
        }

# Основные функции для использования в коде
async def get_cached_user_info(user_id: int, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Основная функция для получения данных пользователя через кэш"""
    return await _global_cache.get_user_info(user_id, force_refresh)

async def bulk_preload_all_users() -> Dict[str, Any]:
    """Предзагрузка всех пользователей (для использования при старте бота)"""
    return await _global_cache.bulk_preload_all_users()

def get_cache_statistics() -> Dict[str, Any]:
    """Получить статистику кэша для мониторинга"""
    return _global_cache.get_cache_stats()

def print_cache_status():
    """Вывести статистику кэша в консоль"""
    try:
        stats = _global_cache.get_cache_stats()
        
        stats_block = (
            "\nСТАТИСТИКА КЭША ПОЛЬЗОВАТЕЛЕЙ\n"
            + "=" * 50 + "\n"
            f" Производительность:\n"
            f"   • Всего запросов: {stats.get('total_requests', 0)}\n"
            f"   • Попаданий в кэш: {stats.get('hits', 0)}\n"
            f"   • Промахов кэша: {stats.get('misses', 0)}\n"
            f"   • Hit Rate: {stats.get('hit_rate_percent', 0)}%\n"
            f"   • Размер кэша: {len(_global_cache._cache)}\n"
            + "=" * 50
        )
        logger.info(stats_block)
    except Exception as e:
        logger.error("ERROR in print_cache_status: %s", e)
        import traceback
        traceback.print_exc()

async def force_refresh_user_cache(user_id: int) -> Optional[Dict[str, Any]]:
    """Принудительное обновление конкретного пользователя"""
    return await _global_cache.force_refresh_user(user_id)
