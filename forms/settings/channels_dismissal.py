"""
Dismissal channel configuration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, ConfigDisplayHelper
from .channels_base import ChannelSelectionModal


class DismissalChannelView(BaseSettingsView):
    """View for dismissal channel configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("dismissal")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⚙️ Роль автоувольнений", style=discord.ButtonStyle.secondary)
    async def set_auto_dismissal_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AutoDismissalRoleModal()
        await interaction.response.send_modal(modal)


class AutoDismissalRoleModal(BaseSettingsModal):
    """Modal for configuring automatic dismissal role"""
    
    def __init__(self):
        super().__init__(title="Настройка роли для автоматических увольнений")
        
        # Load current setting
        config = load_config()
        current_role = config.get('military_role_name', 'Военнослужащий ВС РФ')
        
        self.role_name = ui.TextInput(
            label="Имя роли для автоувольнений",
            placeholder="Например: Военнослужащий ВС РФ",
            default=current_role,
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.role_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            role_name = self.role_name.value.strip()
            
            # Validate that the role exists in the guild
            guild = interaction.guild
            target_role = None
            
            for role in guild.roles:
                if role.name.lower() == role_name.lower():
                    target_role = role
                    break
            
            if not target_role:
                await self.send_error_message(
                    interaction,
                    "Роль не найдена",
                    f"Роль с именем '{role_name}' не найдена на сервере. Проверьте правильность написания."
                )
                return
            
            # Save configuration
            config = load_config()
            config['military_role_name'] = role_name
            save_config(config)
            
            await self.send_success_message(
                interaction,
                "Роль настроена",
                f"Роль для автоматических увольнений установлена: **{role_name}**\n\n"
                f"Теперь пользователи с этой ролью, покинувшие сервер, будут автоматически получать рапорт на увольнение с причиной 'Потеря спец. связи'.\n"
                f"При одобрении такого рапорта модератор будет запрошен указать статик."
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке роли: {str(e)}"
            )


async def show_dismissal_config(interaction: discord.Interaction):
    """Show dismissal channel configuration"""
    embed = discord.Embed(
        title="📝 Настройка канала увольнений",
        description="Управление каналом увольнений и ролью для автоматических увольнений.",
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )
    
    config = load_config()
    helper = ConfigDisplayHelper()
    
    # Show current channel
    embed.add_field(
        name="📂 Текущий канал:",
        value=helper.format_channel_info(config, 'dismissal_channel', interaction.guild),
        inline=False
    )
    
    # Show automatic dismissal role
    auto_role_name = config.get('military_role_name', 'Военнослужащий ВС РФ')
    auto_role = None
    for role in interaction.guild.roles:
        if role.name == auto_role_name:
            auto_role = role
            break
    
    auto_role_display = auto_role.mention if auto_role else f"❌ Роль '{auto_role_name}' не найдена"
    embed.add_field(
        name="🤖 Роль для автоматических увольнений:",
        value=f"{auto_role_display}\n*Пользователи с этой ролью автоматически получают рапорт при выходе с сервера*",
        inline=False
    )
    
    embed.add_field(
        name="📢 Настройки пингов:",
        value="Настройки пингов для уведомлений при увольнениях теперь находятся в отдельном разделе:\n`/settings` → **Настройки пингов**",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Доступные действия:",
        value=(
            "• **Настроить канал** - установить канал для рапортов на увольнение\n"
            "• **Роль автоувольнений** - настроить роль для автоматических рапортов"
        ),
        inline=False
    )
    
    view = DismissalChannelView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
