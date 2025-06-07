import discord
from discord import app_commands
from discord.ext import commands

from forms.settings_form import send_settings_message

class ChannelManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings", description="⚙️ Настройка каналов Discord бота")
    @app_commands.checks.has_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        """Unified command for bot configuration with interactive interface"""
        await send_settings_message(interaction)

    # Error handling for commands
    @settings.error
    async def settings_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ У вас нет прав для выполнения этой команды. Требуются права администратора.", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Произошла ошибка: {error}", 
                ephemeral=True
            )
            print(f"Settings command error: {error}")

# Setup function for adding the cog to the bot
async def setup(bot):
    await bot.add_cog(ChannelManagementCog(bot))
