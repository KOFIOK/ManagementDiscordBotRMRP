"""
Новая система синхронизации званий - простая и эффективная
Логика: Если у пользователя есть ключевая роль И активность RMRP с званием - выдаем роль звания
"""
import discord
import re
import asyncio
from typing import Optional
from utils.config_manager import load_config


class RankSync:
    """Простая система синхронизации званий"""
    
    def __init__(self, bot):
        self.bot = bot
        
    async def sync_user(self, member: discord.Member, force: bool = False) -> dict:
        """Синхронизирует звание одного пользователя"""
        try:
            print(f"🔄 Синхронизация {member.display_name}...")
            
            # 1. Проверяем ключевую роль (если не force)
            if not force and not self._has_key_role(member):
                print(f"⚠️ {member.display_name} не имеет ключевой роли")
                return {
                    "success": False,
                    "error": "Нет ключевой роли"
                }
            
            # 2. Ищем RMRP активность
            rmrp_text = self._find_rmrp_activity(member)
            if not rmrp_text:
                print(f"❌ {member.display_name} не играет в RMRP")
                return {
                    "success": False,
                    "error": "RMRP активность не найдена"
                }
            
            print(f"🎮 Найдена RMRP активность: {rmrp_text}")
            
            # 3. Извлекаем звание
            rank = self._extract_rank(rmrp_text)
            if not rank:
                print(f"❌ Звание не найдено в активности")
                return {
                    "success": False,
                    "error": "Звание не обнаружено в активности",
                    "rmrp_activity": rmrp_text
                }
            
            print(f"🎖️ Обнаружено звание: {rank}")
            
            # 4. Синхронизируем роли
            result = await self._sync_roles(member, rank)
            
            if result["success"]:
                print(f"✅ {member.display_name} синхронизирован с званием {rank}")
                return {
                    "success": True,
                    "rank_detected": rank,
                    "rmrp_activity": rmrp_text,
                    "roles_added": result.get("roles_added", []),
                    "roles_removed": result.get("roles_removed", [])
                }
            else:
                print(f"❌ Не удалось синхронизировать {member.display_name}")
                return {
                    "success": False,
                    "error": result.get("error", "Ошибка синхронизации ролей"),
                    "rank_detected": rank,
                    "rmrp_activity": rmrp_text
                }
                
        except Exception as e:
            print(f"❌ Ошибка синхронизации {member.display_name}: {e}")
            return {
                "success": False,
                "error": f"Исключение: {str(e)}"
            }
    
    def _has_key_role(self, member: discord.Member) -> bool:
        """Проверяет, есть ли у пользователя ключевая роль"""
        config = load_config()
        key_role_id = config.get('rank_sync_key_role')
        
        if not key_role_id:
            print("ℹ️ Ключевая роль не настроена, пропускаем проверку")
            return True
        
        key_role = member.guild.get_role(key_role_id)
        if not key_role:
            print(f"⚠️ Ключевая роль {key_role_id} не найдена на сервере")
            return True
        
        has_role = key_role in member.roles
        print(f"🔑 Ключевая роль '{key_role.name}': {'✅' if has_role else '❌'}")
        return has_role
    
    def _find_rmrp_activity(self, member: discord.Member) -> Optional[str]:
        """Ищет RMRP активность в статусе пользователя"""
        print(f"🔍 Ищем активности у пользователя {member.display_name}")
        print(f"� Всего активностей: {len(member.activities)}")
        
        if not member.activities:
            print(f"❌ У пользователя {member.display_name} нет активностей")
            return None
        
        for i, activity in enumerate(member.activities):
            print(f"🔍 Активность #{i+1}: {activity.name} (тип: {type(activity).__name__})")
            print(f"   🆔 ID активности: {getattr(activity, 'application_id', 'Нет')}")
            print(f"   🎮 Тип активности: {getattr(activity, 'type', 'Неизвестно')}")
            
            # Собираем все текстовые поля для отладки
            if hasattr(activity, 'name') and activity.name:
                print(f"   📝 Name: '{activity.name}'")
            if hasattr(activity, 'details') and activity.details:
                print(f"   📋 Details: '{activity.details}'")
            if hasattr(activity, 'state') and activity.state:
                print(f"   📊 State: '{activity.state}'")
            if hasattr(activity, 'large_text') and activity.large_text:
                print(f"   🖼️ Large text: '{activity.large_text}'")
            if hasattr(activity, 'small_text') and activity.small_text:
                print(f"   🏷️ Small text: '{activity.small_text}'")
            if hasattr(activity, 'url'):
                print(f"   🔗 URL: '{activity.url}'")
            if hasattr(activity, 'platform'):
                print(f"   💻 Platform: '{activity.platform}'")
                
            # Выводим все доступные атрибуты активности для полной диагностики
            all_attrs = [attr for attr in dir(activity) if not attr.startswith('_') and not callable(getattr(activity, attr, None))]
            print(f"   🔧 Все атрибуты: {all_attrs}")
            
            # Ищем RMRP активность
            # Проверяем название игры на "RAGE Multiplayer"
            if hasattr(activity, 'name') and activity.name and 'rage multiplayer' in activity.name.lower():
                print(f"✅ Найдена RAGE Multiplayer активность!")
                # Если есть детали с RMRP сервером, возвращаем state (где звание)
                if hasattr(activity, 'details') and activity.details and self._is_rmrp_server(activity.details):
                    print(f"✅ Подтверждён RMRP сервер в details: {activity.details}")
                    # Возвращаем state, где находится информация о звании
                    if hasattr(activity, 'state') and activity.state:
                        print(f"✅ Используем state для извлечения звания: {activity.state}")
                        return activity.state
                    else:
                        print(f"⚠️ State не найден, используем details")
                        return activity.details
                else:
                    print(f"❌ Details не содержит RMRP индикаторы: {activity.details}")
                
            # Альтернативный поиск по любому полю с RMRP
            for attr in ['name', 'details', 'state', 'large_text', 'small_text']:
                if hasattr(activity, attr):
                    text = getattr(activity, attr, '')
                    if text and self._is_rmrp_server(text):
                        print(f"✅ Найден RMRP индикатор в {attr}: '{text}'")
                        # Если нашли RMRP в details, то ищем звание в state
                        if hasattr(activity, 'state') and activity.state and text != activity.state:
                            print(f"🎯 Используем state для звания: '{activity.state}'")
                            return activity.state
                        return text
        
        print(f"❌ RMRP активность не найдена у {member.display_name}")
        return None
    
    def _is_rmrp_server(self, text: str) -> bool:
        """Проверяет, содержит ли текст информацию о сервере RMRP"""
        if not text:
            return False
        
        text_lower = text.lower()
        rmrp_indicators = [
            "rmrp.ru",
            "rmrp",
            "арбат", 
            "rmrp.ru - арбат",
            "russian military roleplay"
        ]
        
        return any(indicator in text_lower for indicator in rmrp_indicators)
    
    def _extract_rank(self, activity_text: str) -> Optional[str]:
        """Извлекает звание из текста активности"""
        if not activity_text:
            return None
        
        # Словарь всех возможных вариантов званий
        rank_patterns = {
            # Рядовые
            'рядовой': r'\b(?:рядовой|рдв|р\.?)\b',
            'ефрейтор': r'\b(?:ефрейтор|еф|ефр\.?)\b',
            
            # Сержанты  
            'мл. сержант': r'\b(?:мл\.?\s*сержант|младший\s+сержант|мл\.?\s*сер\.?|мс)\b',
            'сержант': r'\b(?:сержант|сер\.?|с\.)\b',
            'ст. сержант': r'\b(?:ст\.?\s*сержант|старший\s+сержант|ст\.?\s*сер\.?|сс)\b',
            'старшина': r'\b(?:старшина|стар\.?|ст\.)\b',
            
            # Прапорщики
            'прапорщик': r'\b(?:прапорщик|прап\.?|пр\.?)\b',
            'ст. прапорщик': r'\b(?:ст\.?\s*прапорщик|старший\s+прапорщик|ст\.?\s*прап\.?|сп)\b',
            
            # Лейтенанты
            'мл. лейтенант': r'\b(?:мл\.?\s*лейтенант|младший\s+лейтенант|мл\.?\s*лт\.?|мл)\b',
            'лейтенант': r'\b(?:лейтенант|лт\.?|л\.?|лейт\.?)\b',
            'ст. лейтенант': r'\b(?:ст\.?\s*лейтенант|старший\s+лейтенант|ст\.?\s*лт\.?|сл)\b',
            
            # Высшие звания
            'капитан': r'\b(?:капитан|кап\.?|к\.?|капит\.?)\b',
            'майор': r'\b(?:майор|май\.?|м\.?)\b',
            'подполковник': r'\b(?:подполковник|пп|ппк)\b',
            'полковник': r'\b(?:полковник|п\.?|плк)\b',
            'генерал': r'\b(?:генерал.*?|ген\.?\s*.*?|гм|гл|гп|га)\b',
            'маршал': r'\b(?:маршал|мар\.?|мш)\b'
        }
        
        text_lower = activity_text.lower()
        
        # Ищем звание в тексте
        for rank, pattern in rank_patterns.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                print(f"🔍 Найдено совпадение '{rank}' по паттерну '{pattern}'")
                return rank
        
        print(f"❌ Звание не найдено в тексте: {activity_text}")
        return None
    
    async def _sync_roles(self, member: discord.Member, rank: str) -> dict:
        """Синхронизирует роли пользователя с обнаруженным званием"""
        try:
            config = load_config()
            rank_roles = config.get('rank_roles', {})
            
            # Ищем роль для звания (без учета регистра)
            target_role_id = None
            for config_rank, role_id in rank_roles.items():
                if config_rank.lower() == rank.lower():
                    target_role_id = role_id
                    break
            
            if not target_role_id:
                print(f"❌ Роль для звания '{rank}' не настроена")
                return {
                    "success": False,
                    "error": f"Роль для звания '{rank}' не настроена"
                }
            
            target_role = member.guild.get_role(target_role_id)
            if not target_role:
                print(f"❌ Роль {target_role_id} не найдена на сервере")
                return {
                    "success": False,
                    "error": f"Роль {target_role_id} не найдена на сервере"
                }
            
            print(f"🎯 Целевая роль: {target_role.name}")
            
            roles_added = []
            roles_removed = []
            
            # Проверяем, есть ли уже эта роль
            if target_role in member.roles:
                print(f"✅ {member.display_name} уже имеет роль {target_role.name}")
                return {
                    "success": True,
                    "roles_added": [],
                    "roles_removed": [],
                    "message": f"Роль {target_role.name} уже назначена"
                }
            
            # Удаляем другие роли званий
            roles_to_remove = []
            for role in member.roles:
                if role.id in rank_roles.values() and role.id != target_role_id:
                    roles_to_remove.append(role)
            
            if roles_to_remove:
                role_names = [r.name for r in roles_to_remove]
                print(f"🗑️ Удаляем старые роли: {role_names}")
                await member.remove_roles(*roles_to_remove, reason="Синхронизация званий")
                roles_removed = role_names
            
            # Добавляем новую роль
            print(f"➕ Добавляем роль: {target_role.name}")
            await member.add_roles(target_role, reason=f"Обнаружено звание: {rank}")
            roles_added = [target_role.name]
            
            return {
                "success": True,
                "roles_added": roles_added,
                "roles_removed": roles_removed
            }
            
        except Exception as e:
            print(f"❌ Ошибка синхронизации ролей: {e}")
            return {
                "success": False,
                "error": f"Ошибка синхронизации ролей: {str(e)}"
            }
    
    async def sync_all(self, guild: discord.Guild) -> tuple[int, int]:
        """Синхронизирует всех пользователей сервера"""
        print(f"🚀 Начинаю массовую синхронизацию сервера {guild.name}")
        
        config = load_config()
        key_role_id = config.get('rank_sync_key_role')
        
        # Фильтруем пользователей
        if key_role_id:
            key_role = guild.get_role(key_role_id)
            if key_role:
                members_to_sync = [m for m in guild.members if not m.bot and key_role in m.roles]
                print(f"🔑 Фильтрация по ключевой роли '{key_role.name}': {len(members_to_sync)} пользователей")
            else:
                members_to_sync = [m for m in guild.members if not m.bot]
                print(f"⚠️ Ключевая роль не найдена, синхронизируем всех: {len(members_to_sync)} пользователей")
        else:
            members_to_sync = [m for m in guild.members if not m.bot]
            print(f"ℹ️ Ключевая роль не настроена, синхронизируем всех: {len(members_to_sync)} пользователей")
        
        synced_count = 0
        
        for member in members_to_sync:
            result = await self.sync_user(member, force=False)
            if result.get("success"):
                synced_count += 1
            
            # Небольшая пауза для избежания rate limit
            await asyncio.sleep(0.1)
        
        print(f"✅ Массовая синхронизация завершена: {synced_count}/{len(members_to_sync)} пользователей")
        return synced_count, len(members_to_sync)


# Глобальный экземпляр
rank_sync = None

def initialize_rank_sync(bot):
    """Инициализирует систему синхронизации"""
    global rank_sync
    rank_sync = RankSync(bot)
    print("✅ Новая система синхронизации званий инициализирована")
    return rank_sync
