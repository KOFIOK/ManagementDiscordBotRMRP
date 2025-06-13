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
            ),
            discord.SelectOption(
                label="Регистрация модераторов",
                description="Настроить канал для регистрации модераторов в системе",                emoji="🔐",
                value="moderator_registration"
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
        elif config_type == "blacklist":
            await self.show_blacklist_config(interaction)
        elif config_type == "moderator_registration":
            await self.show_moderator_registration_config(interaction)
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
            name="ℹ️ Доступные действия:",
            value=(
                "• **Настроить канал** - установить канал для рапортов на увольнение\n"
                "• **Добавить пинг** - добавить настройку для подразделения\n"
                "• **Удалить пинг** - убрать настройку пинга\n"
                "• **Роль автоувольнений** - настроить роль для автоматических рапортов\n"
                "• **Очистить пинги** - удалить все настройки пингов"
            ),
            inline=False
        )
        
        view = DismissalChannelView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_blacklist_config(self, interaction: discord.Interaction):
        """Show blacklist channel configuration with ping management"""
        embed = discord.Embed(
            title="🚫 Настройка канала чёрного списка",
            description="Управление каналом чёрного списка и пингами для уведомлений.",
            color=discord.Color.dark_red(),
            timestamp=discord.utils.utcnow()
        )
        
        config = load_config()
        helper = ConfigDisplayHelper()
        
        # Show current channel
        embed.add_field(
            name="📂 Текущий канал:",
            value=helper.format_channel_info(config, 'blacklist_channel', interaction.guild),
            inline=False
        )
        
        # Show blacklist ping settings
        blacklist_role_mentions = config.get('blacklist_role_mentions', [])
        if blacklist_role_mentions:
            ping_roles = []
            for role_id in blacklist_role_mentions:
                role = interaction.guild.get_role(role_id)
                if role:
                    ping_roles.append(role.mention)
                else:
                    ping_roles.append(f"❌ Роль не найдена (ID: {role_id})")
            ping_text = ", ".join(ping_roles)
        else:
            ping_text = "❌ Пинги не настроены"
        
        embed.add_field(
            name="📢 Пинг-роли для чёрного списка:",
            value=ping_text,
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Доступные действия:",
            value=(
                "• **Настроить канал** - установить канал для чёрного списка\n"
                "• **Добавить пинг-роль** - добавить роль для уведомлений\n"
                "• **Удалить пинг-роль** - убрать роль из уведомлений\n"
                "• **Очистить пинги** - удалить все пинг-роли"
            ),
            inline=False
        )
        
        view = BlacklistChannelView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_moderator_registration_config(self, interaction: discord.Interaction):
        """Show moderator registration channel configuration"""
        config = load_config()
        
        embed = discord.Embed(
            title="🔐 Настройка канала регистрации модераторов",
            description="Управление каналом для регистрации модераторов в системе.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Show current channel
        channel_id = config.get('moderator_registration_channel')
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                embed.add_field(
                    name="📂 Текущий канал:",
                    value=f"{channel.mention} (ID: {channel.id})",
                    inline=False
                )
            else:
                embed.add_field(
                    name="❌ Текущий канал:",
                    value=f"Канал не найден (ID: {channel_id})",
                    inline=False
                )
        else:
            embed.add_field(
                name="❌ Канал не настроен",
                value="Установите канал для регистрации модераторов",
                inline=False
            )
        
        embed.add_field(
            name="ℹ️ Описание функции:",
            value=(
                "В этом канале будет размещено закреплённое сообщение с кнопкой "
                "для регистрации модераторов в системе кадрового учёта.\n\n"
                "**Регистрироваться могут только пользователи с правами модератора.**"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Доступные действия:",
            value="• **Настроить канал** - установить канал для регистрации",
            inline=False
        )
        
        view = ModeratorRegistrationChannelView()
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
            "role_assignment": "получения ролей",
            "moderator_registration": "регистрации модераторов"
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
                "role_assignment": "получения ролей",
                "moderator_registration": "регистрации модераторов"
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
            elif self.config_type == "moderator_registration":
                # Import and send moderator registration message
                from forms.moderator_registration import ensure_moderator_registration_message
                await ensure_moderator_registration_message(interaction.guild, channel.id)
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
    
    @discord.ui.button(label="⚙️ Роль автоувольнений", style=discord.ButtonStyle.secondary)
    async def set_auto_dismissal_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AutoDismissalRoleModal()
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


class BlacklistChannelView(BaseSettingsView):
    """View for blacklist channel and ping configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("blacklist")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➕ Добавить пинг-роль", style=discord.ButtonStyle.secondary)
    async def add_ping_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BlacklistPingRoleModal("add")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Удалить пинг-роль", style=discord.ButtonStyle.red)
    async def remove_ping_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        blacklist_role_mentions = config.get('blacklist_role_mentions', [])
        
        if not blacklist_role_mentions:
            await self.send_error_message(
                interaction,
                "Нет ролей для удаления",
                "Нет настроенных пинг-ролей для удаления."
            )
            return
        
        modal = BlacklistPingRoleModal("remove")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Очистить пинги", style=discord.ButtonStyle.danger)
    async def clear_ping_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        config['blacklist_role_mentions'] = []
        save_config(config)
        
        await self.send_success_message(
            interaction,
            "Пинг-роли очищены",
            "Все пинг-роли для чёрного списка были удалены. Теперь при отправке в чёрный список уведомления отправляться не будут."
        )


class BlacklistPingRoleModal(BaseSettingsModal):
    """Modal for managing blacklist ping roles"""
    
    def __init__(self, action: str):
        self.action = action
        
        if action == "add":
            title = "Добавить пинг-роль для чёрного списка"
            placeholder = "Например: @модераторы или 1234567890123456789"
            label = "Роль для добавления"
        else:  # remove
            title = "Удалить пинг-роль из чёрного списка"
            placeholder = "Например: @модераторы или 1234567890123456789"
            label = "Роль для удаления"
        
        super().__init__(title=title)
        
        self.role_input = ui.TextInput(
            label=label,
            placeholder=placeholder,
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            from .base import RoleParser
            
            # Parse role input
            role = RoleParser.parse_role_input(
                self.role_input.value.strip(), 
                interaction.guild
            )
            
            if not role:
                await self.send_error_message(
                    interaction,
                    "Роль не найдена",
                    f"Не удалось найти роль: `{self.role_input.value}`"
                )
                return
            
            # Load config
            config = load_config()
            blacklist_role_mentions = config.get('blacklist_role_mentions', [])
            
            if self.action == "add":
                if role.id in blacklist_role_mentions:
                    await self.send_error_message(
                        interaction,
                        "Роль уже добавлена",
                        f"Роль {role.mention} уже настроена для уведомлений чёрного списка."
                    )
                    return
                
                blacklist_role_mentions.append(role.id)
                config['blacklist_role_mentions'] = blacklist_role_mentions
                save_config(config)
                
                await self.send_success_message(
                    interaction,
                    "Пинг-роль добавлена",
                    f"Роль {role.mention} добавлена в список уведомлений чёрного списка."
                )
            
            else:  # remove
                if role.id not in blacklist_role_mentions:
                    await self.send_error_message(
                        interaction,
                        "Роль не найдена в настройках",
                        f"Роль {role.mention} не настроена для уведомлений чёрного списка."
                    )
                    return
                
                blacklist_role_mentions.remove(role.id)
                config['blacklist_role_mentions'] = blacklist_role_mentions
                save_config(config)
                
                await self.send_success_message(
                    interaction,
                    "Пинг-роль удалена",
                    f"Роль {role.mention} удалена из списка уведомлений чёрного списка."
                )
                
        except Exception as e:            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при обработке роли: {str(e)}"
            )


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
                if role.name == role_name:
                    target_role = role
                    break
            
            if not target_role:
                await self.send_error_message(
                    interaction,
                    "Роль не найдена",
                    f"Роль с именем '{role_name}' не найдена на сервере.\n"
                    "Убедитесь, что имя роли указано точно как в настройках сервера."
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


class ModeratorRegistrationChannelView(BaseSettingsView):
    """View for moderator registration channel configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("moderator_registration")
        await interaction.response.send_modal(modal)
