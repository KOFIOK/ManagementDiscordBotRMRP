"""
Утилиты для управления системой склада
Включает в себя валидацию лимитов, определение должностей/званий и логику кулдауна
"""

import asyncio
import discord
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple, Any, List
import re
from .config_manager import load_config
from .google_sheets import GoogleSheetsManager

class WarehouseManager:
    def __init__(self, sheets_manager: GoogleSheetsManager):
        self.sheets_manager = sheets_manager
        
        # Категории предметов склада
        self.item_categories = {
            "Оружие": {
                "emoji": "🔫",
                "key": "оружие",
                "items": [
                    "АК-74М", "Кольт М16", "Кольт 416 Канада", "ФН СКАР-Т", 
                    "Штейр АУГ-А3", "Таурус Бешеный бык", "САР М249", 
                    "Таурус Бешенный бык МК2", "Обрез", "Тип 97", "Сайга-12К"
                ]
            },
            "Бронежилеты": {
                "emoji": "🦺", 
                "key": "бронежилеты",
                "items": [
                    "Средний бронежилет", "Тяжелый бронежилет",
                ]
            },
            "Медикаменты": {
                "emoji": "💊",
                "key": "медикаменты", 
                "items": [
                    "Армейская аптечка", "Обезболивающее", "Дефибриллятор", "Алкотестер"
                ]
            },
            "Другое": {
                "emoji": "📦",
                "key": "другое",
                "items": [
                    "Материалы", "Патроны", "Бодикамеры", "Прочее"
                ]
            }
        }        # Ограниченные виды оружия для определенных должностей
        self.restricted_weapons = [
            "Кольт М16", "Кольт 416 Канада", "ФН СКАР-Т", 
            "Штейр АУГ-А3", "Таурус Бешеный бык"
        ]

    def get_warehouse_channels(self) -> Tuple[Optional[int], Optional[int]]:
        """Получить каналы склада из конфигурации"""
        config = load_config()
        request_channel = config.get("warehouse_request_channel")
        audit_channel = config.get("warehouse_audit_channel")
        return request_channel, audit_channel
    
    def get_warehouse_submission_channel(self) -> Optional[int]:
        """Получить канал отправки заявок склада из конфигурации"""
        config = load_config()
        # Если настроен отдельный канал отправки, используем его
        # Иначе используем канал запросов как fallback
        submission_channel = config.get("warehouse_submission_channel")
        if submission_channel:
            return submission_channel
        
        fallback_channel = config.get("warehouse_request_channel")
        if fallback_channel:
            print("⚠️ warehouse_submission_channel не настроен, используется warehouse_request_channel как fallback")
        
        return fallback_channel

    def get_cooldown_hours(self) -> int:
        """Получить кулдаун в часах"""
        config = load_config()
        return config.get("warehouse_cooldown_hours", 6)

    def get_limits_mode(self) -> Dict[str, bool]:
        """Получить настройки режима лимитов"""
        config = load_config()
        return config.get("warehouse_limits_mode", {
            "positions_enabled": True,
            "ranks_enabled": False
        })

    def get_position_limits(self) -> Dict[str, Dict[str, Any]]:
        """Получить лимиты по должностям"""
        config = load_config()
        return config.get("warehouse_limits_positions", {})

    def get_rank_limits(self) -> Dict[str, Dict[str, Any]]:
        """Получить лимиты по званиям"""
        config = load_config()
        return config.get("warehouse_limits_ranks", {})

    async def check_user_cooldown(self, user_id: int, channel: discord.TextChannel, user: discord.Member = None) -> Tuple[bool, Optional[datetime]]:
        """
        Проверить кулдаун пользователя с учетом статуса заявки
        Кулдаун применяется только если последняя заявка одобрена или на рассмотрении
        Если отклонена - можно подавать новую сразу
        Модераторы и администраторы обходят кулдаун полностью
        Возвращает (can_request, next_available_time_moscow)
        """
        # Проверка bypass кулдауна для модераторов/администраторов
        if user and await self._user_can_bypass_cooldown(user):
            return True, None
        
        cooldown_hours = self.get_cooldown_hours()
        moscow_tz = timezone(timedelta(hours=3))  # UTC+3 для Москвы
        
        # Ищем последнее сообщение с заявкой этого пользователя
        found_message = False
        async for message in channel.history(limit=200):
            # Ищем сообщения с embed'ами о заявках склада
            if (message.embeds and 
                "Запрос склада" in message.embeds[0].title and
                message.embeds[0].footer and
                f"ID пользователя: {user_id}" in message.embeds[0].footer.text):
                found_message = True
                
                embed = message.embeds[0]
                
                # Определяем статус заявки по цвету embed'а и полям
                status = "pending"  # По умолчанию - на рассмотрении
                
                if embed.color:
                    if embed.color.value == discord.Color.green().value:
                        status = "approved"  # Одобрена
                    elif embed.color.value == discord.Color.red().value:
                        status = "rejected"  # Отклонена
                
                # Дополнительная проверка по полям embed'а
                for field in embed.fields:
                    if field.name:
                        if "✅ Одобрено" in field.name:
                            status = "approved"
                            break
                        elif "❌ Отклонено" in field.name:
                            status = "rejected"
                            break
                
                print(f"📋 COOLDOWN CHECK: Найдена заявка со статусом '{status}'")
                
                # Если заявка отклонена - кулдаун не применяется
                if status == "rejected":
                    return True, None
                
                # Для одобренных и на рассмотрении заявок проверяем время
                # Конвертируем время сообщения в московское время
                message_time_utc = message.created_at.replace(tzinfo=None)
                message_time_moscow = message_time_utc + timedelta(hours=3)  # UTC -> Moscow
                current_time_moscow = datetime.now(moscow_tz).replace(tzinfo=None)
                
                time_since = current_time_moscow - message_time_moscow
                
                if time_since < timedelta(hours=cooldown_hours):
                    next_time_moscow = message_time_moscow + timedelta(hours=cooldown_hours)
                    print(f"❌ COOLDOWN CHECK: Кулдаун активен! Следующий запрос: {next_time_moscow.strftime('%Y-%m-%d %H:%M:%S')} МСК")
                    return False, next_time_moscow
                break
        
        if not found_message:
            print(f"✅ COOLDOWN CHECK: Предыдущих заявок не найдено, можно делать запрос")
        
        return True, None

    async def get_user_info(self, user: discord.Member) -> Tuple[str, str, str, str]:
        """
        Получить информацию о пользователе (имя, статик, должность, звание)
        Сначала ищет в Google Sheets (лист "Личный Состав"), потом в ролях Discord
        """
        try:
            # Используем UserDatabase для поиска в Google Sheets с защитой от rate limiting
            from utils.user_cache import get_cached_user_info
            
            # Retry с защитой от API ошибок
            user_data = None
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    user_data = await get_cached_user_info(user.id)
                    break  # Успешно получили данные
                except Exception as e:
                    if "429" in str(e) or "Quota exceeded" in str(e):
                        # Rate limiting - ждем и повторяем
                        wait_time = 2 ** attempt  # Exponential backoff
                        print(f"⏳ RATE LIMIT в get_user_info: ждем {wait_time}s, попытка {attempt + 1}/{max_retries}")
                        await asyncio.sleep(wait_time)
                        if attempt == max_retries - 1:
                            print(f"❌ Не удалось получить данные пользователя после {max_retries} попыток")
                            user_data = None
                    else:
                        # Другая ошибка - прекращаем попытки
                        print(f"❌ Ошибка получения данных пользователя: {e}")
                        user_data = None
                        break
            
            if user_data:
                # Структура UserDatabase: first_name, last_name, static, rank, department, position, discord_id
                full_name = user_data.get('full_name', '')
                static = user_data.get('static', '')
                rank = user_data.get('rank', '').strip()
                department = user_data.get('department', '')
                position = user_data.get('position', '')
                
                # Если звание пустое, пробуем извлечь из ролей Discord
                if not rank:
                    rank = self._extract_rank_from_roles(user)
                    print(f"🔄 Звание из ролей Discord для {user.display_name}: '{rank}'")
                
                print(f"✅ USER ROLE DATA: {user.id} -> должность='{position}', звание='{rank}'")
                
                if full_name and static:
                    print(f"✅ UserDatabase: Найдены данные для {user.display_name}: {full_name} | {static} | {position} | {rank}")
                    return full_name, static, position, rank
                else:
                    print(f"⚠️ UserDatabase: Данные неполные для {user.display_name}: имя='{full_name}', статик='{static}'")
        except Exception as e:
            print(f"❌ Ошибка при поиске в UserDatabase: {e}")
            import traceback
            traceback.print_exc()

        # Fallback: извлечение из никнейма и ролей Discord
        print(f"📋 Данные не найдены в UserDatabase для {user.display_name}, используем роли Discord")
        name = self._extract_name_from_nickname(user)
        static = self._extract_static_from_nickname(user)
        position = self._extract_position_from_roles(user)
        rank = self._extract_rank_from_roles(user)
        
        print(f"📋 Fallback данные для {user.display_name}: имя='{name}', статик='{static}', должность='{position}', звание='{rank}'")
        return name, static, position, rank

    def _extract_name_from_nickname(self, user: discord.Member) -> str:
        """Извлечь имя из никнейма Discord"""
        display_name = user.display_name
        
        # Паттерны для извлечения имени
        patterns = [
            r'^\[.*?\]\s*(.+)',  # [Должность] Имя Фамилия
            r'^!!\[.*?\]\s*(.+)',  # !![Звание] Имя Фамилия  
            r'^.*?\|\s*(.+)',  # Статик | Имя Фамилия
            r'^(.+)'  # Просто имя
        ]
        
        for pattern in patterns:
            match = re.search(pattern, display_name.strip())
            if match:
                return match.group(1).strip()
        
        return user.display_name

    def _extract_static_from_nickname(self, user: discord.Member) -> str:
        """Извлечь статик из никнейма Discord"""
        display_name = user.display_name
        
        # Поиск статика в формате XXX-XXX или XXXXXX
        static_pattern = r'(\d{2,3}[-\s]?\d{3})'
        match = re.search(static_pattern, display_name)
        if match:
            static = match.group(1).replace(' ', '-').replace('--', '-')
            return static
        
        return ""

    def _extract_position_from_roles(self, user: discord.Member) -> str:
        """Извлечь должность из ролей Discord"""
        position_keywords = [
            "Оперативник ССО", "Старший сотрудник охраны", "Сотрудник охраны", 
            "Младший сотрудник охраны", "Военный врач", "Помощник врача",
            "Старший инспектор ВП", "Дознаватель ВП", "Инспектор ВП",
            "Старший инструктор"
        ]
        
        for role in user.roles:
            for keyword in position_keywords:
                if keyword.lower() in role.name.lower():
                    return keyword
        
        return ""

    def _extract_rank_from_roles(self, user: discord.Member) -> str:
        """Извлечь звание из ролей Discord"""
        rank_keywords = [
            "Рядовой", "Ефрейтор", "Младший сержант", "Сержант", "Старший сержант",
            "Старшина", "Прапорщик", "Старший прапорщик", "Младший лейтенант",
            "Лейтенант", "Старший лейтенант", "Капитан", "Майор", "Подполковник", "Полковник"
        ]
        
        for role in user.roles:
            for keyword in rank_keywords:
                if keyword.lower() in role.name.lower():
                    return keyword
        
        return ""

    def get_user_limits(self, position: str, rank: str) -> Dict[str, Any]:
        """
        Получить лимиты для пользователя на основе должности или звания
        """
        limits_mode = self.get_limits_mode()
        
        # Если все лимиты отключены - без ограничений
        if not limits_mode.get("positions_enabled", True) and not limits_mode.get("ranks_enabled", False):
            return {
                "оружие": 999,
                "бронежилеты": 999,
                "аптечки": 999,
                "weapon_restrictions": []
            }
        
        # Проверка лимитов по должности (приоритет)
        if limits_mode.get("positions_enabled", True) and position:
            position_limits = self.get_position_limits()
            if position in position_limits:
                return position_limits[position]
        
        # Проверка лимитов по званию (fallback)
        if limits_mode.get("ranks_enabled", False) and rank:
            rank_limits = self.get_rank_limits()
            if rank in rank_limits:
                return rank_limits[rank]
        
        # Базовые лимиты по умолчанию
        return {
            "оружие": 2,
            "бронежилеты": 10,
            "аптечки": 20,
            "weapon_restrictions": []
        }

    def validate_item_request(self, category_key: str, item_name: str, quantity: int, 
                            position: str, rank: str, current_cart_items: List = None) -> Tuple[bool, int, str]:
        """
        Валидировать запрос предмета с учетом уже добавленных в корзину
        Возвращает (is_valid, corrected_quantity, message)
        """
        user_limits = self.get_user_limits(position, rank)
        
        # Подсчитываем уже существующие предметы данного типа в корзине
        existing_quantity = 0
        if current_cart_items:
            for cart_item in current_cart_items:
                if self._items_are_same_type(category_key, item_name, cart_item.category, cart_item.item_name):
                    existing_quantity += cart_item.quantity
        
        # Специальная обработка для разных категорий
        if category_key == "оружие":
            max_weapons = user_limits.get("оружие", 3)
            weapon_restrictions = user_limits.get("weapon_restrictions", [])
            
            # Проверка ограничений на тип оружия
            if weapon_restrictions and item_name not in weapon_restrictions:
                return False, 0, f"❌ Вам недоступен данный тип оружия. Доступно: {', '.join(weapon_restrictions)}"
            
            # Проверка общего количества (существующие + новые)
            total_quantity = existing_quantity + quantity
            if total_quantity > max_weapons:
                # Корректируем количество с учетом уже имеющихся
                corrected_quantity = max_weapons - existing_quantity
                if corrected_quantity <= 0:
                    return False, 0, f"❌ Превышен лимит оружия ({max_weapons}). В корзине уже: {existing_quantity}"
                return True, corrected_quantity, f"Количество уменьшено до максимально возможного: {corrected_quantity} (лимит: {max_weapons}, в корзине: {existing_quantity})"
            
        elif category_key == "бронежилеты":
            max_armor = user_limits.get("бронежилеты", 15)
            
            # Проверка общего количества (существующие + новые)
            total_quantity = existing_quantity + quantity
            if total_quantity > max_armor:
                # Корректируем количество с учетом уже имеющихся
                corrected_quantity = max_armor - existing_quantity
                if corrected_quantity <= 0:
                    return False, 0, f"❌ Превышен лимит бронежилетов ({max_armor}). В корзине уже: {existing_quantity}"
                return True, corrected_quantity, f"Количество уменьшено до максимально возможного: {corrected_quantity} (лимит: {max_armor}, в корзине: {existing_quantity})"
                
        elif category_key == "медикаменты":
            if item_name == "Армейская аптечка":
                max_medkits = user_limits.get("аптечки", 20)
                
                # Проверка общего количества (существующие + новые)
                total_quantity = existing_quantity + quantity
                if total_quantity > max_medkits:
                    # Корректируем количество с учетом уже имеющихся
                    corrected_quantity = max_medkits - existing_quantity
                    if corrected_quantity <= 0:
                        return False, 0, f"❌ Превышен лимит аптечек ({max_medkits}). В корзине уже: {existing_quantity}"
                    return True, corrected_quantity, f"Количество уменьшено до максимально возможного: {corrected_quantity} (лимит: {max_medkits}, в корзине: {existing_quantity})"
                
        elif category_key == "другое":
            if item_name == "Материалы":
                # Проверка общего количества материалов
                total_quantity = existing_quantity + quantity
                if total_quantity > 1000:
                    # Корректируем количество с учетом уже имеющихся
                    corrected_quantity = 1000 - existing_quantity
                    if corrected_quantity <= 0:
                        return False, 0, f"❌ Превышен лимит материалов (1000). В корзине уже: {existing_quantity}"
                    return True, corrected_quantity, f"Количество уменьшено до максимально возможного: {corrected_quantity} (лимит: 1000, в корзине: {existing_quantity})"
        
        return True, quantity, "✅ Запрос корректен"

    def get_ping_roles_for_warehouse_request(self, user: discord.Member, department: str) -> list:
        """
        Получить роли для пинга в warehouse request на основе подразделения пользователя
        """
        from utils.config_manager import load_config
        
        config = load_config()
        ping_settings = config.get('ping_settings', {})
        
        ping_roles = []
        user_role_ids = [role.id for role in user.roles]
        
        # Проверяем каждую настройку пингов
        for dept_role_id_str, ping_role_ids in ping_settings.items():
            dept_role_id = int(dept_role_id_str)
            
            # Если у пользователя есть эта роль подразделения, добавляем соответствующие пинг-роли
            if dept_role_id in user_role_ids:
                for ping_role_id in ping_role_ids:
                    ping_role = user.guild.get_role(ping_role_id)
                    if ping_role and ping_role not in ping_roles:
                        ping_roles.append(ping_role)
                break  # Нашли подразделение, прерываем поиск
        
        return ping_roles
    
    def format_warehouse_request_embed(self, user: discord.Member, name: str, static: str,
                                     category: str, item_name: str, quantity: int,
                                     position: str, rank: str, department: str) -> discord.Embed:
        """Создать embed для запроса склада"""
        embed = discord.Embed(
            title="📦 Запрос склада",
            description=f"## {user.mention}",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        # Информация о пользователе - объединяем имя и статик
        embed.add_field(
            name="� Имя | Статик", 
            value=f"{name or 'Не указано'} | {static or 'Не указан'}", 
            inline=False
        )
        
        # Подразделение, должность, звание в правильном порядке
        embed.add_field(name="� Подразделение", value=department or "Не определено", inline=True)
        embed.add_field(name="� Должность", value=position or "Не указано", inline=True)
        embed.add_field(name="🎖️ Звание", value=rank or "Не указано", inline=True)
        
        # Добавляем пустое поле для разделения
        embed.add_field(name="\u200b", value="\u200b", inline=False)
            
        embed.add_field(name="📦 Категория", value=category, inline=True)
        embed.add_field(name="📋 Предмет", value=item_name, inline=True)
        embed.add_field(name="🔢 Количество", value=str(quantity), inline=True)
        
        embed.set_footer(text=f"ID пользователя: {user.id}")
        
        return embed

    def format_warehouse_audit_embed(self, user: discord.Member, moderator: discord.Member,
                                   name: str, static: str, category: str, item_name: str,
                                   quantity: int, position: str, rank: str) -> discord.Embed:
        """Создать embed для аудита склада"""
        embed = discord.Embed(
            title="📊 Аудит склада - Выдача",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="👤 Получатель", value=f"{user.mention}\n({name})", inline=True)
        embed.add_field(name="🆔 Статик", value=static or "Не указан", inline=True)
        embed.add_field(name="👮 Выдал", value=moderator.mention, inline=True)
        
        if position:
            embed.add_field(name="💼 Должность", value=position, inline=True)
        if rank:
            embed.add_field(name="🎖️ Звание", value=rank, inline=True)
            
        embed.add_field(name="📦 Выдано", value=f"{item_name} - {quantity} шт.", inline=False)
        
        embed.set_footer(text="Система аудита склада ВС РФ")
        
        return embed
    
    def _items_are_same_type(self, category_key1: str, item_name1: str, 
                           category2: str, item_name2: str) -> bool:
        """
        Определить, относятся ли предметы к одному типу для проверки лимитов
        Каждый конкретный предмет имеет свой отдельный лимит
        """
        # Приводим категории к единому формату (ключ)
        category_key2 = None
        for cat_name, cat_data in self.item_categories.items():
            if cat_name == category2:
                category_key2 = cat_data["key"]
                break
        
        if not category_key2:
            return False
        
        # Предметы считаются одного типа только если:
        # 1. Они из одной категории И
        # 2. Имеют одинаковое название
        return (category_key1 == category_key2) and (item_name1 == item_name2)

    async def _user_can_bypass_cooldown(self, user: discord.Member) -> bool:
        """
        Проверить, может ли пользователь обходить кулдаун склада
        Модераторы и администраторы могут подавать заявки без ограничений по времени
        """
        try:
            from utils.moderator_auth import has_moderator_permissions, has_admin_permissions
            
            # Администраторы могут всегда обходить кулдаун
            if await has_admin_permissions(user, user.guild):
                print(f"🛡️ COOLDOWN BYPASS: Администратор {user.display_name} обходит кулдаун")
                return True
            
            # Модераторы могут всегда обходить кулдаун  
            elif await has_moderator_permissions(user, user.guild):
                print(f"👮 COOLDOWN BYPASS: Модератор {user.display_name} обходит кулдаун")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Ошибка при проверке прав bypass кулдауна: {e}")
            # В случае ошибки - не даем bypass (безопасность)
            return False
