"""
Настройки электронных заявок через /settings
"""

import discord
from discord import ui
from utils.config_manager import load_config, save_config
from utils.logging_setup import get_logger
from .base import BaseSettingsView

logger = get_logger(__name__)


class ElectronicApplicationsSettingsView(BaseSettingsView):
    """View для настройки электронных заявок"""
    
    def __init__(self):
        super().__init__()
        self.ea_config = load_config().get('electronic_applications', {})
    
    @ui.button(label="📂 Установить канал", style=discord.ButtonStyle.blurple, custom_id="ea_set_channel")
    async def set_channel(self, interaction: discord.Interaction, button: ui.Button):
        """Установить канал для электронных заявок"""
        await interaction.response.send_modal(SetChannelModal(self))
    
    @ui.button(label="✅ Успешная реакция", style=discord.ButtonStyle.green, custom_id="ea_set_success_reaction")
    async def set_success_reaction(self, interaction: discord.Interaction, button: ui.Button):
        """Установить реакцию успеха"""
        await interaction.response.send_modal(SetSuccessReactionModal(self))
    
    @ui.button(label="❌ Ошибка реакция", style=discord.ButtonStyle.red, custom_id="ea_set_failure_reaction")
    async def set_failure_reaction(self, interaction: discord.Interaction, button: ui.Button):
        """Установить реакцию ошибки"""
        await interaction.response.send_modal(SetFailureReactionModal(self))
    
    @ui.button(label="🔍 Регулярка для парсинга", style=discord.ButtonStyle.secondary, custom_id="ea_set_pattern")
    async def set_pattern(self, interaction: discord.Interaction, button: ui.Button):
        """Установить регулярку для парсинга Discord-тега"""
        await interaction.response.send_modal(SetPatternModal(self))
    
    @ui.button(label="📊 Статус", style=discord.ButtonStyle.secondary, custom_id="ea_status")
    async def show_status(self, interaction: discord.Interaction, button: ui.Button):
        """Показать текущий статус настроек"""
        config = load_config()
        ea_config = config.get('electronic_applications', {})
        
        channel_id = ea_config.get('channel_id')
        channel_mention = f"<#{channel_id}>" if channel_id else "❌ Не установлен"
        
        embed = discord.Embed(
            title="📋 Статус электронных заявок",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="✅ Статус системы",
            value="🟢 Включено" if ea_config.get('enabled', False) else "🔴 Отключено",
            inline=False
        )
        
        embed.add_field(
            name="📂 Канал",
            value=channel_mention,
            inline=False
        )
        
        embed.add_field(
            name="✅ Реакция успеха",
            value=ea_config.get('success_reaction', '✅'),
            inline=True
        )
        
        embed.add_field(
            name="❌ Реакция ошибки",
            value=ea_config.get('failure_reaction', '❌'),
            inline=True
        )
        
        embed.add_field(
            name="📝 Шаблон вступления",
            value=f"`{ea_config.get('template_path', 'data/electronic_applications.md')}`",
            inline=False
        )
        
        embed.add_field(
            name="🔍 Регулярка для парсинга",
            value=f"`{ea_config.get('discord_tag_pattern', '')[:100]}...`" if ea_config.get('discord_tag_pattern', '') else "❌ Не установлена",
            inline=False
        )
        
        embed.add_field(
            name="💡 Инструкция",
            value=(
                "1. Установите канал, в который летят вебхук-заявки\n"
                "2. Проверьте регулярку парсинга (должна совпадать с форматом вебхука)\n"
                "3. Система автоматически будет обрабатывать заявки\n"
                "4. Используйте `/message_request_edit` для редактирования шаблонов"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SetChannelModal(ui.Modal, title="Установить канал для электронных заявок"):
    """Modal для установки канала"""
    
    channel = ui.TextInput(
        label="ID или упоминание канала",
        placeholder="1452359439502803097 или #канал",
        required=True
    )
    
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_input = self.channel.value.strip()
            
            # Пытаемся найти канал
            if channel_input.startswith('<#') and channel_input.endswith('>'):
                # Формат <#123456>
                channel_id = int(channel_input[2:-1])
            else:
                try:
                    channel_id = int(channel_input)
                except ValueError:
                    # Поиск по названию
                    found_channel = None
                    for ch in interaction.guild.channels:
                        if ch.name.lower() == channel_input.lower():
                            found_channel = ch
                            break
                    
                    if not found_channel:
                        await interaction.response.send_message(
                            "❌ Канал не найден. Используйте ID, упоминание или точное название.",
                            ephemeral=True
                        )
                        return
                    
                    channel_id = found_channel.id
            
            # Проверяем, существует ли канал
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "❌ Канал не найден на сервере.",
                    ephemeral=True
                )
                return
            
            # Сохраняем конфиг
            config = load_config()
            config['electronic_applications']['channel_id'] = channel_id
            config['electronic_applications']['enabled'] = True
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Канал для электронных заявок установлен: {channel.mention}",
                ephemeral=True
            )
            
            logger.info(f"ELEC_APP SETTINGS: Канал установлен на {channel.mention} пользователем {interaction.user.display_name}")
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка: {str(e)[:100]}",
                ephemeral=True
            )
            logger.error(f"ELEC_APP SETTINGS ERROR: {e}")


class SetSuccessReactionModal(ui.Modal, title="Успешная реакция"):
    """Modal для установки реакции успеха"""
    
    reaction = ui.TextInput(
        label="Эмодзи для успешной доставки",
        placeholder="✅",
        max_length=10,
        required=True
    )
    
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            config = load_config()
            config['electronic_applications']['success_reaction'] = self.reaction.value
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Реакция успеха установлена: {self.reaction.value}",
                ephemeral=True
            )
            
            logger.info(f"ELEC_APP: Реакция успеха изменена на {self.reaction.value}")
        
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)[:100]}", ephemeral=True)


class SetFailureReactionModal(ui.Modal, title="Реакция ошибки"):
    """Modal для установки реакции ошибки"""
    
    reaction = ui.TextInput(
        label="Эмодзи для ошибки доставки",
        placeholder="❌",
        max_length=10,
        required=True
    )
    
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            config = load_config()
            config['electronic_applications']['failure_reaction'] = self.reaction.value
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Реакция ошибки установлена: {self.reaction.value}",
                ephemeral=True
            )
            
            logger.info(f"ELEC_APP: Реакция ошибки изменена на {self.reaction.value}")
        
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)[:100]}", ephemeral=True)


class SetPatternModal(ui.Modal, title="Регулярка для парсинга"):
    """Modal для установки регулярки"""
    
    pattern = ui.TextInput(
        label="Regex-паттерн",
        placeholder="Дискорд для связи с вами:\\s*(?:\\(Пример-\\s*)?@?([\\w.#\\d-]+)",
        required=True,
        style=discord.TextStyle.long
    )
    
    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            import re
            # Проверяем, что это валидная регулярка
            test = re.compile(self.pattern.value)
            
            config = load_config()
            config['electronic_applications']['discord_tag_pattern'] = self.pattern.value
            save_config(config)
            
            await interaction.response.send_message(
                f"✅ Регулярка установлена:\n`{self.pattern.value[:100]}...`",
                ephemeral=True
            )
            
            logger.info(f"ELEC_APP: Регулярка изменена")
        
        except re.error as e:
            await interaction.response.send_message(
                f"❌ Ошибка в регулярке: {str(e)[:100]}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {str(e)[:100]}", ephemeral=True)


async def show_electronic_applications_menu(interaction: discord.Interaction):
    """Показать меню настроек электронных заявок"""
    
    embed = discord.Embed(
        title="📋 Электронные заявки",
        description="Система для обработки вебхук-заявок на вступление/восстановление",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    config = load_config()
    ea_config = config.get('electronic_applications', {})
    
    embed.add_field(
        name="🎯 Функции",
        value=(
            "✅ Автоматическая обработка вебхук-заявок\n"
            "✅ Поиск пользователей по Discord-тегу\n"
            "✅ Отправка сообщений в личные сообщения\n"
            "✅ Реакции на успех/ошибку\n"
            "✅ Поддержка разных типов заявок"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Доступные настройки",
        value=(
            "• 📂 Установить канал\n"
            "• ✅ Успешная реакция\n"
            "• ❌ Реакция ошибки\n"
            "• 🔍 Регулярка для парсинга Discord-тега"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📝 Редактирование шаблонов",
        value="Используйте команду `/message_request_edit` для загрузки новых шаблонов заявок",
        inline=False
    )
    
    view = ElectronicApplicationsSettingsView()
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
