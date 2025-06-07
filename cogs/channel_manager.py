import discord
from discord import app_commands
from discord.ext import commands

from utils.config_manager import load_config, save_config
from forms.dismissal_form import send_dismissal_button_message
from forms.audit_form import send_audit_button_message
from forms.blacklist_form import send_blacklist_button_message

class ChannelManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set-dismissal-channel", description="Установить канал для рапортов на увольнение")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_dismissal_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_config()
        config['dismissal_channel'] = channel.id
        save_config(config)
        
        # Send message with button to the configured channel
        await send_dismissal_button_message(channel)
        
        await interaction.response.send_message(
            f"Канал для рапортов на увольнение установлен: {channel.mention}\nСообщение с кнопкой для отправки рапортов было добавлено в канал.", 
            ephemeral=True
        )

    @app_commands.command(name="set-audit-channel", description="Установить канал для кадрового аудита")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_audit_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_config()
        config['audit_channel'] = channel.id
        save_config(config)
        
        # Send message with button to the configured channel
        await send_audit_button_message(channel)
        
        await interaction.response.send_message(
            f"Канал для кадрового аудита установлен: {channel.mention}\nСообщение с кнопкой для добавления записей аудита было добавлено в канал.", 
            ephemeral=True
        )

    @app_commands.command(name="set-blacklist-channel", description="Установить канал для чёрного списка")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_blacklist_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_config()
        config['blacklist_channel'] = channel.id
        save_config(config)
        
        # Send message with button to the configured channel
        await send_blacklist_button_message(channel)
        
        await interaction.response.send_message(
            f"Канал для чёрного списка установлен: {channel.mention}\nСообщение с кнопкой для добавления записей в чёрный список было добавлено в канал.", 
            ephemeral=True
        )

    @app_commands.command(name="show-channels", description="Показать настроенные каналы")
    @app_commands.checks.has_permissions(administrator=True)
    async def show_channels(self, interaction: discord.Interaction):
        config = load_config()
        
        # Create response message
        response = "**Настроенные каналы:**\n"
        
        # Add dismissal channel info
        if config['dismissal_channel']:
            channel = self.bot.get_channel(config['dismissal_channel'])
            response += f"Рапорт на увольнение: {channel.mention if channel else 'Канал не найден'}\n"
        else:
            response += "Рапорт на увольнение: Не настроен\n"
        
        # Add audit channel info
        if config['audit_channel']:
            channel = self.bot.get_channel(config['audit_channel'])
            response += f"Кадровый аудит: {channel.mention if channel else 'Канал не найден'}\n"
        else:
            response += "Кадровый аудит: Не настроен\n"
        
        # Add blacklist channel info
        if config['blacklist_channel']:
            channel = self.bot.get_channel(config['blacklist_channel'])
            response += f"Чёрный список: {channel.mention if channel else 'Канал не найден'}\n"
        else:
            response += "Чёрный список: Не настроен\n"
        
        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(name="recreate-dismissal-button", description="Пересоздать сообщение с кнопкой для рапортов на увольнение")
    @app_commands.checks.has_permissions(administrator=True)
    async def recreate_dismissal_button(self, interaction: discord.Interaction):
        config = load_config()
        dismissal_channel_id = config.get('dismissal_channel')
        
        if not dismissal_channel_id:
            await interaction.response.send_message(
                "Ошибка: канал для рапортов на увольнение не настроен. Сначала используйте команду /set-dismissal-channel", 
                ephemeral=True
            )
            return
            
        channel = self.bot.get_channel(dismissal_channel_id)
        if not channel:
            await interaction.response.send_message(
                "Ошибка: не удалось найти канал для рапортов. Возможно, канал был удален или бот не имеет к нему доступа.", 
                ephemeral=True
            )
            return
        
        await send_dismissal_button_message(channel)
        
        await interaction.response.send_message(
            f"Сообщение с кнопкой для отправки рапортов на увольнение было добавлено в канал {channel.mention}", 
            ephemeral=True
        )

    @app_commands.command(name="recreate-audit-button", description="Пересоздать сообщение с кнопкой для кадрового аудита")
    @app_commands.checks.has_permissions(administrator=True)
    async def recreate_audit_button(self, interaction: discord.Interaction):
        config = load_config()
        audit_channel_id = config.get('audit_channel')
        
        if not audit_channel_id:
            await interaction.response.send_message(
                "Ошибка: канал для кадрового аудита не настроен. Сначала используйте команду /set-audit-channel", 
                ephemeral=True
            )
            return
            
        channel = self.bot.get_channel(audit_channel_id)
        if not channel:
            await interaction.response.send_message(
                "Ошибка: не удалось найти канал для аудита. Возможно, канал был удален или бот не имеет к нему доступа.", 
                ephemeral=True
            )
            return
        
        await send_audit_button_message(channel)
        
        await interaction.response.send_message(
            f"Сообщение с кнопкой для кадрового аудита было добавлено в канал {channel.mention}", 
            ephemeral=True
        )

    @app_commands.command(name="recreate-blacklist-button", description="Пересоздать сообщение с кнопкой для чёрного списка")
    @app_commands.checks.has_permissions(administrator=True)
    async def recreate_blacklist_button(self, interaction: discord.Interaction):
        config = load_config()
        blacklist_channel_id = config.get('blacklist_channel')
        
        if not blacklist_channel_id:
            await interaction.response.send_message(
                "Ошибка: канал для чёрного списка не настроен. Сначала используйте команду /set-blacklist-channel", 
                ephemeral=True
            )
            return
            
        channel = self.bot.get_channel(blacklist_channel_id)
        if not channel:
            await interaction.response.send_message(
                "Ошибка: не удалось найти канал для чёрного списка. Возможно, канал был удален или бот не имеет к нему доступа.",
                ephemeral=True
            )
            return
        
        await send_blacklist_button_message(channel)
        
        await interaction.response.send_message(
            f"Сообщение с кнопкой для чёрного списка было добавлено в канал {channel.mention}", 
            ephemeral=True
        )

    @app_commands.command(name="recreate-all-buttons", description="Пересоздать все сообщения с кнопками во всех настроенных каналах")
    @app_commands.checks.has_permissions(administrator=True)
    async def recreate_all_buttons(self, interaction: discord.Interaction):
        config = load_config()
        messages = []
        
        # Recreate dismissal button
        dismissal_channel_id = config.get('dismissal_channel')
        if dismissal_channel_id:
            channel = self.bot.get_channel(dismissal_channel_id)
            if channel:
                await send_dismissal_button_message(channel)
                messages.append(f"✅ Рапорт на увольнение: {channel.mention}")
            else:
                messages.append("❌ Рапорт на увольнение: канал не найден")
        else:
            messages.append("⚠️ Рапорт на увольнение: не настроен")
        
        # Recreate audit button
        audit_channel_id = config.get('audit_channel')
        if audit_channel_id:
            channel = self.bot.get_channel(audit_channel_id)
            if channel:
                await send_audit_button_message(channel)
                messages.append(f"✅ Кадровый аудит: {channel.mention}")
            else:
                messages.append("❌ Кадровый аудит: канал не найден")
        else:
            messages.append("⚠️ Кадровый аудит: не настроен")
        
        # Recreate blacklist button
        blacklist_channel_id = config.get('blacklist_channel')
        if blacklist_channel_id:
            channel = self.bot.get_channel(blacklist_channel_id)
            if channel:
                await send_blacklist_button_message(channel)
                messages.append(f"✅ Чёрный список: {channel.mention}")
            else:
                messages.append("❌ Чёрный список: канал не найден")
        else:
            messages.append("⚠️ Чёрный список: не настроен")
        
        response = "**Результат пересоздания кнопок:**\n" + "\n".join(messages)
        await interaction.response.send_message(response, ephemeral=True)

    # Error handling for commands
    @set_dismissal_channel.error
    @set_audit_channel.error
    @set_blacklist_channel.error
    @show_channels.error
    @recreate_dismissal_button.error
    @recreate_audit_button.error
    @recreate_blacklist_button.error
    @recreate_all_buttons.error
    async def channel_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("У вас нет прав для выполнения этой команды.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Произошла ошибка: {error}", ephemeral=True)
            print(f"Command error: {error}")

# Setup function for adding the cog to the bot
async def setup(bot):
    await bot.add_cog(ChannelManagementCog(bot))
