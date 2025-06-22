"""
Warehouse User Data Optimization

Специализированный модуль для оптимизации работы с данными пользователей
в системе складских запросов. Решает проблему таймаутов Discord при
длительной обработке модальных окон.

Features:
- Быстрый отклик на Discord interactions
- Предзагрузка данных для складских операций
- Фоновая обработка тяжелых операций
- Интеграция с системой кэширования
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from utils.user_cache import get_cached_user_info, preload_user_data
from utils.user_database import UserDatabase


class WarehouseUserDataManager:
    """Менеджер пользовательских данных для системы склада"""
    
    def __init__(self):
        self.preload_cache = {}  # Кэш предзагруженных данных для сессий
        
    async def get_user_data_fast(self, user_id: int) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Быстрое получение данных пользователя
        
        Args:
            user_id: Discord ID пользователя
            
        Returns:
            Tuple[user_data, is_from_cache] - данные и флаг источника
        """
        try:
            # Сначала пробуем из кэша
            user_data = await get_cached_user_info(user_id)
            
            if user_data is not None:
                return user_data, True
            
            # Если в кэше нет, делаем быстрый запрос
            print(f"⚡ FAST REQUEST: Быстрый запрос данных для {user_id}")
            user_data = await UserDatabase.get_user_info(user_id)
            
            return user_data, False
            
        except Exception as e:
            print(f"❌ FAST REQUEST ERROR: {e}")
            return None, False
    
    async def prepare_user_data_for_modal(self, user_id: int) -> Dict[str, str]:
        """
        Подготовить данные пользователя для автозаполнения модального окна
        
        Args:
            user_id: Discord ID пользователя
            
        Returns:
            Dict с данными для автозаполнения (name, static, placeholders)
        """
        try:
            user_data, from_cache = await self.get_user_data_fast(user_id)
            
            if user_data:
                name_value = user_data.get('full_name', '')
                static_value = user_data.get('static', '')
                
                # Указываем источник данных в placeholder
                source = "кэш" if from_cache else "база данных"
                
                return {
                    'name_value': name_value,
                    'static_value': static_value,
                    'name_placeholder': f"Данные из {source}: {name_value}" if name_value else "Введите ваше имя и фамилию",
                    'static_placeholder': f"Данные из {source}: {static_value}" if static_value else "Например: 123-456",
                    'has_data': bool(name_value or static_value),
                    'source': source
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
            print(f"❌ MODAL PREP ERROR: {e}")
            return {
                'name_value': '',
                'static_value': '',
                'name_placeholder': "Введите ваше имя и фамилию (ошибка загрузки данных)",
                'static_placeholder': "Например: 123-456",
                'has_data': False,
                'source': 'error'
            }
    
    async def get_user_position_and_rank(self, user_id: int) -> Tuple[str, str]:
        """
        Получить должность и звание пользователя
        
        Args:
            user_id: Discord ID пользователя
            
        Returns:
            Tuple[position, rank]
        """
        try:
            user_data, _ = await self.get_user_data_fast(user_id)
            
            if user_data:
                position = user_data.get('position', 'Не указано')
                rank = user_data.get('rank', 'Не указано')
                
                print(f"✅ USER ROLE DATA: {user_id} -> должность='{position}', звание='{rank}'")
                return position, rank
            else:
                print(f"⚠️ USER ROLE FALLBACK: Данные для {user_id} не найдены")
                return "Не указано", "Не указано"
                
        except Exception as e:
            print(f"❌ USER ROLE ERROR: {e}")
            return "Не указано", "Не указано"
    
    async def get_user_department(self, user_id: int) -> str:
        """
        Получить подразделение пользователя
        
        Args:
            user_id: Discord ID пользователя
            
        Returns:
            Название подразделения
        """
        try:
            user_data, _ = await self.get_user_data_fast(user_id)
            
            if user_data:
                department = user_data.get('department', 'Не определено')
                print(f"✅ USER DEPT DATA: {user_id} -> подразделение='{department}'")
                return department
            else:
                print(f"⚠️ USER DEPT FALLBACK: Данные для {user_id} не найдены")
                return "Не определено"
                
        except Exception as e:
            print(f"❌ USER DEPT ERROR: {e}")
            return "Не определено"
    
    async def get_complete_user_info(self, user_id: int) -> Dict[str, str]:
        """
        Получить полную информацию о пользователе
        
        Args:
            user_id: Discord ID пользователя
            
        Returns:
            Dict с полной информацией пользователя
        """
        try:
            user_data, from_cache = await self.get_user_data_fast(user_id)
            
            if user_data:
                return {
                    'full_name': user_data.get('full_name', ''),
                    'static': user_data.get('static', ''),
                    'position': user_data.get('position', 'Не указано'),
                    'rank': user_data.get('rank', 'Не указано'),
                    'department': user_data.get('department', 'Не определено'),
                    'source': 'cache' if from_cache else 'database',
                    'found': True
                }
            else:
                return {
                    'full_name': '',
                    'static': '',
                    'position': 'Не указано',
                    'rank': 'Не указано',
                    'department': 'Не определено',
                    'source': 'none',
                    'found': False
                }
                
        except Exception as e:
            print(f"❌ COMPLETE USER INFO ERROR: {e}")
            return {
                'full_name': '',
                'static': '',
                'position': 'Не указано',
                'rank': 'Не указано',
                'department': 'Не определено',
                'source': 'error',
                'found': False
            }
    
    def store_session_data(self, user_id: int, data: Dict[str, Any]):
        """Сохранить данные сессии для быстрого доступа"""
        self.preload_cache[user_id] = {
            'data': data,
            'timestamp': datetime.now()
        }
        print(f"💾 SESSION STORE: Данные сессии сохранены для {user_id}")
    
    def get_session_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные сессии"""
        session_data = self.preload_cache.get(user_id)
        if session_data:
            # Проверяем актуальность (5 минут)
            age = (datetime.now() - session_data['timestamp']).total_seconds()
            if age < 300:  # 5 минут
                print(f"📋 SESSION HIT: Данные сессии получены для {user_id}")
                return session_data['data']
            else:
                # Удаляем устаревшие данные
                del self.preload_cache[user_id]
                print(f"🗑️ SESSION EXPIRED: Устаревшие данные сессии удалены для {user_id}")
        
        return None
    
    def clear_session_data(self, user_id: int):
        """Очистить данные сессии пользователя"""
        if user_id in self.preload_cache:
            del self.preload_cache[user_id]
            print(f"🗑️ SESSION CLEAR: Данные сессии очищены для {user_id}")


# Глобальный экземпляр менеджера
warehouse_user_manager = WarehouseUserDataManager()


async def get_warehouse_user_data(user_id: int) -> Dict[str, str]:
    """
    Удобная функция для получения данных пользователя в складской системе
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Dict с данными пользователя
    """
    return await warehouse_user_manager.get_complete_user_info(user_id)


async def prepare_modal_data(user_id: int) -> Dict[str, str]:
    """
    Удобная функция для подготовки данных модального окна
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Dict с данными для автозаполнения
    """
    return await warehouse_user_manager.prepare_user_data_for_modal(user_id)


async def get_user_role_data(user_id: int) -> Tuple[str, str]:
    """
    Удобная функция для получения должности и звания
    
    Args:
        user_id: Discord ID пользователя
        
    Returns:
        Tuple[position, rank]
    """
    return await warehouse_user_manager.get_user_position_and_rank(user_id)
