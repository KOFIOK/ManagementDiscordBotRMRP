"""
Channel configuration forms and views
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from forms.dismissal_form import send_dismissal_button_message
from .base import BaseSettingsView, BaseSettingsModal, ChannelParser, ConfigDisplayHelper


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
                emoji="🔍",
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
    
    async def show_channel_selection(self, interaction: discord.Interaction, config_type: str):
        """Show channel selection interface"""
        if config_type == "role_assignment":
            await self.show_role_assignment_config(interaction)
        else:
            # Create channel selection modal for other channel types
            modal = ChannelSelectionModal(config_type)
            await interaction.response.send_modal(modal)
    
    async def show_role_assignment_config(self, interaction: discord.Interaction):
        """Show role assignment channel configuration with role management"""
        embed = discord.Embed(
            title="🎖️ Настройка канала получения ролей",
            description="Управление каналом и ролями для системы получения ролей.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        config = load_config()
        helper = ConfigDisplayHelper()
        
        # Show current channel
        embed.add_field(
            name="📂 Текущий канал:",
            value=helper.format_channel_info(config, 'role_assignment_channel', interaction.guild),
            inline=False
        )
        
        # Show current roles
        embed.add_field(
            name="🪖 Роль военнослужащего:",
            value=helper.format_role_info(config, 'military_role', interaction.guild),
            inline=True
        )
        embed.add_field(
            name="👤 Роль гражданского:",
            value=helper.format_role_info(config, 'civilian_role', interaction.guild),
            inline=True
        )
        
        embed.add_field(
            name="ℹ️ Доступные действия:",
            value=(
                "• **Настроить канал** - установить канал для получения ролей\n"
                "• **Настроить роли** - настроить военную и гражданскую роли\n"
                "• **Полная настройка** - настроить всё сразу"
            ),
            inline=False
        )
        
        view = RoleAssignmentChannelView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class RoleAssignmentChannelView(BaseSettingsView):
    """View for role assignment channel configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("role_assignment")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🪖 Роль военнослужащего", style=discord.ButtonStyle.primary)
    async def set_military_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetRoleModal
        modal = SetRoleModal("military_role", "🪖 Настройка роли военнослужащего", "Укажите роль для военнослужащих")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👤 Роль гражданского", style=discord.ButtonStyle.secondary)
    async def set_civilian_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetRoleModal
        modal = SetRoleModal("civilian_role", "👤 Настройка роли гражданского", "Укажите роль для гражданских")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⚔️ Дополнительные военные роли", style=discord.ButtonStyle.blurple)
    async def set_additional_military_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("additional_military_roles", "⚔️ Дополнительные военные роли", "Укажите дополнительные роли для военнослужащих (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📢 Ping-роль", style=discord.ButtonStyle.green)
    async def set_ping_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetRoleModal
        modal = SetRoleModal("role_assignment_ping_role", "📢 Настройка ping-роли", "Укажите роль для уведомлений о новых заявках")
        await interaction.response.send_modal(modal)


class ChannelSelectionModal(BaseSettingsModal):
    """Modal for selecting and configuring channels"""
    
    def __init__(self, config_type: str):
        self.config_type = config_type
        
        type_names = {
            "dismissal": "увольнений",
            "audit": "аудита", 
            "blacklist": "чёрного списка",
            "role_assignment": "получения ролей"
        }
        
        super().__init__(title=f"Настройка канала {type_names.get(config_type, config_type)}")
        
        self.channel_input = ui.TextInput(
            label="ID или упоминание канала",
            placeholder="Например: #канал-увольнений или 1234567890123456789",
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
                    f"Не удалось найти канал по запросу: `{channel_text}`\n"
                    "Убедитесь, что вы указали правильное ID, упоминание или название канала."
                )
                return
            
            if not isinstance(channel, discord.TextChannel):
                await self.send_error_message(
                    interaction,
                    "Неподходящий тип канала",
                    "Выбранный канал должен быть текстовым каналом."
                )
                return
            
            # Save configuration
            config = load_config()
            config[f'{self.config_type}_channel'] = channel.id
            save_config(config)
            
            # Define type names and handle button messages
            type_names = {
                "dismissal": "рапортов на увольнение",
                "audit": "кадрового аудита",
                "blacklist": "чёрного списка",
                "role_assignment": "получения ролей"
            }
            type_name = type_names.get(self.config_type, self.config_type)
            
            # Send appropriate button message to the channel
            button_message_added = False
            if self.config_type == "dismissal":
                await send_dismissal_button_message(channel)
                button_message_added = True
            elif self.config_type == "role_assignment":
                # Import and send role assignment button message
                from forms.role_assignment_form import send_role_assignment_message
                await send_role_assignment_message(channel)
                button_message_added = True
            
            success_message = f"Канал {type_name} успешно настроен на {channel.mention}!"
            if button_message_added:
                success_message += "\nСообщение с кнопками добавлено в канал."
            
            await self.send_success_message(
                interaction,
                "Канал настроен",
                success_message
            )
            
        except ValueError as e:
            await self.send_error_message(
                interaction,
                "Ошибка валидации",
                f"Некорректные данные: {str(e)}"
            )
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке канала: {str(e)}"
            )
