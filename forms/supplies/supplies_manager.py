import json
import os
import discord
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from utils.config_manager import load_config


class SuppliesManager:
    """Менеджер для управления таймерами поставок"""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.data_file = "data/supplies_timers.json"
        self._ensure_data_file()
        
        # Объекты поставок с их настройками
        self.objects = {
            "object_7": {
                "name": "Объект №7", 
                "emoji": "🏭"
            },
            "military_warehouses": {
                "name": "Военные Склады",
                "emoji": "📦" 
            },
            "radar_orbit": {
                "name": "РЛС Орбита",
                "emoji": "📡"
            }
        }
    
    def _ensure_data_file(self):
        """Создает файл данных если его нет"""
        os.makedirs("data", exist_ok=True)
        
        if not os.path.exists(self.data_file):
            initial_data = {
                "active_timers": {}
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
    
    def _load_data(self) -> Dict[str, Any]:
        """Загружает данные из файла"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка загрузки данных поставок: {e}")
            return {"active_timers": {}}
    
    def _save_data(self, data: Dict[str, Any]):
        """Сохраняет данные в файл"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения данных поставок: {e}")
    
    async def start_timer(self, object_key: str, user) -> bool:
        """Запускает таймер для объекта"""
        try:
            if object_key not in self.objects:
                print(f"❌ Неизвестный объект: {object_key}")
                return False
            
            # Получаем канал уведомлений для удаления старых сообщений
            config = load_config()
            notification_channel_id = config.get('supplies', {}).get('notification_channel_id')
            notification_channel = None
            
            if notification_channel_id and hasattr(user, 'guild'):
                notification_channel = user.guild.get_channel(notification_channel_id)
            
            # Удаляем все старые сообщения для этого объекта перед запуском нового таймера
            await self._delete_all_messages_for_object(object_key, notification_channel)
            
            # Проверяем, нет ли уже активного таймера
            if self.is_timer_active(object_key):
                print(f"⚠️ Таймер для {object_key} уже активен")
                return False
            
            config = load_config()
            # Поддерживаем обратную совместимость
            timer_duration_minutes = config.get('supplies', {}).get('timer_duration_minutes', 
                                             config.get('supplies', {}).get('timer_duration_hours', 4) * 60)
            
            # Создаем данные таймера
            now = datetime.now()
            end_time = now + timedelta(minutes=timer_duration_minutes)
            
            timer_data = {
                "started_by": user.id,
                "started_by_name": user.display_name,
                "start_time": now.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_minutes": timer_duration_minutes,
                "warning_sent": False,
                "object_name": self.objects[object_key]["name"],
                "emoji": self.objects[object_key]["emoji"],
                "notification_messages": {
                    "start_message_id": None,
                    "warning_message_id": None
                }
            }
            
            # Сохраняем таймер
            data = self._load_data()
            data["active_timers"][object_key] = timer_data
            self._save_data(data)
            
            # Форматируем длительность для лога
            hours = timer_duration_minutes // 60
            remaining_minutes = timer_duration_minutes % 60
            if hours > 0 and remaining_minutes > 0:
                duration_str = f"{hours}ч {remaining_minutes}м"
            elif hours > 0:
                duration_str = f"{hours}ч"
            else:
                duration_str = f"{remaining_minutes}м"
            
            print(f"✅ Таймер запущен для {object_key} на {duration_str}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка запуска таймера для {object_key}: {e}")
            return False
    
    def is_timer_active(self, object_key: str) -> bool:
        """Проверяет, активен ли таймер для объекта"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            
            if object_key not in active_timers:
                return False
            
            timer_info = active_timers[object_key]
            end_time = datetime.fromisoformat(timer_info["end_time"])
            
            # Если таймер истек, удаляем его
            if datetime.now() > end_time:
                del active_timers[object_key]
                self._save_data(data)
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка проверки таймера {object_key}: {e}")
            return False
    
    def get_remaining_time(self, object_key: str) -> str:
        """Возвращает оставшееся время в читаемом формате"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            
            if object_key not in active_timers:
                return "Не активен"
            
            timer_info = active_timers[object_key]
            end_time = datetime.fromisoformat(timer_info["end_time"])
            now = datetime.now()
            
            if now > end_time:
                return "Истек"
            
            remaining = end_time - now
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            
            if hours > 0:
                return f"{hours}ч {minutes}м"
            else:
                return f"{minutes}м"
                
        except Exception as e:
            print(f"❌ Ошибка получения оставшегося времени для {object_key}: {e}")
            return "Ошибка"
    
    def get_active_timers(self) -> Dict[str, Any]:
        """Возвращает все активные таймеры"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            
            # Удаляем истекшие таймеры
            current_time = datetime.now()
            expired_timers = []
            
            for object_key, timer_info in active_timers.items():
                end_time = datetime.fromisoformat(timer_info["end_time"])
                if current_time > end_time:
                    expired_timers.append(object_key)
            
            # Удаляем истекшие таймеры
            if expired_timers:
                for expired in expired_timers:
                    del active_timers[expired]
                self._save_data(data)
            
            return active_timers
            
        except Exception as e:
            print(f"❌ Ошибка получения активных таймеров: {e}")
            return {}
    
    async def cancel_timer_with_cleanup(self, object_key: str) -> bool:
        """Отменяет таймер для объекта и удаляет все связанные сообщения"""
        try:
            # Сначала удаляем все сообщения
            config = load_config()
            notification_channel_id = config.get('supplies', {}).get('notification_channel_id')
            
            if notification_channel_id and self.bot:
                channel = self.bot.get_channel(notification_channel_id)
                if channel:
                    await self._delete_all_messages_for_object(object_key, channel)
            
            # Затем отменяем таймер
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            
            if object_key in active_timers:
                del active_timers[object_key]
                self._save_data(data)
                print(f"✅ Таймер для {object_key} отменен и сообщения удалены")
                return True
            else:
                print(f"⚠️ Активный таймер для {object_key} не найден")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка отмены таймера с очисткой для {object_key}: {e}")
            return False
    
    def get_timer_info(self, object_key: str) -> Optional[Dict[str, Any]]:
        """Возвращает информацию о конкретном таймере"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            return active_timers.get(object_key)
        except Exception as e:
            print(f"❌ Ошибка получения информации о таймере {object_key}: {e}")
            return None
    
    def get_expired_timers(self) -> Dict[str, Any]:
        """Возвращает истекшие таймеры и удаляет их"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            current_time = datetime.now()
            expired_timers = {}
            
            # Находим истекшие таймеры
            for object_key, timer_info in list(active_timers.items()):
                end_time = datetime.fromisoformat(timer_info["end_time"])
                if current_time > end_time:
                    expired_timers[object_key] = timer_info
                    del active_timers[object_key]
            
            # Сохраняем обновленные данные
            if expired_timers:
                self._save_data(data)
            
            return expired_timers
            
        except Exception as e:
            print(f"❌ Ошибка получения истекших таймеров: {e}")
            return {}
    
    async def save_notification_message(self, object_key: str, message_id: int, message_type: str):
        """Сохраняет ID уведомительного сообщения"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            
            if object_key in active_timers:
                if "notification_messages" not in active_timers[object_key]:
                    active_timers[object_key]["notification_messages"] = {}
                
                active_timers[object_key]["notification_messages"][f"{message_type}_message_id"] = message_id
                self._save_data(data)
                print(f"✅ Сохранен ID сообщения {message_type} для {object_key}: {message_id}")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения ID сообщения: {e}")
    
    async def clear_warning_messages(self, channel):
        """Удаляет все сообщения с предупреждениями (с пингами ролей)"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            
            for object_key, timer_info in active_timers.items():
                notification_messages = timer_info.get("notification_messages", {})
                warning_message_id = notification_messages.get("warning_message_id")
                
                if warning_message_id:
                    try:
                        message = await channel.fetch_message(warning_message_id)
                        await message.delete()
                        print(f"✅ Удалено сообщение с предупреждением для {object_key}")
                    except discord.NotFound:
                        pass
                    except Exception as e:
                        print(f"❌ Ошибка удаления сообщения {warning_message_id}: {e}")
                    
                    # Очищаем ID
                    notification_messages["warning_message_id"] = None
            
            self._save_data(data)
            
        except Exception as e:
            print(f"❌ Ошибка очистки предупреждающих сообщений: {e}")
    
    async def clear_start_message(self, object_key: str, channel):
        """Удаляет стартовое сообщение объекта"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            
            if object_key in active_timers:
                notification_messages = active_timers[object_key].get("notification_messages", {})
                start_message_id = notification_messages.get("start_message_id")
                
                if start_message_id:
                    try:
                        message = await channel.fetch_message(start_message_id)
                        await message.delete()
                        print(f"✅ Удалено стартовое сообщение для {object_key}")
                    except discord.NotFound:
                        pass
                    except Exception as e:
                        print(f"❌ Ошибка удаления стартового сообщения {start_message_id}: {e}")
                    
                    # Очищаем ID
                    notification_messages["start_message_id"] = None
                    self._save_data(data)
            
        except Exception as e:
            print(f"❌ Ошибка удаления стартового сообщения: {e}")

    async def _delete_all_messages_for_object(self, object_key: str, channel=None):
        """Удаляет все существующие сообщения для объекта перед запуском нового таймера"""
        try:
            config = load_config()
            
            # Если channel не передан, получаем из конфигурации
            if not channel:
                channel_id = config.get('supplies', {}).get('notification_channel_id')
                
                if not channel_id or not self.bot:
                    print(f"⚠️ Не удалось получить канал для удаления сообщений {object_key}")
                    return
                
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    print(f"⚠️ Канал уведомлений {channel_id} не найден")
                    return
            
            # Получаем название объекта для поиска
            object_info = self.objects.get(object_key, {})
            object_name = object_info.get('name', object_key)
            
            print(f"🔍 Ищем старые сообщения для объекта '{object_name}' в канале")
            
            # Ищем и удаляем все сообщения бота с упоминанием этого объекта
            deleted_count = 0
            async for message in channel.history(limit=50):  # Проверяем последние 50 сообщений
                if message.author == channel.guild.me and message.embeds:
                    # Проверяем каждый embed на наличие названия объекта
                    for embed in message.embeds:
                        # Проверяем title и description
                        embed_text = (embed.title or '') + ' ' + (embed.description or '')
                        
                        if object_name in embed_text:
                            try:
                                await message.delete()
                                deleted_count += 1
                                print(f"🗑️ Удалено старое сообщение для {object_name}: {message.id}")
                                break  # Переходим к следующему сообщению
                            except (discord.NotFound, discord.HTTPException) as e:
                                print(f"⚠️ Не удалось удалить сообщение {message.id}: {e}")
                                
            if deleted_count > 0:
                print(f"✅ Удалено {deleted_count} старых сообщений для '{object_name}'")
            else:
                print(f"ℹ️ Старые сообщения для '{object_name}' не найдены")
                        
        except Exception as e:
            print(f"❌ Ошибка удаления старых сообщений для {object_key}: {e}")
