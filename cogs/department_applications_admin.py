"""
Department applications admin commands
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging

from forms.department_applications.manager import DepartmentApplicationManager
from utils.config_manager import load_config

logger = logging.getLogger(__name__)

class DepartmentApplicationsAdmin(commands.Cog):
    """Admin commands for department applications system"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.app_manager = DepartmentApplicationManager(bot)
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        # Restore persistent views on startup (this will auto-create missing messages)
        logger.info("Loading department applications admin cog - restoring persistent views")
        await self.app_manager.restore_persistent_views()
        logger.info("Department applications system ready!")
    
    @app_commands.command(
        name="setup_department_channels",
        description="Проверить и настроить каналы заявлений для всех подразделений"
    )
    @app_commands.describe(
        refresh="Принудительно обновить все сообщения (удалить старые и создать новые)"
    )
    async def setup_department_channels(
        self, 
        interaction: discord.Interaction,
        refresh: bool = False
    ):
        """Check and setup application messages in all department channels"""
        
        # Check admin permissions
        if not await self._check_admin_permissions(interaction.user):
            await interaction.response.send_message(
                "❌ У вас нет прав для выполнения этой команды.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            if refresh:
                # Refresh all channels (force recreate)
                config = load_config()
                departments = config.get('departments', {})
                results = {}
                
                for dept_code in departments.keys():
                    success = await self.app_manager.refresh_department_channel(dept_code, interaction.guild)
                    results[dept_code] = "✅ Принудительно обновлено" if success else "❌ Ошибка"
            else:
                # Smart check and setup (normal mode)
                results = await self.app_manager.setup_all_department_channels(interaction.guild)
            
            # Create result embed
            embed = discord.Embed(
                title="� Проверка каналов заявлений",
                description="Результат проверки и настройки каналов подразделений:",
                color=discord.Color.green()
            )
            
            if not refresh:
                embed.add_field(
                    name="🤖 Автоматический режим",
                    value="Система проверила закрепленные сообщения и создала недостающие.\n"
                          "При каждом запуске бота это происходит автоматически.",
                    inline=False
                )
            
            for dept_code, result in results.items():
                embed.add_field(
                    name=f"{dept_code}",
                    value=result,
                    inline=True
                )
            
            if not results:
                embed.description = "❌ Нет настроенных каналов для подразделений."
                embed.color = discord.Color.red()
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting up department channels: {e}")
            await interaction.followup.send(
                f"❌ Произошла ошибка: {e}",
                ephemeral=True
            )
    
    @app_commands.command(
        name="refresh_department_channel",
        description="Обновить сообщение заявлений для конкретного подразделения"
    )
    @app_commands.describe(
        department="Код подразделения для обновления"
    )
    async def refresh_department_channel(
        self,
        interaction: discord.Interaction,
        department: str
    ):
        """Refresh application message for a specific department"""
        
        # Check admin permissions
        if not await self._check_admin_permissions(interaction.user):
            await interaction.response.send_message(
                "❌ У вас нет прав для выполнения этой команды.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            department = department.upper()
            success = await self.app_manager.refresh_department_channel(department, interaction.guild)
            
            if success:
                await interaction.followup.send(
                    f"✅ Сообщение для подразделения **{department}** обновлено!"
                )
            else:
                await interaction.followup.send(
                    f"❌ Не удалось обновить сообщение для **{department}**. "
                    f"Проверьте настройки канала.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error refreshing department channel: {e}")
            await interaction.followup.send(
                f"❌ Произошла ошибка: {e}",
                ephemeral=True
            )
    
    @refresh_department_channel.autocomplete('department')
    async def department_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for department codes"""
        config = load_config()
        departments = config.get('departments', {})
        
        choices = []
        for dept_code in departments.keys():
            if current.upper() in dept_code.upper():
                choices.append(app_commands.Choice(name=dept_code, value=dept_code))
        
        return choices[:25]  # Discord limit
    
    @app_commands.command(
        name="department_applications_status",
        description="Показать статус системы заявлений в подразделения"
    )
    async def department_applications_status(self, interaction: discord.Interaction):
        """Show status of department applications system"""
        
        # Check admin permissions
        if not await self._check_admin_permissions(interaction.user):
            await interaction.response.send_message(
                "❌ У вас нет прав для выполнения этой команды.",
                ephemeral=True
            )
            return
        
        try:
            embed = await self.app_manager.create_application_summary_embed(interaction.guild)
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing applications status: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка: {e}",
                ephemeral=True
            )
    
    async def _check_admin_permissions(self, user: discord.Member) -> bool:
        """Check if user has admin permissions"""
        config = load_config()
        administrators = config.get('administrators', {})
        
        # Check admin users
        if user.id in administrators.get('users', []):
            return True
        
        # Check admin roles
        user_role_ids = [role.id for role in user.roles]
        admin_role_ids = administrators.get('roles', [])
        
        return any(role_id in user_role_ids for role_id in admin_role_ids)

async def setup(bot: commands.Bot):
    """Setup the cog"""
    await bot.add_cog(DepartmentApplicationsAdmin(bot))
