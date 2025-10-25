import json
import os
import discord
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from utils.config_manager import load_config
from utils.message_manager import get_supplies_message


class SuppliesManager:
    """Менеджер для управления таймерами поставок"""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.data_file = "data/supplies_timers.json"
        self._ensure_data_file()
        
        # Объекты поставок по категориям (каждая категория = ряд кнопок)
        self.categories = {
            "army": {
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
            },
            "medical": {
                "gsmo": {
                    "name": "ГСМО",
                    "emoji": "💉"
                },
                "zmh": {
                    "name": "ЗМХ",
                    "emoji": "🧑‍⚕️"
                },
                "ms": {
                    "name": "МС", 
                    "emoji": "😷"
                },
                "cms": {
                    "name": "ЦМС", 
                    "emoji": "⚕️"
                }
            },
            "gov": {
                "finka": {
                    "name": "Финансовая поставка",
                    "emoji": "💰"
                }
            }
        }
        
        # Плоский словарь всех объектов для обратной совместимости
        self.objects = {}
        for category_key, category_objects in self.categories.items():
            self.objects.update(category_objects)
    
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
            print(get_supplies_message(0, "templates.errors.processing").format(object="загрузки данных поставок", error=e))
            return {"active_timers": {}}
    
    def _save_data(self, data: Dict[str, Any]):
        """Сохраняет данные в файл"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(get_supplies_message(0, "templates.errors.processing").format(object="сохранения данных поставок", error=e))
    
    def get_categories(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Возвращает все категории с объектами"""
        return self.categories
    
    def get_category_objects(self, category_key: str) -> Dict[str, Dict[str, str]]:
        """Возвращает объекты определенной категории"""
        return self.categories.get(category_key, {})
    
    def get_all_objects_for_choices(self) -> list:
        """Возвращает список всех объектов в формате для discord.app_commands.Choice"""
        choices = []
        for category_key, category_objects in self.categories.items():
            for object_key, object_info in category_objects.items():
                choice_name = f"{object_info['emoji']} {object_info['name']}"
                choices.append({
                    'name': choice_name,
                    'value': object_key
                })
        return choices
    
    async def start_timer(self, object_key: str, user) -> bool:
        """Запускает таймер для объекта"""
        try:
            if object_key not in self.objects:
                return False
            
            # Получаем канал уведомлений для удаления старых сообщений
            config = load_config()
            notification_channel_id = config.get('supplies', {}).get('notification_channel_id')
            notification_channel = None
            
            if notification_channel_id and self.bot:
                notification_channel = self.bot.get_channel(notification_channel_id)
            elif notification_channel_id and hasattr(user, 'guild'):
                notification_channel = user.guild.get_channel(notification_channel_id)
            
            # Удаляем все старые сообщения для этого объекта перед запуском нового таймера
            await self._delete_all_messages_for_object(object_key, notification_channel)
            
            # Проверяем, нет ли уже активного таймера
            if self.is_timer_active(object_key):
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
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка в start_timer(): {e}")
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
            print(get_supplies_message(0, "templates.errors.processing").format(object=f"проверки таймера для {object_key}", error=e))
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
            print(get_supplies_message(0, "templates.errors.processing").format(object=f"получения оставшегося времени для {object_key}", error=e))
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
            print(get_supplies_message(0, "templates.errors.processing").format(object="получения активных таймеров", error=e))
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
                print(get_supplies_message(0, "templates.status.completed").format(action=f"Таймер для {object_key} отменен"))
                return True
            else:
                print(f"⚠️ Активный таймер для {object_key} не найден")
                return False
                
        except Exception as e:
            print(get_supplies_message(0, "templates.errors.processing").format(object=f"отмены таймера для {object_key}", error=e))
            return False
    
    def get_timer_info(self, object_key: str) -> Optional[Dict[str, Any]]:
        """Возвращает информацию о конкретном таймере"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            return active_timers.get(object_key)
        except Exception as e:
            print(get_supplies_message(0, "templates.errors.processing").format(object=f"получения информации о таймере для {object_key}", error=e))
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
            print(get_supplies_message(0, "templates.errors.processing").format(object="получения истекших таймеров", error=e))
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
                print(get_supplies_message(0, "templates.status.completed").format(action=f"Сообщение {message_type} сохранено для {object_key} (ID: {message_id})"))
            
        except Exception as e:
            print(get_supplies_message(0, "templates.errors.processing").format(object="сохранения ID сообщения", error=e))
    
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
            print(f"🔍 Начинаем удаление сообщений для {object_key}")
            
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
            
            print(f"✅ Канал получен: {channel.id}")
            
            # Получаем название объекта для поиска
            object_info = self.objects.get(object_key, {})
            object_name = object_info.get('name', object_key)
            
            print(f"🔍 Ищем старые сообщения для объекта '{object_name}' в канале")
            
            # Ищем и удаляем все сообщения бота с упоминанием этого объекта
            deleted_count = 0
            try:
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
                                    
            except Exception as e:
                print(f"❌ Ошибка при получении истории канала: {e}")
                raise
                        
            if deleted_count > 0:
                print(f"✅ Удалено {deleted_count} старых сообщений для '{object_name}'")
            else:
                print(f"ℹ️ Старые сообщения для '{object_name}' не найдены")
                        
        except Exception as e:
            print(f"❌ Ошибка удаления старых сообщений для {object_key}: {e}")
            raise

    async def update_notification_messages(self, channel):
        """Обновляет стартовые сообщения в канале оповещений с актуальным временем"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            
            if not active_timers:
                return
            
            for object_key, timer_info in active_timers.items():
                notification_messages = timer_info.get("notification_messages", {})
                start_message_id = notification_messages.get("start_message_id")
                
                if not start_message_id:
                    continue
                
                try:
                    # Получаем сообщение
                    message = await channel.fetch_message(start_message_id)
                    
                    # Получаем актуальное оставшееся время
                    remaining_time = self.get_remaining_time(object_key)
                    
                    if remaining_time == "Истек" or remaining_time == "Не активен":
                        continue  # Таймер истек, сообщение скоро удалится
                    
                    # Получаем данные объекта
                    object_name = timer_info.get("object_name", object_key)
                    emoji = timer_info.get("emoji", "📦")
                    started_by_name = timer_info.get("started_by_name", "Неизвестно")
                    
                    # Создаем обновленный embed
                    embed = discord.Embed(
                        title=f"{emoji} Поставка **{object_name}** запущена",
                        description="",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    
                    embed.add_field(
                        name=f"⏰ Будет доступно через: **{remaining_time}**",
                        value="",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="👤 Запустил",
                        value=started_by_name,
                        inline=True
                    )
                    
                    embed.set_footer(text="Уведомление будет отправлено за несколько минут до конца таймера")
                    
                    # Обновляем сообщение (оставляем контент без изменений)
                    await message.edit(embed=embed)
                    
                except discord.NotFound:
                    # Сообщение удалено, очищаем ID
                    notification_messages["start_message_id"] = None
                    print(f"⚠️ Стартовое сообщение {start_message_id} для {object_key} не найдено")
                except Exception as e:
                    print(f"❌ Ошибка обновления сообщения {start_message_id} для {object_key}: {e}")
            
            # Сохраняем изменения (если были очищены ID)
            self._save_data(data)
            
        except Exception as e:
            print(f"❌ Ошибка обновления сообщений в канале оповещений: {e}")

    async def update_warning_messages(self, channel):
        """Обновляет сообщения с предупреждениями в канале оповещений с актуальным временем"""
        try:
            data = self._load_data()
            active_timers = data.get("active_timers", {})
            
            # Сначала обновляем активные таймеры
            for object_key, timer_info in active_timers.items():
                await self._update_warning_message_for_timer(channel, object_key, timer_info, data)
            
            # Затем ищем и обновляем сообщения от истекших таймеров
            await self._update_expired_warning_messages(channel)
            
            # Сохраняем изменения (если были убраны ID)
            self._save_data(data)
            
        except Exception as e:
            print(f"❌ Ошибка обновления сообщений предупреждений в канале оповещений: {e}")
    
    async def _update_warning_message_for_timer(self, channel, object_key, timer_info, data):
        """Обновляет warning сообщения для конкретного таймера"""
        try:
            notification_messages = timer_info.get("notification_messages", {})
            
            # Поддержка как единственной, так и множественной формы ID
            warning_message_id = notification_messages.get("warning_message_id")
            warning_message_ids = notification_messages.get("warning_message_ids", [])
            
            # Объединяем в список для обработки
            all_warning_ids = []
            if warning_message_id:
                all_warning_ids.append(warning_message_id)
            all_warning_ids.extend(warning_message_ids)
            
            if not all_warning_ids:
                return
            
            # Получаем актуальное оставшееся время
            remaining_time = self.get_remaining_time(object_key)
            
            # Получаем данные объекта
            object_name = timer_info.get("object_name", object_key)
            emoji = timer_info.get("emoji", "📦")
            
            # Обновляем каждое сообщение с предупреждением
            for message_id in all_warning_ids[:]:  # Копия списка для безопасного изменения
                print(f"🔍 Пытаемся обновить warning сообщение {message_id}")
                try:
                    # Получаем сообщение
                    message = await channel.fetch_message(message_id)
                    
                    # Определяем статус и цвет
                    if remaining_time == "Истек" or remaining_time == "Не активен":
                        # Таймер истек - делаем сообщение зеленым
                        embed = discord.Embed(
                            title="✅ Поставка готова к запуску!",
                            description=f"{emoji} **{object_name}** готов к новой поставке материалов!",
                            color=discord.Color.green(),
                            timestamp=datetime.now()
                        )
                        
                        embed.add_field(
                            name="🎯 Статус",
                            value=(
                                f"**Объект:** {object_name}\n"
                                f"**Статус:** Готов к запуску\n"
                            ),
                            inline=False
                        )
                    else:
                        # Таймер еще активен - обновляем оставшееся время
                        # Вычисляем минуты для отображения
                        if "ч" in remaining_time and "м" in remaining_time:
                            # Парсим время вида "1ч 30м"
                            parts = remaining_time.replace("ч", "").replace("м", "").split()
                            hours = int(parts[0]) if len(parts) > 0 else 0
                            minutes = int(parts[1]) if len(parts) > 1 else 0
                            total_minutes = hours * 60 + minutes
                        elif "ч" in remaining_time:
                            # Только часы "2ч"
                            hours = int(remaining_time.replace("ч", ""))
                            total_minutes = hours * 60
                        elif "м" in remaining_time:
                            # Только минуты "15м"
                            total_minutes = int(remaining_time.replace("м", ""))
                        else:
                            total_minutes = 0
                        
                        embed = discord.Embed(
                            title="⚠️ Скоро будет доступна поставка!",
                            description=f"{emoji} **{object_name}** будет готов через **{total_minutes} минут**!",
                            color=discord.Color.orange(),
                            timestamp=datetime.now()
                        )
                        
                        embed.add_field(
                            name="⏰ Предупреждение",
                            value=(
                                f"**Объект:** {object_name}\n"
                                f"**Осталось:** {remaining_time}\n"
                            ),
                            inline=False
                        )
                    
                    embed.set_footer(text="Система управления поставками")
                    
                    # Обновляем сообщение (оставляем контент без изменений)
                    await message.edit(embed=embed)
                    
                except discord.NotFound:
                    # Сообщение удалено, убираем ID из соответствующих списков
                    if message_id == warning_message_id:
                        notification_messages["warning_message_id"] = None
                        print(f"⚠️ Очищен warning_message_id {message_id} для {object_key}")
                    if message_id in warning_message_ids:
                        warning_message_ids.remove(message_id)
                        print(f"⚠️ Удален из warning_message_ids {message_id} для {object_key}")
                    print(f"⚠️ Сообщение предупреждения {message_id} для {object_key} не найдено")
                except Exception as e:
                    print(f"❌ Ошибка обновления сообщения предупреждения {message_id} для {object_key}: {e}")
                    
        except Exception as e:
            print(f"❌ Ошибка обновления warning сообщения для {object_key}: {e}")
    
    async def _update_expired_warning_messages(self, channel):
        """Ищет и обновляет warning сообщения от истекших таймеров"""
        try:
            # Ищем сообщения бота с предупреждениями в последних 100 сообщениях
            async for message in channel.history(limit=100):
                if (message.author == channel.guild.me and message.embeds and 
                    len(message.embeds) > 0 and message.embeds[0].title and
                    "⚠️ Скоро будет доступна поставка!" in message.embeds[0].title):
                    
                    embed = message.embeds[0]
                    description = embed.description or ""
                    
                    # Ищем название объекта и эмодзи в описании
                    for object_key, object_info in self.objects.items():
                        object_name = object_info["name"]
                        emoji = object_info["emoji"]
                        
                        if object_name in description and emoji in description:
                            # Проверяем, истек ли таймер для этого объекта
                            remaining_time = self.get_remaining_time(object_key)
                            
                            if remaining_time == "Не активен" or remaining_time == "Истек":
                                # Обновляем сообщение до статуса "готово"
                                print(f"🔄 Обновляем истекшее warning сообщение для {object_name}")
                                
                                new_embed = discord.Embed(
                                    title="✅ Поставка готова к запуску!",
                                    description=f"{emoji} **{object_name}** готов к новой поставке материалов!",
                                    color=discord.Color.green(),
                                    timestamp=datetime.now()
                                )
                                
                                new_embed.add_field(
                                    name="🎯 Статус",
                                    value=(
                                        f"**Объект:** {object_name}\n"
                                        f"**Статус:** Готов к запуску\n"
                                    ),
                                    inline=False
                                )
                                
                                new_embed.set_footer(text="Система управления поставками")
                                
                                try:
                                    await message.edit(embed=new_embed)
                                    print(f"✅ Обновлено истекшее warning сообщение для {object_name}")
                                except Exception as e:
                                    print(f"❌ Ошибка обновления истекшего warning сообщения: {e}")
                            break
                            
        except Exception as e:
            print(f"❌ Ошибка поиска истекших warning сообщений: {e}")
