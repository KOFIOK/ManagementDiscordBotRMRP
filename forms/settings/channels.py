"""
Channel configuration forms and views - Main navigation
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, ChannelParser, ConfigDisplayHelper

# Import specific channel configuration modules
from .channels_role_assignment import show_role_assignment_config
from .channels_dismissal import show_dismissal_config
from .channels_other import (
    show_blacklist_config, 
    show_leave_requests_config, 
    show_medical_registration_config,
    show_safe_documents_config
)
from .channels_promotion import show_promotion_reports_config
from .channels_warehouse import show_warehouse_config
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class ChannelsConfigView(BaseSettingsView):
    """View for channel configuration selection"""
    
    def __init__(self):
        super().__init__()
        self.add_item(ChannelConfigSelect())


class ChannelConfigSelect(ui.Select):
    """Select menu for choosing which channel to configure"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Канал увольнений",
                description="Настроить канал для рапортов на увольнение",
                emoji="📝",
                value="dismissal"
            ),
            discord.SelectOption(
                label="Канал аудита",
                description="Настроить канал для кадрового аудита",
                emoji="📋",
                value="audit"
            ),
            discord.SelectOption(
                label="Канал чёрного списка",
                description="Настроить канал для чёрного списка",
                emoji="🚫",
                value="blacklist"
            ),
            discord.SelectOption(
                label="Канал получения ролей",
                description="Настроить канал для выбора военной/гражданской роли",
                emoji="🎖️",
                value="role_assignment"
            ),
            discord.SelectOption(
                label="Каналы отчётов на повышение",
                description="Настроить каналы для отчётов на повышение по подразделениям",
                emoji="📈",
                value="promotion_reports"
            ),
            discord.SelectOption(
                label="Канал отгулов",
                description="Настроить канал для заявок на отгулы",
                emoji="🏖️",
                value="leave_requests"
            ),
            discord.SelectOption(
                label="Запись к врачу",
                description="Настроить канал для записи к врачу медицинской роты",
                emoji="🏥",
                value="medical_registration"
            ),
            discord.SelectOption(
                label="Каналы склада",
                description="Настроить каналы запросов и аудита складского имущества",
                emoji="📦",
                value="warehouse"
            ),
            discord.SelectOption(
                label="Заявления в подразделения",
                description="Настроить каналы для заявлений в подразделения",
                emoji="🏢",
                value="departments"
            ),
            discord.SelectOption(
                label="Сейф документов",
                description="Настроить канал для заявок на безопасное хранение документов",
                emoji="📋",
                value="safe_documents"
            )
        ]
        
        super().__init__(
            placeholder="Выберите канал для настройки...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="channel_config_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_option = self.values[0]
        await self.show_channel_selection(interaction, selected_option)
    
    async def _redirect_to_warehouse_settings(self, interaction: discord.Interaction):
        """Редирект на полную панель настроек склада"""
        from .warehouse_settings import WarehouseSettingsView
        
        embed = discord.Embed(
            title="📦 Настройки склада",
            description=(
                "Для настройки каналов склада используйте полную панель настроек склада.\n\n"
                "📋 **Доступные настройки:**\n"
                "• Каналы склада (запросы, отправка заявок, аудит)\n"
                "• Кулдаун запросов\n"
                "• Режим лимитов\n"
                "• Лимиты по должностям и званиям"
            ),
            color=discord.Color.blue()
        )
        
        view = WarehouseSettingsView()
        
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def show_channel_selection(self, interaction: discord.Interaction, config_type: str):
        """Show channel selection interface"""
        try:
            if config_type == "role_assignment":
                await show_role_assignment_config(interaction)
            elif config_type == "dismissal":
                await show_dismissal_config(interaction)
            elif config_type == "blacklist":
                await show_blacklist_config(interaction)
            elif config_type == "promotion_reports":
                await show_promotion_reports_config(interaction)
            elif config_type == "leave_requests":
                await show_leave_requests_config(interaction)
            elif config_type == "medical_registration":
                await show_medical_registration_config(interaction)
            elif config_type == "warehouse":
                # Редирект на полную панель настроек склада для избежания дублирования
                await self._redirect_to_warehouse_settings(interaction)
            elif config_type == "departments":
                from .channels_departments import show_department_channels_config
                await show_department_channels_config(interaction)
            elif config_type == "safe_documents":
                await show_safe_documents_config(interaction)
            else:
                # For audit channel (simple channel selection)
                from .channels_base import ChannelSelectionModal
                modal = ChannelSelectionModal(config_type)
                await interaction.response.send_modal(modal)
                
        except Exception as e:
            logger.error("Ошибка в show_channel_selection для %s: %s", config_type, e)
            import traceback
            traceback.print_exc()
            
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Произошла ошибка при загрузке настроек канала {config_type}.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f" Произошла ошибка при загрузке настроек канала {config_type}.",
                    ephemeral=True
                )