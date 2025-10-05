"""
Система восстановления сообщений поставок после перезапуска бота
"""

import discord
from typing import Optional, Dict, Any
from utils.config_manager import load_config
from forms.supplies.supplies_control_view import send_supplies_control_message
from forms.supplies.supplies_subscription_view import send_supplies_subscription_message


class SuppliesRestoreManager:
    """Менеджер восстановления сообщений системы поставок"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def restore_all_messages(self):
        """Восстанавливает все сообщения поставок"""
        try:
            config = load_config()
            supplies_config = config.get('supplies', {})
            
            print("🔄 Восстановление сообщений системы поставок...")
            
            # Восстанавливаем сообщение управления
            await self._restore_control_message(supplies_config)
            
            # Восстанавливаем сообщение подписки
            await self._restore_subscription_message(supplies_config)
            
            print("✅ Восстановление сообщений поставок завершено")
            
        except Exception as e:
            print(f"❌ Ошибка восстановления сообщений поставок: {e}")
    
    async def _restore_control_message(self, supplies_config: Dict[str, Any]):
        """Восстанавливает сообщение управления поставками"""
        try:
            control_channel_id = supplies_config.get('control_channel_id')
            if not control_channel_id:
                print("⚠️ Канал управления поставками не настроен")
                return
            
            channel = self.bot.get_channel(control_channel_id)
            if not channel:
                print(f"❌ Канал управления поставками не найден (ID: {control_channel_id})")
                return
            
            # Проверяем, есть ли уже сообщение
            has_message = await self._check_for_supplies_message(
                channel, 
                "Управление поставками"
            )
            
            if not has_message:
                print(f"📝 Создаем сообщение управления поставками в #{channel.name}")
                await send_supplies_control_message(channel)
            else:
                print(f"✅ Сообщение управления поставками уже существует в #{channel.name}")
                
        except Exception as e:
            print(f"❌ Ошибка восстановления сообщения управления: {e}")
    
    async def _restore_subscription_message(self, supplies_config: Dict[str, Any]):
        """Восстанавливает сообщение подписки на уведомления"""
        try:
            subscription_channel_id = supplies_config.get('subscription_channel_id')
            if not subscription_channel_id:
                print("⚠️ Канал подписки на поставки не настроен")
                return
            
            channel = self.bot.get_channel(subscription_channel_id)
            if not channel:
                print(f"❌ Канал подписки на поставки не найден (ID: {subscription_channel_id})")
                return
            
            # Проверяем, есть ли уже сообщение
            has_message = await self._check_for_supplies_message(
                channel, 
                "Подписка на уведомления о поставках"
            )
            
            if not has_message:
                print(f"📝 Создаем сообщение подписки на поставки в #{channel.name}")
                await send_supplies_subscription_message(channel)
            else:
                print(f"✅ Сообщение подписки на поставки уже существует в #{channel.name}")
                
        except Exception as e:
            print(f"❌ Ошибка восстановления сообщения подписки: {e}")
    
    async def _check_for_supplies_message(self, channel: discord.TextChannel, 
                                        title_keyword: str) -> bool:
        """Проверяет, есть ли уже сообщение поставок в канале"""
        try:
            # Проверяем последние 10 сообщений
            async for message in channel.history(limit=10):
                if message.author == self.bot.user and message.embeds:
                    for embed in message.embeds:
                        if embed.title and title_keyword in embed.title:
                            return True
            return False
        except Exception as e:
            print(f"❌ Ошибка проверки сообщений в #{channel.name}: {e}")
            return False
    
    async def update_control_message_timers(self):
        """Обновляет информацию о таймерах в сообщении управления"""
        try:
            config = load_config()
            control_channel_id = config.get('supplies', {}).get('control_channel_id')
            
            if not control_channel_id:
                return
            
            channel = self.bot.get_channel(control_channel_id)
            if not channel:
                return
            
            # Ищем сообщение управления поставками
            async for message in channel.history(limit=10):
                if (message.author == self.bot.user and message.embeds and 
                    len(message.embeds) >= 1 and message.embeds[0].title and 
                    "Управление поставками" in message.embeds[0].title):
                    
                    # Обновляем view с правильными состояниями кнопок
                    from forms.supplies.supplies_control_view import SuppliesControlView
                    new_view = SuppliesControlView()
                    new_view._update_button_states()
                    
                    # Создаем обновленный embed с таймерами
                    from forms.supplies.supplies_manager import SuppliesManager
                    from datetime import datetime
                    
                    supplies_manager = SuppliesManager()
                    active_timers = supplies_manager.get_active_timers()
                    
                    timer_embed = discord.Embed(
                        title="📊 Активные поставки",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    
                    if not active_timers:
                        timer_embed.description = "🟢 Все объекты готовы к поставке"
                    else:
                        for object_key, timer_info in active_timers.items():
                            object_name = timer_info.get('object_name', object_key)
                            emoji = timer_info.get('emoji', '📦')
                            started_by = timer_info.get('started_by_name', 'Неизвестно')
                            remaining = supplies_manager.get_remaining_time(object_key)
                            
                            timer_embed.add_field(
                                name=f"{emoji} {object_name}",
                                value=f"⏰ Осталось: **{remaining}**\n👤 Запустил: {started_by}",
                                inline=True
                            )
                    
                    # Обновляем сообщение с новым view и embeds
                    embeds = list(message.embeds)
                    if len(embeds) >= 2:
                        embeds[1] = timer_embed
                    else:
                        embeds.append(timer_embed)
                    
                    await message.edit(embeds=embeds, view=new_view)
                    break
            
            # Ищем сообщение управления
            async for message in channel.history(limit=10):
                if (message.author == self.bot.user and 
                    message.embeds and 
                    message.embeds[0].title and
                    "Управление поставками" in message.embeds[0].title):
                    
                    # Обновляем view с правильными состояниями кнопок
                    from forms.supplies.supplies_control_view import SuppliesControlView
                    new_view = SuppliesControlView()
                    new_view._update_button_states()
                    
                    # Создаем обновленный embed с таймерами
                    from forms.supplies.supplies_manager import SuppliesManager
                    from datetime import datetime
                    
                    supplies_manager = SuppliesManager()
                    active_timers = supplies_manager.get_active_timers()
                    
                    timer_embed = discord.Embed(
                        title="📊 Активные поставки",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    
                    if not active_timers:
                        timer_embed.description = "🟢 Все объекты готовы к поставке"
                    else:
                        for object_key, timer_info in active_timers.items():
                            object_name = timer_info.get('object_name', object_key)
                            emoji = timer_info.get('emoji', '📦')
                            started_by = timer_info.get('started_by_name', 'Неизвестно')
                            remaining = supplies_manager.get_remaining_time(object_key)
                            
                            timer_embed.add_field(
                                name=f"{emoji} {object_name}",
                                value=f"⏰ Осталось: **{remaining}**\n👤 Запустил: {started_by}",
                                inline=True
                            )
                    
                    # Обновляем сообщение с новым view и embeds
                    embeds = list(message.embeds)
                    if len(embeds) >= 2:
                        embeds[1] = timer_embed
                    else:
                        embeds.append(timer_embed)
                    
                    await message.edit(embeds=embeds, view=new_view)
                    break
                    
        except Exception as e:
            print(f"❌ Ошибка обновления таймеров в сообщении управления: {e}")


# Глобальный экземпляр для использования в других модулях
supplies_restore_manager: Optional[SuppliesRestoreManager] = None


def initialize_supplies_restore_manager(bot) -> SuppliesRestoreManager:
    """Инициализирует менеджер восстановления поставок"""
    global supplies_restore_manager
    
    try:
        supplies_restore_manager = SuppliesRestoreManager(bot)
        return supplies_restore_manager
    except Exception as e:
        print(f"❌ Ошибка инициализации менеджера восстановления поставок: {e}")
        return None


def get_supplies_restore_manager() -> Optional[SuppliesRestoreManager]:
    """Возвращает экземпляр менеджера восстановления поставок"""
    return supplies_restore_manager
