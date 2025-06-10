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
        elif config_type == "dismissal":
            await self.show_dismissal_config(interaction)
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
            inline=False        )
        
        # Show current roles
        embed.add_field(
            name="🪖 Роли военнослужащих:",
            value=helper.format_roles_info(config, 'military_roles', interaction.guild),
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
                f"👤 Гражданские: {helper.format_roles_list(config, 'civilian_role_assignment_ping_roles', interaction.guild)}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Доступные действия:",
            value=(
                "• **Настроить канал** - установить канал для получения ролей\n"
                "• **Настроить роли** - настроить военную и гражданскую роли\n"
                "• **Настроить пинги** - настроить роли для уведомлений\n"
                "• **Полная настройка** - настроить всё сразу"
            ),
            inline=False
        )
        view = RoleAssignmentChannelView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_dismissal_config(self, interaction: discord.Interaction):
        """Show dismissal channel configuration with ping management"""
        embed = discord.Embed(
            title="📝 Настройка канала увольнений",
            description="Управление каналом увольнений и пингами для уведомлений по подразделениям.",
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
        
        # Show ping settings
        ping_settings = config.get('ping_settings', {})
        if ping_settings:
            ping_text = ""
            for department_role_id, ping_roles_ids in ping_settings.items():
                department_role = interaction.guild.get_role(int(department_role_id))
                if department_role:
                    ping_roles = []
                    for ping_role_id in ping_roles_ids:
                        ping_role = interaction.guild.get_role(ping_role_id)
                        if ping_role:
                            ping_roles.append(ping_role.mention)
                    if ping_roles:
                        ping_text += f"• {department_role.mention} → {', '.join(ping_roles)}\n"
            ping_text = ping_text or "❌ Настройки пингов не найдены"
        else:
            ping_text = "❌ Настройки пингов не настроены"
        embed.add_field(
            name="📢 Настройки пингов по подразделениям:",
            value=ping_text,
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Доступные действия:",
            value=(
                "• **Настроить канал** - установить канал для рапортов на увольнение\n"
                "• **Добавить пинг** - добавить настройку для подразделения\n"
                "• **Удалить пинг** - убрать настройку пинга\n"
                "• **Очистить пинги** - удалить все настройки пингов"
            ),
            inline=False
        )
        
        view = DismissalChannelView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


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
    
    @discord.ui.button(label="👤 Роли гражданских", style=discord.ButtonStyle.secondary)
    async def set_civilian_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("civilian_roles", "👤 Настройка ролей гражданских", "Укажите роли для гражданских (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📢 Настроить ping-роли", style=discord.ButtonStyle.green)
    async def set_ping_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RolePingConfigView()
        await view.show_ping_config(interaction)


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


class RolePingConfigView(BaseSettingsView):
    """View for configuring role assignment ping settings"""
    
    def __init__(self):
        super().__init__()
    
    async def show_ping_config(self, interaction: discord.Interaction):
        """Show ping role configuration interface"""
        embed = discord.Embed(
            title="📢 Настройка пинг-ролей",
            description="Настройте роли для уведомлений о новых заявках.",
            color=discord.Color.orange(),            timestamp=discord.utils.utcnow()
        )
        
        config = load_config()
        helper = ConfigDisplayHelper()
        
        embed.add_field(
            name="🪖 Пинг-роли для военных заявок:",
            value=helper.format_roles_list(config, 'military_role_assignment_ping_roles', interaction.guild),
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
    
    @discord.ui.button(label="🪖 Пинг военных", style=discord.ButtonStyle.green)
    async def set_military_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("military_role_assignment_ping_roles", "🪖 Пинг-роли для военных", "Укажите роли для уведомлений о военных заявках")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👤 Пинг гражданских", style=discord.ButtonStyle.secondary)
    async def set_civilian_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("civilian_role_assignment_ping_roles", "👤 Пинг-роли для гражданских", "Укажите роли для уведомлений о гражданских заявках")
        await interaction.response.send_modal(modal)


class DismissalChannelView(BaseSettingsView):
    """View for dismissal channel and ping configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("dismissal")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➕ Добавить пинг", style=discord.ButtonStyle.secondary)
    async def add_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .ping_settings import AddPingSettingModal
        modal = AddPingSettingModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Удалить пинг", style=discord.ButtonStyle.red)
    async def remove_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        ping_settings = config.get('ping_settings', {})
        
        if not ping_settings:
            await self.send_error_message(
                interaction,
                "Нет настроек для удаления",
                "Нет настроенных пингов для удаления."
            )
            return
        
        from .ping_settings import RemovePingSettingModal
        modal = RemovePingSettingModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Очистить пинги", style=discord.ButtonStyle.danger)
    async def clear_pings(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        config['ping_settings'] = {}
        save_config(config)
        
        await self.send_success_message(
            interaction,
            "Настройки пингов очищены",
            "Все настройки пингов были удалены. Теперь при подаче рапортов уведомления отправляться не будут."
        )
