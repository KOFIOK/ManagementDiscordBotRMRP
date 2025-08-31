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
        
    async def sync_user(self, member: discord.Member, force: bool = False) -> bool:
        """Синхронизирует звание одного пользователя"""
        try:
            print(f"🔄 Синхронизация {member.display_name}...")
            
            # 1. Проверяем ключевую роль (если не force)
            if not force and not self._has_key_role(member):
                print(f"⚠️ {member.display_name} не имеет ключевой роли")
                return False
            
            # 2. Ищем RMRP активность
            rmrp_text = self._find_rmrp_activity(member)
            if not rmrp_text:
                print(f"❌ {member.display_name} не играет в RMRP")
                return False
            
            print(f"🎮 Найдена RMRP активность: {rmrp_text}")
            
            # 3. Извлекаем звание
            rank = self._extract_rank(rmrp_text)
            if not rank:
                print(f"❌ Звание не найдено в активности")
                return False
            
            print(f"🎖️ Обнаружено звание: {rank}")
            
            # 4. Синхронизируем роли
            success = await self._sync_roles(member, rank)
            
            if success:
                print(f"✅ {member.display_name} синхронизирован с званием {rank}")
                return True
            else:
                print(f"❌ Не удалось синхронизировать {member.display_name}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка синхронизации {member.display_name}: {e}")
            return False
    
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
        for activity in member.activities:
            # Проверяем все возможные поля активности
            activity_texts = []
            
            # Собираем все текстовые поля
            if hasattr(activity, 'name') and activity.name:
                activity_texts.append(activity.name)
            if hasattr(activity, 'details') and activity.details:
                activity_texts.append(activity.details)
            if hasattr(activity, 'state') and activity.state:
                activity_texts.append(activity.state)
            if hasattr(activity, 'large_text') and activity.large_text:
                activity_texts.append(activity.large_text)
            if hasattr(activity, 'small_text') and activity.small_text:
                activity_texts.append(activity.small_text)
            
            # Ищем RMRP в любом из полей
            for text in activity_texts:
                if self._is_rmrp_server(text):
                    return text
        
        return None
    
    def _is_rmrp_server(self, text: str) -> bool:
        """Проверяет, содержит ли текст информацию о сервере RMRP"""
        if not text:
            return False
        
        text_lower = text.lower()
        rmrp_indicators = [
            "rmrp.ru",
            "rmrp - арбат",
            "арбат",
            "rmrp",
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
    
    async def _sync_roles(self, member: discord.Member, rank: str) -> bool:
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
                return False
            
            target_role = member.guild.get_role(target_role_id)
            if not target_role:
                print(f"❌ Роль {target_role_id} не найдена на сервере")
                return False
            
            print(f"🎯 Целевая роль: {target_role.name}")
            
            # Проверяем, есть ли уже эта роль
            if target_role in member.roles:
                print(f"✅ {member.display_name} уже имеет роль {target_role.name}")
                return True
            
            # Удаляем другие роли званий
            roles_to_remove = []
            for role in member.roles:
                if role.id in rank_roles.values() and role.id != target_role_id:
                    roles_to_remove.append(role)
            
            if roles_to_remove:
                print(f"🗑️ Удаляем старые роли: {[r.name for r in roles_to_remove]}")
                await member.remove_roles(*roles_to_remove, reason="Синхронизация званий")
            
            # Добавляем новую роль
            print(f"➕ Добавляем роль: {target_role.name}")
            await member.add_roles(target_role, reason=f"Обнаружено звание: {rank}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка синхронизации ролей: {e}")
            return False
    
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
            success = await self.sync_user(member, force=False)
            if success:
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
