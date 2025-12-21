import discord
from discord.ext import commands
from datetime import datetime
from forms.supplies import SuppliesManager
from utils.config_manager import load_config
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class SuppliesCog(commands.Cog):
    """Команды управления системой поставок"""
    
    def __init__(self, bot):
        self.bot = bot
        self.supplies_manager = SuppliesManager(self.bot)

    async def supplies_object_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[discord.app_commands.Choice[str]]:
        """Автодополнение для объектов поставок"""
        try:
            choices = []
            for category_key, category_objects in self.supplies_manager.categories.items():
                for object_key, object_info in category_objects.items():
                    choice_name = f"{object_info['emoji']} {object_info['name']}"
                    # Фильтруем по введенному тексту
                    if current.lower() in choice_name.lower() or current.lower() in object_key.lower():
                        choices.append(discord.app_commands.Choice(name=choice_name, value=object_key))
                        
            # Ограничиваем до 25 вариантов (лимит Discord)
            return choices[:25]
        except Exception as e:
            logger.warning("Ошибка автодополнения объектов поставок: %s", e)
            return []
    
    @discord.app_commands.command(
        name="supplies-reset",
        description="Сбросить таймер для конкретного военного объекта"
    )
    @discord.app_commands.describe(
        объект="Выберите объект для сброса таймера"
    )
    @discord.app_commands.autocomplete(объект=supplies_object_autocomplete)
    async def supplies_reset(self, interaction: discord.Interaction, объект: str):
        """Сброс таймера для выбранного объекта"""
        try:
            # Проверяем права доступа (модераторы/администраторы или Discord-админы)
            config = load_config()
            moderator_role_ids = config.get('moderators', {}).get('roles', [])
            administrator_role_ids = config.get('administrators', {}).get('roles', [])
            
            user_role_ids = [role.id for role in interaction.user.roles]
            is_bot_moderator_or_admin = any(role_id in user_role_ids for role_id in moderator_role_ids + administrator_role_ids)
            is_discord_admin = interaction.user.guild_permissions.administrator
            
            if not (is_bot_moderator_or_admin or is_discord_admin):
                await interaction.response.send_message(
                    "❌ У вас нет прав для управления поставками.",
                    ephemeral=True
                )
                return
            
            # Получаем информацию об объекте
            object_info = self.supplies_manager.objects.get(объект)
            if not object_info:
                await interaction.response.send_message(
                    "❌ Неизвестный объект.",
                    ephemeral=True
                )
                return
            
            object_name = object_info["name"]
            emoji = object_info["emoji"]
            
            # Проверяем, есть ли активный таймер
            if not self.supplies_manager.is_timer_active(объект):
                await interaction.response.send_message(
                    f"ℹ️ {emoji} **{object_name}** не имеет активного таймера.",
                    ephemeral=True
                )
                return
            
            # Сбрасываем таймер и удаляем связанные сообщения
            success = await self.supplies_manager.cancel_timer_with_cleanup(объект)
            
            if success:
                await interaction.response.send_message(
                    f"✅ {emoji} Таймер для **{object_name}** успешно сброшен!\n"
                    f"👤 Сброшен: {interaction.user.mention}",
                    ephemeral=True
                )
                
                # Обновляем сообщение управления
                await self._update_control_message_after_reset()
            else:
                await interaction.response.send_message(
                    f"❌ Ошибка при сбросе таймера для **{object_name}**.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.warning("Ошибка в команде supplies-reset: %s", e)
            await interaction.response.send_message(
                "❌ Произошла ошибка при выполнении команды.",
                ephemeral=True
            )
    
    @discord.app_commands.command(
        name="supplies-setup",
        description="Создать сообщения системы поставок в настроенных каналах"
    )
    async def supplies_setup(self, interaction: discord.Interaction):
        """Создает сообщения поставок в настроенных каналах"""
        try:
            # Проверяем права доступа (администраторы или Discord-админы)
            config = load_config()
            administrator_role_ids = config.get('administrators', {}).get('roles', [])
            
            user_role_ids = [role.id for role in interaction.user.roles]
            is_bot_admin = any(role_id in user_role_ids for role_id in administrator_role_ids)
            is_discord_admin = interaction.user.guild_permissions.administrator
            
            if not (is_bot_admin or is_discord_admin):
                await interaction.response.send_message(
                    "❌ У вас нет прав для настройки системы поставок.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            supplies_config = config.get('supplies', {})
            
            # Создаем сообщение управления
            control_result = await self._setup_control_message(supplies_config)
            
            # Создаем сообщение подписки  
            subscription_result = await self._setup_subscription_message(supplies_config)
            
            # Формируем результат
            results = []
            if control_result:
                results.append(f"✅ {control_result}")
            if subscription_result:
                results.append(f"✅ {subscription_result}")
            
            if not results:
                results.append("❌ Не удалось создать сообщения - проверьте настройки каналов")
            
            message = "🚚 **Результат настройки системы поставок:**\n\n" + "\n".join(results)
            await interaction.followup.send(message, ephemeral=True)
            
        except Exception as e:
            logger.warning("Ошибка в команде supplies-setup: %s", e)
            await interaction.followup.send(
                "❌ Произошла ошибка при настройке системы поставок.",
                ephemeral=True
            )
    
    async def _setup_control_message(self, supplies_config: dict) -> str:
        """Создает сообщение управления поставками"""
        try:
            control_channel_id = supplies_config.get('control_channel_id')
            if not control_channel_id:
                return None
            
            channel = self.bot.get_channel(control_channel_id)
            if not channel:
                return None
            
            from forms.supplies.supplies_control_view import send_supplies_control_message
            message = await send_supplies_control_message(channel)
            
            if message:
                return f"Сообщение управления создано в #{channel.name}"
            return None
            
        except Exception as e:
            logger.warning("Ошибка создания сообщения управления: %s", e)
            return None
    
    async def _setup_subscription_message(self, supplies_config: dict) -> str:
        """Создает сообщение подписки"""
        try:
            subscription_channel_id = supplies_config.get('subscription_channel_id')
            if not subscription_channel_id:
                return None
            
            channel = self.bot.get_channel(subscription_channel_id)
            if not channel:
                return None
            
            from forms.supplies.supplies_subscription_view import send_supplies_subscription_message
            message = await send_supplies_subscription_message(channel)
            
            if message:
                return f"Сообщение подписки создано в #{channel.name}"
            return None
            
        except Exception as e:
            logger.warning("Ошибка создания сообщения подписки: %s", e)
            return None
    
    async def _update_control_message_after_reset(self):
        """Обновляет сообщение управления после сброса таймера"""
        try:
            from utils.supplies_restore import get_supplies_restore_manager
            restore_manager = get_supplies_restore_manager()
            if restore_manager:
                await restore_manager.update_control_message_timers()
        except Exception as e:
            logger.warning("Ошибка обновления сообщения управления после сброса: %s", e)
    
    @discord.app_commands.command(
        name="supplies-debug", 
        description="ℹ️ [DEV] Отладочная информация о системе поставок"
    )
    async def supplies_debug(self, interaction: discord.Interaction):
        """Показывает отладочную информацию о системе поставок"""
        try:
            # Проверяем права доступа (администраторы или Discord-админы)
            config = load_config()
            administrator_role_ids = config.get('administrators', {}).get('roles', [])
            
            user_role_ids = [role.id for role in interaction.user.roles]
            is_bot_admin = any(role_id in user_role_ids for role_id in administrator_role_ids)
            is_discord_admin = interaction.user.guild_permissions.administrator
            
            if not (is_bot_admin or is_discord_admin):
                await interaction.response.send_message(
                    "❌ У вас нет прав для отладки системы поставок.",
                    ephemeral=True
                )
                return
            
            # Собираем информацию
            supplies_config = config.get('supplies', {})
            active_timers = self.supplies_manager.get_active_timers()
            
            embed = discord.Embed(
                title="🔧 Отладка системы поставок",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            # Настройки каналов
            embed.add_field(
                name="📺 Каналы",
                value=(
                    f"🎮 Управление: {supplies_config.get('control_channel_id', 'Не настроен')}\n"
                    f"📢 Уведомления: {supplies_config.get('notification_channel_id', 'Не настроен')}\n"
                    f"🔔 Подписка: {supplies_config.get('subscription_channel_id', 'Не настроен')}"
                ),
                inline=False
            )
            
            # Настройки времени
            embed.add_field(
                name="⏰ Время",
                value=(
                    f"⏳ Таймер: {supplies_config.get('timer_duration_hours', 4)} ч.\n"
                    f"⚠️ Предупреждение: {supplies_config.get('warning_minutes', 20)} мин.\n"
                    f"🔔 Роль: {supplies_config.get('subscription_role_id', 'Не настроена')}"
                ),
                inline=True
            )
            
            # Активные таймеры
            if active_timers:
                timer_info = []
                for obj_key, timer_data in active_timers.items():
                    remaining = self.supplies_manager.get_remaining_time(obj_key)
                    timer_info.append(f"• {timer_data.get('emoji', '📦')} {timer_data.get('object_name', obj_key)}: {remaining}")
                
                embed.add_field(
                    name=f"⏰ Активные таймеры ({len(active_timers)})",
                    value="\n".join(timer_info) if timer_info else "Нет активных таймеров",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⏰ Активные таймеры",
                    value="🟢 Нет активных таймеров",
                    inline=False
                )
            
            # Состояние планировщика
            from utils.supplies_scheduler import get_supplies_scheduler
            scheduler = get_supplies_scheduler()
            scheduler_status = "🟢 Активен" if scheduler and scheduler.is_running else "🔴 Неактивен"
            
            embed.add_field(
                name="🤖 Планировщик",
                value=f"Статус: {scheduler_status}",
                inline=True
            )
            
            embed.set_footer(text="Отладочная информация системы поставок")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.warning("Ошибка в команде supplies-debug: %s", e)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении отладочной информации.",
                ephemeral=True
            )


async def setup(bot):
    """Функция загрузки cog"""
    await bot.add_cog(SuppliesCog(bot))
    logger.info("Supplies cog loaded successfully")