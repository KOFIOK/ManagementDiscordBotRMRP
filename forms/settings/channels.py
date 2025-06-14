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
            ),            discord.SelectOption(
                label="Регистрация модераторов",
                description="Настроить канал для регистрации модераторов в системе",
                emoji="🔐",
                value="moderator_registration"
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
        elif config_type == "promotion_reports":
            await self.show_promotion_reports_config(interaction)
        elif config_type == "leave_requests":
            await self.show_leave_requests_config(interaction)
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
    
    async def show_dismissal_config(self, interaction: discord.Interaction):
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
    
    async def show_blacklist_config(self, discord_interaction: discord.Interaction):
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
            value=helper.format_channel_info(config, 'blacklist_channel', discord_interaction.guild),
            inline=False
        )
        
        # Show blacklist ping settings
        blacklist_role_mentions = config.get('blacklist_role_mentions', [])
        if blacklist_role_mentions:
            ping_roles = []
            for role_id in blacklist_role_mentions:
                role = discord_interaction.guild.get_role(role_id)
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
        await discord_interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_moderator_registration_config(self, discord_interaction: discord.Interaction):
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
            channel = discord_interaction.guild.get_channel(channel_id)
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
        await discord_interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_promotion_reports_config(self, interaction: discord.Interaction):
        """Show promotion reports channels configuration"""
        embed = discord.Embed(
            title="📈 Настройка каналов отчётов на повышение",
            description="Управление каналами для отчётов на повышение по подразделениям.",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        config = load_config()
        helper = ConfigDisplayHelper()
          # Show current channels
        promotion_channels = config.get('promotion_report_channels', {})
        department_names = {
            'va': 'ВА (Военная Академия)',
            'vk': 'ВК (Военный Комиссариат)',
            'uvp': 'УВП (Военная Полиция)',
            'sso': 'ССО (Силы Спец. Операций)',
            'mr': 'МР (Медицинская Рота)',
            'roio': 'РОиО (Роты Охраны)'
        }
        
        channels_info = ""
        for dept_code, channel_id in promotion_channels.items():
            dept_name = department_names.get(dept_code, dept_code.upper())
            if channel_id:
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    channels_info += f"• **{dept_name}**: {channel.mention}\n"
                else:
                    channels_info += f"• **{dept_name}**: ❌ Канал не найден (ID: {channel_id})\n"
            else:
                channels_info += f"• **{dept_name}**: ❌ Не настроено\n"
        
        embed.add_field(
            name="📊 Настроенные каналы:",
            value=channels_info or "❌ Каналы не настроены",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Описание:",
            value=(
                "Каждый канал предназначен для отчётов на повышение в звании "
                "для соответствующего подразделения. Настройте каналы для "
                "автоматической отправки отчётов в нужные места."
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Доступные действия:",
            value="Выберите подразделение для настройки канала и уведомлений:",
            inline=False
        )
        
        view = PromotionReportsConfigView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_leave_requests_config(self, interaction: discord.Interaction):
        """Show leave requests channel configuration with role management"""
        try:
            embed = discord.Embed(
                title="🏖️ Настройка канала отгулов",
                description="Управление каналом и ролями для системы заявок на отгул.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            config = load_config()
            helper = ConfigDisplayHelper()
            
            # Show current channel
            embed.add_field(
                name="📂 Текущий канал:",
                value=helper.format_channel_info(config, 'leave_requests_channel', interaction.guild),
                inline=False
            )
            
            # Show allowed roles
            allowed_roles = config.get('leave_requests_allowed_roles', [])
            if allowed_roles:
                role_mentions = []
                for role_id in allowed_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_mentions.append(role.mention)
                
                roles_text = "\n".join(role_mentions) if role_mentions else "❌ Настроенные роли не найдены"
            else:
                roles_text = "Все пользователи (роли не настроены)"
            
            embed.add_field(
                name="👥 Кто может подавать заявки:",
                value=roles_text,
                inline=False
            )
            
            embed.add_field(
                name="🔧 Доступные действия:",
                value="Выберите действие для настройки системы отгулов:",
                inline=False            )
            
            view = LeaveRequestsConfigView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            print(f"❌ ERROR in show_leave_requests_config: {e}")
            import traceback
            traceback.print_exc()
            # Try to send error message if interaction hasn't been responded to yet
            if not interaction.response.is_done():
                error_embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Произошла ошибка при загрузке настроек: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            raise


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


class ChannelSelectionModal(BaseSettingsModal):
    """Modal for selecting and configuring channels"""
    
    def __init__(self, config_type: str):
        self.config_type = config_type
        
        type_names = {
            "dismissal": "увольнений",
            "audit": "аудита", 
            "blacklist": "чёрного списка",
            "role_assignment": "получения ролей",
            "moderator_registration": "регистрации модераторов",
            "leave_requests": "отгулов"
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
            save_config(config)            # Define type names and handle button messages
            type_names = {
                "dismissal": "рапортов на увольнение",
                "audit": "кадрового аудита",
                "blacklist": "чёрного списка",
                "role_assignment": "получения ролей",
                "moderator_registration": "регистрации модераторов",
                "leave_requests": "отгулов"
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
            elif self.config_type == "leave_requests":
                # Import and send leave request button message
                from forms.leave_request_form import send_leave_request_button_message
                await send_leave_request_button_message(channel)
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


class PromotionReportsConfigView(BaseSettingsView):
    """View for promotion reports configuration with dropdown selection"""
    
    def __init__(self):
        super().__init__()
        self.add_item(PromotionDepartmentSelect())


class PromotionDepartmentSelect(ui.Select):
    """Select menu for choosing department to configure promotion reports"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Отчёты ВА",
                description="Военная Академия",
                emoji="✈️",
                value="va"
            ),
            discord.SelectOption(
                label="Отчёты ВК",
                description="Военный Комиссариат",
                emoji="🚀",
                value="vk"
            ),
            discord.SelectOption(
                label="Отчёты УВП",
                description="Управление Военной Полиции",
                emoji="👮",
                value="uvp"
            ),
            discord.SelectOption(
                label="Отчёты ССО",
                description="Силы Специальных Операций",
                emoji="🔫",
                value="sso"
            ),
            discord.SelectOption(
                label="Отчёты МР",
                description="Медицинская Рота",
                emoji="⚓",
                value="mr"
            ),
            discord.SelectOption(
                label="Отчёты РОиО",
                description="Рота Охраны и Обеспечения",
                emoji="🛡️",
                value="roio"
            )
        ]
        
        super().__init__(
            placeholder="Выберите подразделение для настройки...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="promotion_department_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_department = self.values[0]
        # Show department configuration with buttons
        department_names = {
            'va': 'ВА (Военная Академия)',
            'vk': 'ВК (Военный Комиссариат)',
            'uvp': 'УВП (Управление Военной Полиции)',
            'sso': 'ССО (Силы Специальных Операций)',
            'mr': 'МР (Медицинская Рота)',
            'roio': 'РОиО (Рота Охраны и Обеспечения)'
        }
        
        department_emojis = {
            'va': '✈️',
            'vk': '🚀',
            'uvp': '👮',
            'sso': '🔫',
            'mr': '⚓',
            'roio': '🛡️'
        }
        
        config = load_config()
        promotion_channels = config.get('promotion_report_channels', {})
        current_channel_id = promotion_channels.get(selected_department)
        
        embed = discord.Embed(
            title=f"{department_emojis.get(selected_department, '📈')} Настройка отчётов {department_names.get(selected_department, selected_department.upper())}",
            description=f"Управление каналом отчётов на повышение для подразделения {department_names.get(selected_department, selected_department.upper())}",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        # Show current channel
        if current_channel_id:
            channel = interaction.guild.get_channel(current_channel_id)
            if channel:
                embed.add_field(
                    name="📂 Текущий канал:",
                    value=f"{channel.mention} (ID: {channel.id})",
                    inline=False
                )
            else:
                embed.add_field(
                    name="❌ Текущий канал:",
                    value=f"Канал не найден (ID: {current_channel_id})",
                    inline=False
                )
        else:
            embed.add_field(
                name="❌ Канал не настроен",
                value="Установите канал для отчётов на повышение",
                inline=False
            )
        
        # Show notification settings
        notification_settings = config.get('promotion_notifications', {}).get(selected_department, {})
        if notification_settings:
            notification_text = notification_settings.get('text')
            notification_image = notification_settings.get('image')
            notification_enabled = notification_settings.get('enabled', False)
            
            status = "🟢 Включены" if notification_enabled else "🔴 Отключены"
            content_parts = []
            if notification_text:
                content_parts.append("📝 Текст")
            if notification_image:
                content_parts.append(f"🖼️ {notification_image}")
            content_info = f" ({', '.join(content_parts)})" if content_parts else ""
            
            # Get configured notification time
            schedule_config = config.get('notification_schedule', {'hour': 21, 'minute': 0})
            hour = schedule_config.get('hour', 21)
            minute = schedule_config.get('minute', 0)
            time_str = f"{hour:02d}:{minute:02d}"
            
            embed.add_field(
                name="🔔 Ежедневные уведомления:",
                value=f"{status}{content_info}\n{'*Отправка в ' + time_str + ' МСК*' if notification_enabled else ''}",
                inline=False
            )
        else:
            embed.add_field(
                name="🕐 Ежедневные уведомления:",
                value="❌ Не настроены",
                inline=False
            )
        
        embed.add_field(
            name="🔧 Доступные действия:",
            value=(
                "• **Настроить канал** - установить канал для отчётов\n"
                "• **Задать уведомление** - настроить ежедневные уведомления\n"
                "*Время отправки: `/set_notification_time`*"
            ),
            inline=False
        )
        
        view = PromotionDepartmentConfigView(selected_department)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        


class PromotionDepartmentConfigView(BaseSettingsView):
    """View for configuring specific department promotion reports"""
    
    def __init__(self, department_code: str):
        super().__init__()
        self.department_code = department_code
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PromotionChannelModal(self.department_code)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔔 Задать уведомление", style=discord.ButtonStyle.secondary)
    async def set_notification(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PromotionNotificationModal(self.department_code)
        await interaction.response.send_modal(modal)


class PromotionChannelModal(BaseSettingsModal):
    """Modal for configuring promotion report channel for specific department"""
    def __init__(self, department_code: str):
        self.department_code = department_code
        
        # Короткие названия для заголовков modal (лимит 45 символов)
        department_names = {
            'va': 'ВА',
            'vk': 'ВК', 
            'uvp': 'УВП',
            'sso': 'ССО',
            'mr': 'МР',
            'roio': 'РОиО'
        }
        
        dept_name = department_names.get(department_code, department_code.upper())
        super().__init__(title=f"📈 Настройка канала {dept_name}")
        
        # Полные названия для подсказок
        full_department_names = {
            'va': 'ВА (Военная Академия)',
            'vk': 'ВК (Военный Комиссариат)',
            'uvp': 'УВП (Военная Полиция)',
            'sso': 'ССО (Спецоперации)',
            'mr': 'МР (Медицинская Рота)',
            'roio': 'РОиО (Рота Охраны и Обеспечения)'
        }
        
        full_dept_name = full_department_names.get(department_code, department_code.upper())
        
        self.channel_input = ui.TextInput(
            label=f"Канал для отчётов {dept_name}",
            placeholder=f"Канал для отчётов {full_dept_name}",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse channel input
            channel = ChannelParser.parse_channel_input(self.channel_input.value.strip(), interaction.guild)
            
            if not channel:
                await self.send_error_message(
                    interaction,
                    "Канал не найден",
                    "Канал не найден. Укажите корректный ID канала, упоминание канала или название канала."
                )
                return
            
            # Save configuration
            config = load_config()
            if 'promotion_report_channels' not in config:
                config['promotion_report_channels'] = {}
            
            config['promotion_report_channels'][self.department_code] = channel.id
            save_config(config)
            
            department_names = {
                'va': 'ВА (Военная Академия)',
                'vk': 'ВК (Военный Комиссариат)',
                'uvp': 'УВП (Военная Полиция)',
                'sso': 'ССО (Спецоперации)',
                'mr': 'МР (Медицинская Рота)',
                'roio': 'РОиО (Рота Охраны и Обеспечения)'
            }
            
            dept_name = department_names.get(self.department_code, self.department_code.upper())
            
            await self.send_success_message(
                interaction,
                "Канал настроен",
                f"Канал для отчётов {dept_name} установлен: {channel.mention}"
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке канала: {str(e)}"
            )


class PromotionNotificationModal(BaseSettingsModal):
    """Modal for configuring promotion report daily notifications"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        
        # Короткие названия для заголовков modal
        department_names = {
            'va': 'ВА',
            'vk': 'ВК',
            'uvp': 'УВП', 
            'sso': 'ССО',
            'mr': 'МР',
            'roio': 'РОиО'
        }
        
        dept_name = department_names.get(department_code, department_code.upper())
        super().__init__(title=f"🔔 Уведомления {dept_name}")
        
        # Load current settings
        config = load_config()
        current_notification = config.get('promotion_notifications', {}).get(department_code, {})
        current_text = current_notification.get('text', '')
        current_image = current_notification.get('image', '')
        current_enabled = current_notification.get('enabled', False)
        
        self.text_input = ui.TextInput(
            label="Текст уведомления",
            placeholder="Введите текст для ежедневного уведомления...",
            style=discord.TextStyle.paragraph,
            min_length=0,
            max_length=1000,
            required=False,
            default=current_text
        )
        self.add_item(self.text_input)
        
        self.image_input = ui.TextInput(
            label="Название файла изображения",
            placeholder="Например: report_va.png (файлы в папке files/reports/)",
            min_length=0,
            max_length=100,
            required=False,
            default=current_image
        )
        self.add_item(self.image_input)
        
        self.enabled_input = ui.TextInput(
            label="Включить уведомления? (да/нет)",
            placeholder="да - включить, нет - отключить",
            min_length=2,
            max_length=3,
            required=True,
            default="да" if current_enabled else "нет"
        )
        self.add_item(self.enabled_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            import os
            
            text = self.text_input.value.strip()
            image_filename = self.image_input.value.strip()
            enabled_str = self.enabled_input.value.strip().lower()
            
            # Validate enabled input
            if enabled_str not in ['да', 'нет', 'yes', 'no']:
                await self.send_error_message(
                    interaction,
                    "Неверное значение",
                    "Введите 'да' для включения или 'нет' для отключения уведомлений."
                )
                return
            
            enabled = enabled_str in ['да', 'yes']
            
            # Validate that at least text or image is provided if enabled
            if enabled and not text and not image_filename:
                await self.send_error_message(
                    interaction,
                    "Пустое уведомление",
                    "Для включения уведомлений укажите хотя бы текст или изображение."
                )
                return
            
            # Validate image file if provided
            image_path = None
            if image_filename:
                image_path = os.path.join('files', 'reports', image_filename)
                if not os.path.exists(image_path):
                    await self.send_error_message(
                        interaction,
                        "Файл не найден",
                        f"Изображение '{image_filename}' не найдено в папке files/reports/.\n"
                        f"Убедитесь, что файл существует и название указано правильно."
                    )
                    return
            
            # Save configuration
            config = load_config()
            if 'promotion_notifications' not in config:
                config['promotion_notifications'] = {}
            
            if self.department_code not in config['promotion_notifications']:
                config['promotion_notifications'][self.department_code] = {}
            
            config['promotion_notifications'][self.department_code] = {
                'text': text if text else None,
                'image': image_filename if image_filename else None,
                'enabled': enabled
            }
            
            save_config(config)
            
            # Initialize scheduler if not exists
            await self._ensure_scheduler_running()
            department_names = {
                'va': 'ВА (Военная Академия)',
                'vk': 'ВК (Военный Комиссариат)',
                'uvp': 'УВП (Военная Полиция)',
                'sso': 'ССО (Спецоперации)',
                'mr': 'МР (Медицинская Рота)',
                'roio': 'РОиО (Рота Охраны и Обеспечения)'
            }
            
            dept_name = department_names.get(self.department_code, self.department_code.upper())
            
            status = "включены" if enabled else "отключены"
            content_info = []
            if enabled:
                if text:
                    content_info.append("текст")
                if image_filename:
                    content_info.append("изображение")
                content_desc = f" ({', '.join(content_info)})" if content_info else ""
            else:
                content_desc = ""
              # Get configured notification time for success message
            schedule_config = config.get('notification_schedule', {'hour': 21, 'minute': 0})
            hour = schedule_config.get('hour', 21)
            minute = schedule_config.get('minute', 0)
            time_str = f"{hour:02d}:{minute:02d}"
            
            await self.send_success_message(
                interaction,
                "Уведомления настроены",
                f"Ежедневные уведомления для {dept_name} {status}{content_desc}.\n"
                f"{'Отправка в ' + time_str + ' МСК.' if enabled else ''}"
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке уведомлений: {str(e)}"
            )
    async def _ensure_scheduler_running(self):
        """Ensure the notification scheduler is running"""
        # This will be implemented when we add the scheduler to the main bot
        pass


class LeaveRequestsConfigView(BaseSettingsView):
    """View for leave requests channel configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("leave_requests")
        await interaction.response.send_modal(modal)    
    @discord.ui.button(label="👥 Кто может подать", style=discord.ButtonStyle.primary)
    async def set_allowed_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = LeaveRequestAllowedRolesModal()
        await interaction.response.send_modal(modal)


class LeaveRequestAllowedRolesModal(BaseSettingsModal):
    """Modal for setting allowed roles for leave requests"""
    
    def __init__(self):
        super().__init__(title="👥 Настройка ролей для отгулов")
        
        # Load current roles
        config = load_config()
        current_roles = config.get('leave_requests_allowed_roles', [])
        current_value = ", ".join([str(role_id) for role_id in current_roles]) if current_roles else ""
        
        self.roles_input = ui.TextInput(
            label="Роли (названия или ID через запятую)",
            placeholder="Например: Администратор, 123456789012345678, @Модератор",
            style=discord.TextStyle.paragraph,
            default=current_value,
            max_length=1000,
            required=False
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            roles_text = self.roles_input.value.strip()
            
            if not roles_text:
                # Clear roles - everyone can submit
                config = load_config()
                config['leave_requests_allowed_roles'] = []
                save_config(config)
                
                embed = discord.Embed(
                    title="✅ Роли сброшены",
                    description="Все пользователи теперь могут подавать заявки на отгул.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Parse roles
            parser = ChannelParser()
            role_ids = []
            
            for role_text in roles_text.split(','):
                role_text = role_text.strip()
                if not role_text:
                    continue
                
                # Try to find role by name or ID
                role = None
                
                # Try by ID first
                if role_text.isdigit():
                    role = interaction.guild.get_role(int(role_text))
                
                # Try by mention
                if not role and role_text.startswith('<@&') and role_text.endswith('>'):
                    try:
                        role_id = int(role_text[3:-1])
                        role = interaction.guild.get_role(role_id)
                    except ValueError:
                        pass
                
                # Try by name
                if not role:
                    for guild_role in interaction.guild.roles:
                        if guild_role.name.lower() == role_text.lower():
                            role = guild_role
                            break
                
                if role:
                    role_ids.append(role.id)
                else:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description=f"Роль '{role_text}' не найдена.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            
            # Save configuration
            config = load_config()
            config['leave_requests_allowed_roles'] = role_ids
            save_config(config)
            
            # Show success message
            if role_ids:
                role_mentions = []
                for role_id in role_ids:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_mentions.append(role.mention)
                
                embed = discord.Embed(
                    title="✅ Роли обновлены",
                    description=f"Подавать заявки на отгул могут пользователи с ролями:\n{chr(10).join(role_mentions)}",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="✅ Роли сброшены",
                    description="Все пользователи теперь могут подавать заявки на отгул.",
                    color=discord.Color.green()
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Произошла ошибка при настройке ролей: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
