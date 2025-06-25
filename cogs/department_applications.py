"""
Department Applications Cog - Slash commands for department application system
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional

from utils.config_manager import load_config
from utils.ping_manager import ping_manager
from forms.department_applications import DepartmentApplicationManager

logger = logging.getLogger(__name__)

class DepartmentApplicationsCog(commands.Cog):
    """Cog for department application system"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.manager = DepartmentApplicationManager(bot)
    
    async def cog_load(self):
        """Called when cog is loaded"""
        # Restore persistent views
        await self.manager.restore_persistent_views()
    
    @app_commands.command(name="setup-department-channel", description="Настроить канал для заявлений в подразделение")
    @app_commands.describe(
        department="Код подразделения (УВП, ССО, РОиО, ВК, МР)",
        channel="Канал для заявлений в подразделение"
    )
    @app_commands.choices(department=[
        app_commands.Choice(name="УВП - Учебно-Воспитательное Подразделение", value="УВП"),
        app_commands.Choice(name="ССО - Силы Специальных Операций", value="ССО"),
        app_commands.Choice(name="РОиО - Разведывательный Отдел и Оборона", value="РОиО"),
        app_commands.Choice(name="ВК - Военная Комендатура", value="ВК"),
        app_commands.Choice(name="МР - Медицинская Рота", value="МР")
    ])
    async def setup_department_channel(
        self, 
        interaction: discord.Interaction, 
        department: str,
        channel: discord.TextChannel
    ):
        """Setup department application channel"""
        try:
            # Check permissions
            if not await self._check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ У вас нет прав для настройки каналов подразделений.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # Validate channel permissions
            bot_member = interaction.guild.get_member(self.bot.user.id)
            if not bot_member:
                await interaction.followup.send(
                    "❌ Не удалось получить информацию о боте.",
                    ephemeral=True
                )
                return
            
            permissions = channel.permissions_for(bot_member)
            missing_perms = []
            
            if not permissions.send_messages:
                missing_perms.append("Отправка сообщений")
            if not permissions.embed_links:
                missing_perms.append("Встраивание ссылок")
            if not permissions.manage_messages:
                missing_perms.append("Управление сообщениями")
            if not permissions.add_reactions:
                missing_perms.append("Добавление реакций")
            
            if missing_perms:
                await interaction.followup.send(
                    f"❌ Боту не хватает следующих разрешений в канале {channel.mention}:\n"
                    f"• {chr(10).join(missing_perms)}",
                    ephemeral=True
                )
                return
            
            # Setup channel
            success = await self.manager.setup_department_channel(department, channel)
            
            if success:
                await interaction.followup.send(
                    f"✅ Канал {channel.mention} успешно настроен для заявлений в подразделение **{department}**!\n"
                    f"Постоянное сообщение с формой заявления создано и закреплено.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Не удалось настроить канал для подразделения **{department}**.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error setting up department channel: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при настройке канала.",
                ephemeral=True
            )
    
    @app_commands.command(name="department-status", description="Проверить статус настройки подразделений")
    async def department_status(self, interaction: discord.Interaction):
        """Check department setup status"""
        try:
            # Check permissions
            if not await self._check_moderator_permissions(interaction):
                await interaction.response.send_message(
                    "❌ У вас нет прав для просмотра статуса подразделений.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # Create status embed
            embed = await self.manager.create_application_summary_embed(interaction.guild)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error checking department status: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при проверке статуса подразделений.",
                ephemeral=True
            )
    
    @app_commands.command(name="setup-department-role", description="Настроить роль для подразделения")
    @app_commands.describe(
        department="Код подразделения",
        role="Роль подразделения"
    )
    @app_commands.choices(department=[
        app_commands.Choice(name="УВП", value="УВП"),
        app_commands.Choice(name="ССО", value="ССО"),
        app_commands.Choice(name="РОиО", value="РОиО"),
        app_commands.Choice(name="ВК", value="ВК"),
        app_commands.Choice(name="МР", value="МР")
    ])
    async def setup_department_role(
        self,
        interaction: discord.Interaction,
        department: str,
        role: discord.Role
    ):
        """Setup department role"""
        try:
            # Check permissions
            if not await self._check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ У вас нет прав для настройки ролей подразделений.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # Validate role hierarchy
            bot_member = interaction.guild.get_member(self.bot.user.id)
            if role.position >= bot_member.top_role.position:
                await interaction.followup.send(
                    f"❌ Роль {role.mention} находится выше роли бота в иерархии.\n"
                    f"Бот не сможет управлять этой ролью.",
                    ephemeral=True
                )
                return
            
            if role.managed:
                await interaction.followup.send(
                    f"❌ Роль {role.mention} управляется интеграцией и не может быть изменена ботом.",
                    ephemeral=True
                )
                return
            
            # Update config
            await self.manager.update_department_config(department, role_id=role.id)
            
            await interaction.followup.send(
                f"✅ Роль {role.mention} успешно настроена для подразделения **{department}**!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error setting up department role: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при настройке роли.",
                ephemeral=True
            )
    
    @app_commands.command(name="setup-department-pings", description="Настроить пинги для заявлений в подразделение")
    @app_commands.describe(
        department="Код подразделения",
        roles="Роли для пинга (через пробел)"
    )
    @app_commands.choices(department=[
        app_commands.Choice(name="УВП", value="УВП"),
        app_commands.Choice(name="ССО", value="ССО"),
        app_commands.Choice(name="РОиО", value="РОиО"),
        app_commands.Choice(name="ВК", value="ВК"),
        app_commands.Choice(name="МР", value="МР")
    ])
    async def setup_department_pings(
        self,
        interaction: discord.Interaction,
        department: str,
        roles: str
    ):
        """Setup ping roles for department applications"""
        try:
            # Check permissions
            if not await self._check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ У вас нет прав для настройки пингов подразделений.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # Parse role mentions
            role_ids = []
            role_mentions = roles.split()
            
            for mention in role_mentions:
                # Extract role ID from mention
                if mention.startswith('<@&') and mention.endswith('>'):
                    role_id = int(mention[3:-1])
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_ids.append(role_id)
                    else:
                        await interaction.followup.send(
                            f"❌ Роль {mention} не найдена.",
                            ephemeral=True
                        )
                        return
                else:
                    await interaction.followup.send(
                        f"❌ Неверный формат роли: {mention}. Используйте упоминания ролей.",
                        ephemeral=True
                    )
                    return
            
            if not role_ids:
                await interaction.followup.send(
                    "❌ Не указано ни одной действительной роли.",
                    ephemeral=True
                )
                return
            
            # Update ping settings
            ping_manager.set_ping_context(department, 'applications', role_ids)
            
            # Create confirmation message
            role_mentions_text = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_mentions_text.append(role.mention)
            
            await interaction.followup.send(
                f"✅ Пинги для заявлений в подразделение **{department}** настроены!\n"
                f"Роли для пинга: {' '.join(role_mentions_text)}",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error setting up department pings: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при настройке пингов.",
                ephemeral=True
            )
    
    @app_commands.command(name="migrate-ping-settings", description="Мигрировать старые настройки пингов в новую систему")
    async def migrate_ping_settings(self, interaction: discord.Interaction):
        """Migrate legacy ping settings to new system"""
        try:
            # Check permissions
            if not await self._check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ У вас нет прав для миграции настроек.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # Run migration
            from utils.ping_adapter import ping_adapter
            ping_adapter.migrate_legacy_pings_to_new_system(interaction.guild)
            
            # Validate compatibility
            is_compatible, issues = ping_adapter.validate_ping_system_compatibility(interaction.guild)
            
            embed = discord.Embed(
                title="🔄 Миграция настроек пингов",
                color=discord.Color.green() if is_compatible else discord.Color.orange()
            )
            
            if is_compatible:
                embed.description = "✅ Миграция завершена успешно! Все системы совместимы."
            else:
                embed.description = "⚠️ Миграция завершена с предупреждениями:"
                embed.add_field(
                    name="Обнаруженные проблемы",
                    value="\n".join(f"• {issue}" for issue in issues[:10]),  # Limit to 10 issues
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error migrating ping settings: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при миграции настроек.",
                ephemeral=True
            )
    
    async def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions"""
        config = load_config()
        administrators = config.get('administrators', {})
        
        # Check admin users
        if interaction.user.id in administrators.get('users', []):
            return True
        
        # Check admin roles
        user_role_ids = [role.id for role in interaction.user.roles]
        admin_role_ids = administrators.get('roles', [])
        
        return any(role_id in user_role_ids for role_id in admin_role_ids)
    
    async def _check_moderator_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has moderator permissions"""
        config = load_config()
        moderators = config.get('moderators', {})
        
        # Check moderator users
        if interaction.user.id in moderators.get('users', []):
            return True
        
        # Check moderator roles
        user_role_ids = [role.id for role in interaction.user.roles]
        moderator_role_ids = moderators.get('roles', [])
        
        return any(role_id in user_role_ids for role_id in moderator_role_ids)

async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(DepartmentApplicationsCog(bot))
