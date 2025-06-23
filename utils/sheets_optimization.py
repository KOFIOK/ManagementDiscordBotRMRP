"""
Оптимизированные функции для Google Sheets

Этот модуль содержит дополнительные оптимизированные функции для работы
с Google Sheets, которые используются системой кэширования.

Это отдельный модуль, чтобы не нарушать существующую логику в google_sheets.py
"""

import asyncio
from typing import Dict, List, Optional, Any
from utils.google_sheets import GoogleSheetsManager


class OptimizedSheetsManager:
    """Оптимизированный менеджер для работы с Google Sheets"""
    
    def __init__(self):
        self.base_manager = GoogleSheetsManager()
        self._batch_cache = {}  # Временный кэш для batch операций
    
    async def get_users_batch(self, user_ids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
        """
        Получить данные нескольких пользователей одним запросом
        
        Args:
            user_ids: Список Discord ID пользователей
            
        Returns:
            Dict {user_id: user_data} с результатами
        """
        try:
            from utils.user_database import UserDatabase
            
            # Получаем рабочий лист
            worksheet = self.base_manager.get_worksheet(UserDatabase.WORKSHEET_NAME)
            if not worksheet:
                print(f"❌ BATCH: Лист '{UserDatabase.WORKSHEET_NAME}' не найден")
                return {user_id: None for user_id in user_ids}
            
            print(f"🔄 BATCH: Загружаем данные для {len(user_ids)} пользователей")
            
            # Получаем все данные листа одним запросом
            all_records = await asyncio.to_thread(worksheet.get_all_records)
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
                            'rank': str(record.get('Звание', '')).strip(),  # ИСПРАВЛЕНО: 'Звание' вместо 'Воинское Звание'
                            'department': str(record.get('Подразделение', '')).strip(),
                            'position': str(record.get('Должность', '')).strip(),
                            'discord_id': discord_id_str
                        }
                    except ValueError:
                        continue  # Пропускаем некорректные Discord ID
            
            # Формируем результаты для запрошенных пользователей
            results = {}
            for user_id in user_ids:
                if user_id in users_index:
                    user_data = users_index[user_id]
                    # Создаем полное имя
                    user_data['full_name'] = f"{user_data['first_name']} {user_data['last_name']}".strip()
                    results[user_id] = user_data
                    print(f"✅ BATCH: Найден пользователь {user_id}: {user_data['full_name']}")
                else:
                    results[user_id] = None
                    print(f"⚠️ BATCH: Пользователь {user_id} не найден")
            
            print(f"✅ BATCH: Обработано {len(user_ids)} пользователей, найдено {len([r for r in results.values() if r])}")
            return results
            
        except Exception as e:
            print(f"❌ BATCH ERROR: {e}")
            import traceback
            traceback.print_exc()
            # Возвращаем пустые результаты при ошибке
            return {user_id: None for user_id in user_ids}
    
    async def get_user_fast(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Быстрое получение данных одного пользователя
        
        Args:
            user_id: Discord ID пользователя
            
        Returns:
            Dict с данными пользователя или None
        """
        try:
            # Используем batch метод для одного пользователя
            results = await self.get_users_batch([user_id])
            return results.get(user_id)
            
        except Exception as e:
            print(f"❌ FAST GET ERROR для {user_id}: {e}")
            return None
    
    async def preload_active_users(self, limit: int = 100) -> Dict[int, Dict[str, Any]]:
        """
        Предзагрузить данные наиболее активных пользователей
        
        Args:
            limit: Максимальное количество пользователей для загрузки
            
        Returns:
            Dict с данными загруженных пользователей
        """
        try:
            from utils.user_database import UserDatabase
            
            # Получаем рабочий лист
            worksheet = self.base_manager.get_worksheet(UserDatabase.WORKSHEET_NAME)
            if not worksheet:
                print(f"❌ PRELOAD: Лист '{UserDatabase.WORKSHEET_NAME}' не найден")
                return {}
            
            print(f"🔄 PRELOAD: Предзагружаем данные до {limit} пользователей")
            
            # Получаем все записи
            all_records = await asyncio.to_thread(worksheet.get_all_records)
            
            # Ограничиваем количество и формируем результат
            results = {}
            count = 0
            
            for record in all_records:
                if count >= limit:
                    break
                    
                discord_id_str = str(record.get('Discord ID', '')).strip()
                if discord_id_str:
                    try:
                        discord_id = int(discord_id_str)
                        user_data = {
                            'first_name': str(record.get('Имя', '')).strip(),
                            'last_name': str(record.get('Фамилия', '')).strip(),
                            'static': str(record.get('Статик', '')).strip(),
                            'rank': str(record.get('Воинское Звание', '')).strip(),
                            'department': str(record.get('Подразделение', '')).strip(),
                            'position': str(record.get('Должность', '')).strip(),
                            'discord_id': discord_id_str
                        }
                        user_data['full_name'] = f"{user_data['first_name']} {user_data['last_name']}".strip()
                        
                        results[discord_id] = user_data
                        count += 1
                        
                    except ValueError:
                        continue
            
            print(f"✅ PRELOAD: Предзагружено {len(results)} пользователей")
            return results
            
        except Exception as e:
            print(f"❌ PRELOAD ERROR: {e}")
            return {}


# Глобальный экземпляр оптимизированного менеджера
optimized_sheets = OptimizedSheetsManager()


async def get_users_batch_optimized(user_ids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
    """
    Удобная функция для batch получения пользователей
    
    Args:
        user_ids: Список Discord ID пользователей
        
    Returns:
        Dict с результатами
    """
    return await optimized_sheets.get_users_batch(user_ids)


async def get_user_fast_optimized(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Удобная функция для быстрого получения одного пользователя
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Dict с данными пользователя или None
    """
    return await optimized_sheets.get_user_fast(user_id)
