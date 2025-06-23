"""
Warehouse channels configuration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, ChannelParser, ConfigDisplayHelper


class WarehouseChannelsConfigView(BaseSettingsView):
    """View for warehouse channels configuration"""
    
    def __init__(self):
        super().__init__()
        
    @discord.ui.button(label="📦 Канал запросов", style=discord.ButtonStyle.primary, emoji="📦")
    async def set_request_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WarehouseChannelSelectionModal("warehouse_request_channel", "📦 Настройка канала запросов склада")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📤 Канал отправки заявок", style=discord.ButtonStyle.primary, emoji="📤")
    async def set_submission_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WarehouseChannelSelectionModal("warehouse_submission_channel", "📤 Настройка канала отправки заявок")
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="📊 Канал аудита", style=discord.ButtonStyle.primary, emoji="📊")
    async def set_audit_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WarehouseChannelSelectionModal("warehouse_audit_channel", "📊 Настройка канала аудита склада")
        await interaction.response.send_modal(modal)


class WarehouseChannelSelectionModal(BaseSettingsModal):
    """Modal for setting warehouse channels"""
    
    def __init__(self, config_key: str, title: str):
        super().__init__(title=title)
        self.config_key = config_key
        
        self.channel_input = discord.ui.TextInput(
            label="Канал",
            placeholder="Введите название канала, ID или упоминание (#канал)",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_text = self.channel_input.value.strip()
            
            # Parse channel input
            channel = ChannelParser.parse_channel_input(channel_text, interaction.guild)
            
            if not channel:
                await self.send_error_message(
                    interaction,
                    "Канал не найден",
                    f"Канал '{channel_text}' не найден на сервере."
                )
                return
            
            if not isinstance(channel, discord.TextChannel):
                await self.send_error_message(
                    interaction,
                    "Неверный тип канала",
                    "Можно указывать только текстовые каналы."
                )
                return
              # Save configuration
            config = load_config()
            config[self.config_key] = channel.id
            save_config(config)
            
            channel_names = {
                "warehouse_request_channel": "запросов склада",
                "warehouse_submission_channel": "отправки заявок склада",
                "warehouse_audit_channel": "аудита склада"
            }
            
            channel_name = channel_names.get(self.config_key, self.config_key)
            
            success_message = f"Канал {channel_name} успешно настроен на {channel.mention}!"
            
            # Special handling for different channel types
            if self.config_key == "warehouse_request_channel":
                try:
                    from utils.warehouse_utils import send_warehouse_message
                    await send_warehouse_message(channel)
                    success_message += "\n\n✅ Закрепленное сообщение склада добавлено в канал."
                except Exception as e:
                    print(f"Ошибка при создании сообщения склада: {e}")
                    success_message += "\n\n⚠️ Канал настроен, но произошла ошибка при создании сообщения. Используйте `/warehouse_setup` в канале."
            elif self.config_key == "warehouse_submission_channel":
                success_message += "\n\n📤 Все заявки склада будут отправляться в этот канал!"
            
            await self.send_success_message(
                interaction,
                "Канал настроен",
                success_message
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке канала: {str(e)}"
            )


async def show_warehouse_config(interaction: discord.Interaction):
    """Show warehouse channels configuration"""
    embed = discord.Embed(
        title="📦 Настройка каналов склада",
        description="Управление каналами для системы складского имущества.",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    config = load_config()
    helper = ConfigDisplayHelper()
    
    # Show current warehouse channels
    embed.add_field(
        name="📦 Канал запросов склада",
        value=helper.format_channel_info(config, 'warehouse_request_channel', interaction.guild),
        inline=False
    )
    
    embed.add_field(
        name="📊 Канал аудита склада", 
        value=helper.format_channel_info(config, 'warehouse_audit_channel', interaction.guild),
        inline=False
    )
    
    # Show current settings
    cooldown_hours = config.get('warehouse_cooldown_hours', 6)
    limits_mode = config.get('warehouse_limits_mode', {
        'positions_enabled': True,
        'ranks_enabled': False
    })
    
    limits_status = []
    if limits_mode.get('positions_enabled', True):
        limits_status.append("По должностям")
    if limits_mode.get('ranks_enabled', False):
        limits_status.append("По званиям")
    
    if not limits_status:
        limits_text = "Отключены"
    else:
        limits_text = " + ".join(limits_status)
    
    embed.add_field(
        name="⚙️ Текущие настройки",
        value=f"**Кулдаун:** {cooldown_hours} часов\n**Лимиты:** {limits_text}",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Инструкция:",
        value=(
            "1. **Канал запросов** - куда будут отправляться запросы на выдачу\n"
            "2. **Канал аудита** - где будут логироваться все выдачи\n"
            "3. Для настройки лимитов используйте меню **Настройки склада**"
        ),
        inline=False
    )
    
    view = WarehouseChannelsConfigView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
