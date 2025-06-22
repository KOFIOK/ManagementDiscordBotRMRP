"""
Role assignment channel configuration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, ConfigDisplayHelper
from .channels_base import ChannelSelectionModal


class RoleAssignmentChannelView(BaseSettingsView):
    """View for role assignment channel configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("role_assignment")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🪖 Роли военнослужащих", style=discord.ButtonStyle.primary)
    async def set_military_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("military_roles", "🪖 Настройка ролей военнослужащих", "Укажите роли для военнослужащих (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📦 Роли доступа к поставкам", style=discord.ButtonStyle.secondary)
    async def set_supplier_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("supplier_roles", "📦 Настройка ролей доступа к поставкам", "Укажите роли для доступа к поставкам (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👤 Роли гражданских", style=discord.ButtonStyle.secondary)
    async def set_civilian_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("civilian_roles", "👤 Настройка ролей гражданских", "Укажите роли для гражданских (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📢 Настроить ping-роли", style=discord.ButtonStyle.green)
    async def set_ping_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RolePingConfigView()
        await view.show_ping_config(interaction)


class RolePingConfigView(BaseSettingsView):
    """View for configuring role assignment ping settings"""
    
    def __init__(self):
        super().__init__()
    
    async def show_ping_config(self, interaction: discord.Interaction):
        """Show ping role configuration interface"""
        embed = discord.Embed(
            title="📢 Настройка пинг-ролей",
            description="Настройте роли для уведомлений о новых заявках.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        config = load_config()
        helper = ConfigDisplayHelper()
        
        embed.add_field(
            name="🪖 Пинг-роли для военных заявок:",
            value=helper.format_roles_list(config, 'military_role_assignment_ping_roles', interaction.guild),
            inline=False
        )
        
        embed.add_field(
            name="📦 Пинг-роли для заявок доступа к поставкам:",
            value=helper.format_roles_list(config, 'supplier_role_assignment_ping_roles', interaction.guild),
            inline=False
        )
        
        embed.add_field(
            name="👤 Пинг-роли для гражданских заявок:",
            value=helper.format_roles_list(config, 'civilian_role_assignment_ping_roles', interaction.guild),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Информация:",
            value="Выберите роли, которые будут получать уведомления при подаче новых заявок. Можно указать несколько ролей через запятую. Формат пинга: `-# @роль1 @роль2`",
            inline=False
        )
        
        view = RolePingButtonsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class RolePingButtonsView(BaseSettingsView):
    """Buttons for ping role configuration"""
    
    @discord.ui.button(label="📜 Пинг военных", style=discord.ButtonStyle.green)
    async def set_military_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("military_role_assignment_ping_roles", "🪖 Пинг-роли для военных", "Укажите роли для уведомлений о военных заявках")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📦 Пинг доступа к поставкам", style=discord.ButtonStyle.secondary)
    async def set_supplier_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("supplier_role_assignment_ping_roles", "📦 Пинг-роли для доступа к поставкам", "Укажите роли для уведомлений о заявках доступа к поставкам")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👨‍⚕️ Пинг госслужащих", style=discord.ButtonStyle.secondary)
    async def set_civilian_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("civilian_role_assignment_ping_roles", "👤 Пинг-роли для гражданских", "Укажите роли для уведомлений о гражданских заявках")
        await interaction.response.send_modal(modal)


async def show_role_assignment_config(interaction: discord.Interaction):
    """Show role assignment channel configuration with role management"""
    embed = discord.Embed(
        title="🎖️ Настройка канала получения ролей",
        description="Управление каналом и ролями для системы получения ролей.",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    config = load_config()
    helper = ConfigDisplayHelper()
    
    # Show current channel and message
    embed.add_field(
        name="📂 Текущий канал:",
        value=helper.format_channel_info(config, 'role_assignment_channel', interaction.guild),
        inline=False
    )
    
    # Show role assignment message info
    message_id = config.get('role_assignment_message_id')
    channel_id = config.get('role_assignment_channel')
    if message_id and channel_id:
        message_link = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{message_id}"
        embed.add_field(
            name="📌 Сообщение с кнопками:",
            value=f"[Перейти к сообщению]({message_link}) (ID: {message_id})",
            inline=False
        )
    else:
        embed.add_field(
            name="📌 Сообщение с кнопками:",
            value="❌ Не настроено или не найдено",
            inline=False
        )
    
    # Show current roles
    embed.add_field(
        name="🪖 Роли военнослужащих:",
        value=helper.format_roles_info(config, 'military_roles', interaction.guild),
        inline=True
    )
    embed.add_field(
        name="📦 Роли доступа к поставкам:",
        value=helper.format_roles_info(config, 'supplier_roles', interaction.guild),
        inline=True
    )
    embed.add_field(
        name="👤 Роли гражданских:",
        value=helper.format_roles_info(config, 'civilian_roles', interaction.guild),
        inline=True
    )
    
    # Show ping roles
    embed.add_field(
        name="📢 Пинг роли:",
        value=(
            f"🪖 Военные: {helper.format_roles_list(config, 'military_role_assignment_ping_roles', interaction.guild)}\n"
            f"📦 Доступ к поставкам: {helper.format_roles_list(config, 'supplier_role_assignment_ping_roles', interaction.guild)}\n"
            f"👤 Гражданские: {helper.format_roles_list(config, 'civilian_role_assignment_ping_roles', interaction.guild)}"
        ),
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Доступные действия:",
        value=(
            "• **Настроить канал** - установить канал для получения ролей\n"
            "• **Настроить роли** - настроить роли для военных, доступа к поставкам и госслужащих\n"
            "• **Настроить пинги** - настроить роли для уведомлений\n"
            "• **Полная настройка** - настроить всё сразу"
        ),
        inline=False
    )
    
    view = RoleAssignmentChannelView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
