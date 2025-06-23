"""
User Data Caching System

Безопасная система кэширования данных пользователей для оптимизации
запросов к Google Sheets API и предотвращения таймаутов Discord.

Features:
- Временное кэширование в памяти с TTL
- Предзагрузка данных для часто используемых операций
- Безопасная обработка ошибок с fallback
- Статистика использования кэша
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple, List
from utils.user_database import UserDatabase


class UserDataCache:
    """Система кэширования данных пользователей"""
    
    def __init__(self):
        # Кэш данных пользователей: {user_id: user_data}
        self._cache: Dict[int, Dict[str, Any]] = {}
        
        # Время истечения кэша: {user_id: expiry_datetime}
        self._expiry: Dict[int, datetime] = {}
        
        # Статистика кэша
        self._stats = {
            'hits': 0,
            'misses': 0,
            'total_requests': 0,
            'cache_size': 0,
            'last_cleanup': datetime.now()
        }
        
        # Настройки
        self.CACHE_TTL = 300  # 5 минут TTL
        self.MAX_CACHE_SIZE = 1000  # Максимум записей в кэше
        self.CLEANUP_INTERVAL = 600  # Очистка каждые 10 минут
    
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
          # Проверяем, нужно ли принудительное обновление
        if not force_refresh and self._is_cached(user_id):
            self._stats['hits'] += 1
            print(f"📋 CACHE HIT: Данные пользователя {user_id} получены из кэша")
            cached_data = self._cache[user_id]
            return cached_data.copy() if cached_data is not None else None
          # Кэш пропуск - загружаем данные
        self._stats['misses'] += 1
        print(f"🔄 CACHE MISS: Загружаем данные пользователя {user_id} из базы")
        
        try:            # Используем оптимизированный batch-запрос если доступен
            try:
                from utils.sheets_optimization import get_user_fast_optimized
                user_data = await get_user_fast_optimized(user_id)
                print(f"🚀 FAST OPTIMIZED: Используем оптимизированный запрос для {user_id}")
            except ImportError:
                # Fallback на обычный UserDatabase
                user_data = await UserDatabase.get_user_info(user_id)
                print(f"📋 STANDARD: Используем стандартный запрос для {user_id}")
            
            if user_data:
                # Сохраняем в кэш
                self._store_in_cache(user_id, user_data)
                print(f"✅ CACHE STORE: Данные пользователя {user_id} сохранены в кэш")
                return user_data.copy() if user_data is not None else None
            else:
                # Сохраняем отрицательный результат (чтобы не запрашивать повторно)
                self._store_in_cache(user_id, None)
                print(f"⚠️ CACHE STORE: Пользователь {user_id} не найден, сохранен отрицательный результат")
                return None
                
        except Exception as e:
            print(f"❌ CACHE ERROR: Ошибка загрузки данных пользователя {user_id}: {e}")
            # Возвращаем устаревшие данные из кэша, если есть
            if user_id in self._cache:
                print(f"🔄 CACHE FALLBACK: Используем устаревшие данные для {user_id}")
                return self._cache[user_id].copy()
            return None
    
    def _is_cached(self, user_id: int) -> bool:
        """Проверить, есть ли действительные данные в кэше"""
        if user_id not in self._cache:
            return False
        
        if user_id not in self._expiry:
            return False
        
        return datetime.now() < self._expiry[user_id]
    
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
            print(f"🧹 CACHE CLEANUP: Удалено {len(expired_keys)} истекших записей")
        
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
        
        print(f"🧹 CACHE EVICTION: Удалено {min(count, len(sorted_entries))} старых записей")
        self._stats['cache_size'] = len(self._cache)
    
    def invalidate_user(self, user_id: int):
        """Принудительно удалить пользователя из кэша"""
        self._cache.pop(user_id, None)
        self._expiry.pop(user_id, None)
        self._stats['cache_size'] = len(self._cache)
        print(f"🗑️ CACHE INVALIDATE: Данные пользователя {user_id} удалены из кэша")
    
    def clear_cache(self):
        """Полностью очистить кэш"""
        self._cache.clear()
        self._expiry.clear()
        self._stats['cache_size'] = 0
        print("🗑️ CACHE CLEAR: Кэш полностью очищен")
    
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
        print(f"🔄 CACHE PRELOAD: Предзагрузка данных для {len(user_ids)} пользователей")
        
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
                
                try:
                    from utils.sheets_optimization import get_users_batch_optimized
                    print(f"🚀 BATCH PRELOAD: Используем batch-запрос для {len(missing_user_ids)} пользователей")
                    batch_results = await get_users_batch_optimized(missing_user_ids)
                    
                    # Сохраняем результаты в кэш и формируем ответ
                    for user_id, user_data in batch_results.items():
                        self._store_in_cache(user_id, user_data)
                        results[user_id] = user_data.copy() if user_data else None
                        
                except ImportError:
                    print(f"📋 STANDARD PRELOAD: Используем стандартные параллельные запросы")
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
                            print(f"❌ PRELOAD ERROR для {user_id}: {result}")
                            results[user_id] = None
                        else:
                            results[user_id] = result
                        
            except Exception as e:
                print(f"❌ PRELOAD BATCH ERROR: {e}")
        
        print(f"✅ CACHE PRELOAD завершена: {len(results)} пользователей обработано")
        return results
    
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
                print("🛑 CACHE CLEANUP TASK: Задача очистки остановлена")
                break
            except Exception as e:
                print(f"❌ CACHE CLEANUP ERROR: {e}")


# Глобальный экземпляр кэша
user_cache = UserDataCache()


# =================== УНИВЕРСАЛЬНЫЕ ФУНКЦИИ ДЛЯ ВСЕХ МОДУЛЕЙ ===================

# Глобальный экземпляр кэша для использования во всех модулях
_global_cache = UserDataCache()


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
        print(f"🗑️ CACHE INVALIDATE: Пользователь {user_id} удален из кэша")


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
    
    print(f"📦 CACHE PRELOAD: Предзагружено {len(user_ids)} пользователей")
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
