"""
Оптимизированные функции для Google Sheets

Этот модуль содержит дополнительные оптимизированные функции для работы
с Google Sheets, которые используются системой кэширования.

Это отдельный модуль, чтобы не нарушать существующую логику в google_sheets.py
"""

import asyncio
import time
import random
from typing import Dict, List, Optional, Any
from utils.google_sheets import GoogleSheetsManager
from utils.user_database import UserDatabase
import gspread


class OptimizedSheetsManager:
    """Оптимизированный менеджер для работы с Google Sheets"""
    
    def __init__(self, base_manager: GoogleSheetsManager):
        self.base_manager = base_manager
        # Глобальный счетчик запросов для контроля rate limiting
        self._request_count = 0
        self._request_window_start = time.time()
        self._max_requests_per_minute = 40  # Консервативный лимит (Google: 100/min)
        self._rate_limit_cooldown = False
        self._cooldown_until = 0
    
    async def _check_rate_limit(self):
        """Проверяет и контролирует rate limiting"""
        current_time = time.time()
        
        # Проверяем, находимся ли мы в состоянии cooldown
        if self._rate_limit_cooldown and current_time < self._cooldown_until:
            sleep_time = self._cooldown_until - current_time
            print(f"🛑 RATE LIMIT: Ждем {sleep_time:.2f}s до окончания cooldown")
            await asyncio.sleep(sleep_time)
            self._rate_limit_cooldown = False
        
        # Сброс окна запросов каждую минуту
        if current_time - self._request_window_start > 60:
            self._request_count = 0
            self._request_window_start = current_time
        
        # Проверяем лимит запросов
        if self._request_count >= self._max_requests_per_minute:
            sleep_time = 60 - (current_time - self._request_window_start)
            print(f"⏳ RATE LIMIT: Достигнут лимит {self._max_requests_per_minute} запросов/мин, ждем {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)
            self._request_count = 0
            self._request_window_start = time.time()
        
        self._request_count += 1
    
    async def _handle_rate_limit_error(self, error):
        """Обрабатывает 429 ошибку и устанавливает cooldown"""
        print(f"🚨 RATE LIMIT ERROR: {error}")
        self._rate_limit_cooldown = True
        self._cooldown_until = time.time() + 120  # 2 минуты cooldown
        print(f"⏰ COOLDOWN: Установлен cooldown на 2 минуты")
    
    async def _retry_with_exponential_backoff(self, func, max_retries=5, base_delay=1):
        """
        Выполняет функцию с retry и exponential backoff для обработки 429 ошибок
        """
        for attempt in range(max_retries):
            try:
                # Проверяем rate limit перед каждой попыткой
                await self._check_rate_limit()
                return await func()
            except gspread.exceptions.APIError as e:
                if e.response.status_code == 429:  # Quota exceeded
                    await self._handle_rate_limit_error(e)
                    
                    if attempt == max_retries - 1:
                        print(f"❌ RETRY: Превышено максимальное количество попыток ({max_retries})")
                        raise
                    
                    # Exponential backoff с jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"⏳ RETRY: Попытка {attempt + 1}/{max_retries}, ждем {delay:.2f}s из-за лимита API")
                    await asyncio.sleep(delay)
                else:
                    # Другие API ошибки - не повторяем
                    raise
            except Exception as e:
                # Неожиданные ошибки - не повторяем
                raise
    
    async def get_users_batch(self, user_ids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
        """
        Массовое получение пользователей из Google Sheets (оптимизированная версия)
        """
        try:
            # Получаем рабочий лист
            worksheet = self.base_manager.get_worksheet(UserDatabase.WORKSHEET_NAME)
            if not worksheet:
                print(f"❌ BATCH: Лист '{UserDatabase.WORKSHEET_NAME}' не найден")
                return {user_id: None for user_id in user_ids}
            
            print(f"🔄 BATCH: Загружаем данные для {len(user_ids)} пользователей")
            
            # Получаем все данные листа одним запросом с retry
            async def get_records():
                return await asyncio.to_thread(worksheet.get_all_records)
            
            all_records = await self._retry_with_exponential_backoff(get_records)
            
            # Создаем индекс по Discord ID для быстрого поиска
            users_index = {}
            for record in all_records:
                discord_id_str = str(record.get('Discord ID', '')).strip()
                if discord_id_str:
                    try:
                        discord_id = int(discord_id_str)
                        users_index[discord_id] = {
                            'first_name': str(record.get('Имя', '')).strip(),
                            'last_name': str(record.get('Фамилия', '')).strip(),
                            'static': str(record.get('Статик', '')).strip(),
                            'rank': str(record.get('Звание', '')).strip(),
                            'department': str(record.get('Подразделение', '')).strip(),
                            'position': str(record.get('Должность', '')).strip(),
                            'discord_id': discord_id
                        }
                    except (ValueError, TypeError):
                        continue
            
            # Формируем результат для запрошенных пользователей
            result = {}
            for user_id in user_ids:
                if user_id in users_index:
                    user_data = users_index[user_id]
                    # Формируем полное имя
                    user_data['full_name'] = f"{user_data['first_name']} {user_data['last_name']}".strip()
                    result[user_id] = user_data
                    print(f"✅ BATCH: Найден пользователь {user_id}: {user_data['full_name']}")
                else:
                    result[user_id] = None
                    print(f"❌ BATCH: Пользователь {user_id} не найден")
            
            print(f"📊 BATCH RESULT: {len([r for r in result.values() if r])}/{len(user_ids)} пользователей найдено")
            return result
            
        except Exception as e:
            print(f"❌ BATCH ERROR: {e}")
            return {user_id: None for user_id in user_ids}
    
    async def get_user_fast(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Быстрое получение одного пользователя"""
        batch_result = await self.get_users_batch([user_id])
        return batch_result.get(user_id)


# Глобальный экземпляр оптимизированного менеджера (ленивая инициализация)
_optimized_sheets = None

def get_optimized_sheets_manager():
    """Получить или создать экземпляр OptimizedSheetsManager с правильной инициализацией"""
    global _optimized_sheets
    
    if _optimized_sheets is None:
        try:
            from utils.google_sheets import GoogleSheetsManager
            
            # GoogleSheetsManager не принимает параметры в __init__
            base_manager = GoogleSheetsManager()
            base_manager.initialize()  # Инициализируем соединение
            _optimized_sheets = OptimizedSheetsManager(base_manager)
            print("✅ OPTIMIZED SHEETS: Инициализирован оптимизированный менеджер")
        except Exception as e:
            print(f"❌ OPTIMIZED SHEETS INIT ERROR: {e}")
            _optimized_sheets = None
    
    return _optimized_sheets


async def get_users_batch_optimized(user_ids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
    """
    Удобная функция для batch получения пользователей
    
    Args:
        user_ids: Список Discord ID пользователей
        
    Returns:
        Dict {user_id: user_data} с результатами
    """
    optimized_sheets = get_optimized_sheets_manager()
    if optimized_sheets is None:
        print("❌ FALLBACK: Используем стандартный UserDatabase")
        # Fallback на стандартный UserDatabase
        results = {}
        for user_id in user_ids:
            try:
                user_data = await UserDatabase.get_user_info(user_id)
                results[user_id] = user_data
            except Exception as e:
                print(f"❌ FALLBACK ERROR для {user_id}: {e}")
                results[user_id] = None
        return results
    
    return await optimized_sheets.get_users_batch(user_ids)


async def get_user_fast_optimized(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Удобная функция для быстрого получения одного пользователя
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Dict с данными пользователя или None
    """
    optimized_sheets = get_optimized_sheets_manager()
    if optimized_sheets is None:
        print("❌ FALLBACK: Используем стандартный UserDatabase")
        try:
            return await UserDatabase.get_user_info(user_id)
        except Exception as e:
            print(f"❌ FALLBACK ERROR для {user_id}: {e}")
            return None
    
    return await optimized_sheets.get_user_fast(user_id)
