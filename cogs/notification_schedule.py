"""
Commands for configuring notification schedules
"""
import discord
from discord import app_commands
from discord.ext import commands
from utils.config_manager import load_config, save_config
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class NotificationScheduleCommands(commands.Cog):
    """Cog for notification schedule configuration commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(
        name="set_notification_time", 
        description="Настроить время отправки ежедневных уведомлений (МСК)"
    )
    @app_commands.describe(
        hour="Час отправки (0-23)",
        minute="Минута отправки (0-59)"
    )
    async def set_notification_time(
        self, 
        interaction: discord.Interaction, 
        hour: app_commands.Range[int, 0, 23],
        minute: app_commands.Range[int, 0, 59] = 0
    ):
        """Set the daily notification time"""
        
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ У вас нет прав администратора для выполнения этой команды.",
                ephemeral=True
            )
            return
        
        try:
            # Load config and update notification schedule
            config = load_config()
            
            if 'notification_schedule' not in config:
                config['notification_schedule'] = {}
            
            config['notification_schedule']['hour'] = hour
            config['notification_schedule']['minute'] = minute
            
            save_config(config)
            
            # Format time display
            time_str = f"{hour:02d}:{minute:02d}"
            
            embed = discord.Embed(
                title="✅ Время уведомлений настроено",
                description=f"Ежедневные уведомления будут отправляться в **{time_str} МСК**",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="ℹ️ Примечание",
                value=(
                    "Изменения вступят в силу при следующем запуске планировщика.\n"
                    "Для немедленного применения перезапустите бота."
                ),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Log the change
            logger.info("Время уведомлений изменено на %s МСК пользователем {interaction.user}", time_str)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при настройке времени: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="show_notification_schedule", 
        description="Показать текущие настройки расписания уведомлений"
    )
    async def show_notification_schedule(self, interaction: discord.Interaction):
        """Show current notification schedule"""
        
        try:
            config = load_config()
            schedule_config = config.get('notification_schedule', {'hour': 21, 'minute': 0})
            
            hour = schedule_config.get('hour', 21)
            minute = schedule_config.get('minute', 0)
            time_str = f"{hour:02d}:{minute:02d}"
            
            # Count enabled notifications
            promotion_notifications = config.get('promotion_notifications', {})
            enabled_count = sum(1 for dept_config in promotion_notifications.values() 
                              if dept_config.get('enabled', False))
            total_count = len(promotion_notifications)
            
            embed = discord.Embed(
                title="🕐 Расписание уведомлений",
                description=f"Ежедневные уведомления отправляются в **{time_str} МСК**",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="📊 Статистика уведомлений",
                value=f"Включено: **{enabled_count}** из **{total_count}** подразделений",
                inline=False
            )
            
            # Show enabled departments
            if enabled_count > 0:
                enabled_depts = []
                dept_names = {
                    'va': 'ВА (Военная Академия)',
                    'vk': 'ВК (Военный Комиссариат)',
                    'uvp': 'УВП (Управление Военной Полиции)',
                    'sso': 'ССО (Силы Специальных Операций)',
                    'mr': 'МР (Медицинская Рота)',
                    'roio': 'РОиО (Рота Охраны и Обеспечения)'
                }
                
                for dept_code, dept_config in promotion_notifications.items():
                    if dept_config.get('enabled', False):
                        dept_name = dept_names.get(dept_code, dept_code.upper())
                        enabled_depts.append(f"• {dept_name}")
                
                embed.add_field(
                    name="✅ Включенные подразделения",
                    value="\n".join(enabled_depts),
                    inline=False
                )
            
            embed.add_field(
                name="🔧 Управление",
                value=(
                    "• `/set_notification_time` - изменить время\n"
                    "• `/settings` → Каналы → Отчёты на повышение - настроить уведомления"
                ),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при получении расписания: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="test_notification", 
        description="Отправить тестовое уведомление сейчас (только для администраторов)"
    )
    @app_commands.describe(
        department="Подразделение для тестирования"
    )
    @app_commands.choices(department=[
        app_commands.Choice(name="ВА (Военная Академия)", value="va"),
        app_commands.Choice(name="ВК (Военный Комиссариат)", value="vk"),
        app_commands.Choice(name="УВП (Управление Военной Полиции)", value="uvp"),
        app_commands.Choice(name="ССО (Силы Специальных Операций)", value="sso"),
        app_commands.Choice(name="МР (Медицинская Рота)", value="mr"),
        app_commands.Choice(name="РОиО (Рота Охраны и Обеспечения)", value="roio"),
    ])
    async def test_notification(
        self, 
        interaction: discord.Interaction, 
        department: str
    ):
        """Send a test notification immediately"""
        
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                " У вас нет прав администратора для выполнения этой команды.",
                ephemeral=True
            )
            return
        
        try:
            import os
            
            config = load_config()
            promotion_notifications = config.get('promotion_notifications', {})
            promotion_channels = config.get('promotion_report_channels', {})
            
            # Check if department has notification configured
            notification_config = promotion_notifications.get(department, {})
            if not notification_config.get('enabled', False):
                await interaction.response.send_message(
                    f"❌ Уведомления для {department.upper()} отключены или не настроены.",
                    ephemeral=True
                )
                return
            
            # Check if channel exists
            channel_id = promotion_channels.get(department)
            if not channel_id:
                await interaction.response.send_message(
                    f"❌ Канал для {department.upper()} не настроен.",
                    ephemeral=True
                )
                return
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    f"❌ Канал для {department.upper()} не найден.",
                    ephemeral=True
                )
                return
            
            # Get notification content
            text = notification_config.get('text')
            image_filename = notification_config.get('image')
            
            if not text and not image_filename:
                await interaction.response.send_message(
                    f"❌ Для {department.upper()} не настроен ни текст, ни изображение.",
                    ephemeral=True
                )
                return
            
            # Send notification exactly as configured
            file = None
            
            # Prepare image file if specified
            if image_filename:
                image_path = os.path.join('files', 'reports', image_filename)
                if os.path.exists(image_path):
                    file = discord.File(image_path, filename=image_filename)
                else:
                    await interaction.response.send_message(
                        f"⚠️ Изображение '{image_filename}' не найдено для {department.upper()}.",
                        ephemeral=True
                    )
                    return
            
            # Send message based on what admin configured
            if text and file:
                # Both text and image
                await channel.send(content=text, file=file)
            elif text:
                # Only text
                await channel.send(content=text)
            elif file:
                # Only image
                await channel.send(file=file)
            
            dept_names = {
                'va': 'ВА (Военная Академия)',
                'vk': 'ВК (Военный Комиссариат)',
                'uvp': 'УВП (Управление Военной Полиции)',
                'sso': 'ССО (Силы Специальных Операций)',
                'mr': 'МР (Медицинская Рота)',
                'roio': 'РОиО (Рота Охраны и Обеспечения)'
            }
            
            dept_name = dept_names.get(department, department.upper())
            
            await interaction.response.send_message(
                f"✅ Тестовое уведомление для {dept_name} отправлено в {channel.mention}",
                ephemeral=True
            )
            
            logger.info("Тестовое уведомление отправлено для %s пользователем {interaction.user}", department)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при отправке тестового уведомления: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(NotificationScheduleCommands(bot))