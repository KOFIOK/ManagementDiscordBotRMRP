"""
Other channels configuration (audit, blacklist, medical, leave requests)
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, ConfigDisplayHelper, RoleParser
from .channels_base import ChannelSelectionModal


# Blacklist Channel Configuration
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
                "Нет пинг-ролей",
                "Пинг-роли для чёрного списка не настроены."
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
            # Parse role input
            role = RoleParser.parse_role_input(
                self.role_input.value.strip(), 
                interaction.guild
            )
            
            if not role:
                await self.send_error_message(
                    interaction,
                    "Роль не найдена",
                    f"Роль '{self.role_input.value.strip()}' не найдена на сервере."
                )
                return
            
            # Load config
            config = load_config()
            blacklist_role_mentions = config.get('blacklist_role_mentions', [])
            
            if self.action == "add":
                if role.id not in blacklist_role_mentions:
                    blacklist_role_mentions.append(role.id)
                    config['blacklist_role_mentions'] = blacklist_role_mentions
                    save_config(config)
                    
                    await self.send_success_message(
                        interaction,
                        "Пинг-роль добавлена",
                        f"Роль {role.mention} добавлена в список пинг-ролей для чёрного списка."
                    )
                else:
                    await self.send_error_message(
                        interaction,
                        "Роль уже добавлена",
                        f"Роль {role.mention} уже находится в списке пинг-ролей."
                    )
            
            else:  # remove
                if role.id in blacklist_role_mentions:
                    blacklist_role_mentions.remove(role.id)
                    config['blacklist_role_mentions'] = blacklist_role_mentions
                    save_config(config)
                    
                    await self.send_success_message(
                        interaction,
                        "Пинг-роль удалена",
                        f"Роль {role.mention} удалена из списка пинг-ролей для чёрного списка."
                    )
                else:
                    await self.send_error_message(
                        interaction,
                        "Роль не найдена",
                        f"Роль {role.mention} не находится в списке пинг-ролей."
                    )
                
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при обработке роли: {str(e)}"
            )


# Leave Requests Channel Configuration
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
                # Clear all roles
                config = load_config()
                config['leave_requests_allowed_roles'] = []
                save_config(config)
                
                await self.send_success_message(
                    interaction,
                    "Роли очищены",
                    "Список ролей для отгулов очищен. Теперь никто не может подавать заявки на отгул."
                )
                return
            
            # Parse roles
            role_ids = []
            roles_list = [r.strip() for r in roles_text.split(',')]
            
            for role_input in roles_list:
                role = RoleParser.parse_role_input(role_input, interaction.guild)
                if role:
                    role_ids.append(role.id)
                else:
                    await self.send_error_message(
                        interaction,
                        "Роль не найдена",
                        f"Роль '{role_input}' не найдена на сервере."
                    )
                    return
            
            # Save configuration
            config = load_config()
            config['leave_requests_allowed_roles'] = role_ids
            save_config(config)
            
            role_mentions = [f"<@&{role_id}>" for role_id in role_ids]
            await self.send_success_message(
                interaction,
                "Роли настроены",
                f"Роли для подачи заявок на отгул настроены:\n{', '.join(role_mentions)}"
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке ролей: {str(e)}"
            )


# Medical Registration Channel Configuration
class MedicalRegistrationConfigView(BaseSettingsView):
    """View for medical registration channel configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("medical_registration")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👩‍⚕️ Роль медицинской роты", style=discord.ButtonStyle.primary)
    async def set_medical_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MedicalRoleModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🩺 Роли доступа ВВК", style=discord.ButtonStyle.secondary)
    async def set_vvk_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MedicalVVKRolesModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📚 Роли доступа лекций", style=discord.ButtonStyle.secondary)
    async def set_lecture_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MedicalLectureRolesModal()
        await interaction.response.send_modal(modal)


class MedicalRoleModal(BaseSettingsModal):
    """Modal for setting medical role"""
    
    def __init__(self):
        super().__init__(title="👩‍⚕️ Настройка роли медицинской роты")
        
        # Load current role
        config = load_config()
        current_role_id = config.get('medical_role_id')
        current_value = str(current_role_id) if current_role_id else ""
        
        self.role_input = ui.TextInput(
            label="Роль медицинской роты (название или ID)",
            placeholder="Например: Медицинская Рота или 123456789012345678",
            style=discord.TextStyle.short,
            default=current_value,
            max_length=100,
            required=False
        )
        self.add_item(self.role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            role_input = self.role_input.value.strip()
            
            if not role_input:
                # Clear role
                config = load_config()
                config['medical_role_id'] = None
                save_config(config)
                
                await self.send_success_message(
                    interaction,
                    "Роль очищена",
                    "Роль медицинской роты очищена."
                )
                return
            
            # Parse role
            role = RoleParser.parse_role_input(role_input, interaction.guild)
            
            if not role:
                await self.send_error_message(
                    interaction,
                    "Роль не найдена",
                    f"Роль '{role_input}' не найдена на сервере."
                )
                return
            
            # Save configuration
            config = load_config()
            config['medical_role_id'] = role.id
            save_config(config)
            
            await self.send_success_message(
                interaction,
                "Роль настроена",
                f"Роль медицинской роты установлена: {role.mention}"
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке роли: {str(e)}"
            )


class MedicalVVKRolesModal(BaseSettingsModal):
    """Modal for setting allowed roles for VVK"""
    
    def __init__(self):
        super().__init__(title="🩺 Настройка ролей доступа к ВВК")
        
        # Load current roles
        config = load_config()
        current_roles = config.get('medical_vvk_allowed_roles', [])
        current_value = ", ".join([str(role_id) for role_id in current_roles]) if current_roles else ""
        
        self.roles_input = ui.TextInput(
            label="Роли (названия или ID через запятую)",
            placeholder="Например: Военнослужащий ВС РФ, 123456789012345678, @Офицер",
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
                # Clear all roles
                config = load_config()
                config['medical_vvk_allowed_roles'] = []
                save_config(config)
                
                await self.send_success_message(
                    interaction,
                    "Роли очищены",
                    "Роли доступа к ВВК очищены."
                )
                return
            
            # Parse roles
            role_ids = []
            roles_list = [r.strip() for r in roles_text.split(',')]
            
            for role_input in roles_list:
                role = RoleParser.parse_role_input(role_input, interaction.guild)
                if role:
                    role_ids.append(role.id)
                else:
                    await self.send_error_message(
                        interaction,
                        "Роль не найдена",
                        f"Роль '{role_input}' не найдена на сервере."
                    )
                    return
            
            # Save configuration
            config = load_config()
            config['medical_vvk_allowed_roles'] = role_ids
            save_config(config)
            
            role_mentions = [f"<@&{role_id}>" for role_id in role_ids]
            await self.send_success_message(
                interaction,
                "Роли настроены",
                f"Роли доступа к ВВК настроены:\n{', '.join(role_mentions)}"
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке ролей: {str(e)}"
            )


class MedicalLectureRolesModal(BaseSettingsModal):
    """Modal for setting allowed roles for lectures"""
    
    def __init__(self):
        super().__init__(title="📚 Настройка ролей доступа к лекциям")
        
        # Load current roles
        config = load_config()
        current_roles = config.get('medical_lecture_allowed_roles', [])
        current_value = ", ".join([str(role_id) for role_id in current_roles]) if current_roles else ""
        
        self.roles_input = ui.TextInput(
            label="Роли (названия или ID через запятую)",
            placeholder="Например: Военнослужащий ВС РФ, 123456789012345678, @Офицер",
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
                # Clear all roles
                config = load_config()
                config['medical_lecture_allowed_roles'] = []
                save_config(config)
                
                await self.send_success_message(
                    interaction,
                    "Роли очищены",
                    "Роли доступа к лекциям очищены."
                )
                return
            
            # Parse roles
            role_ids = []
            roles_list = [r.strip() for r in roles_text.split(',')]
            
            for role_input in roles_list:
                role = RoleParser.parse_role_input(role_input, interaction.guild)
                if role:
                    role_ids.append(role.id)
                else:
                    await self.send_error_message(
                        interaction,
                        "Роль не найдена",
                        f"Роль '{role_input}' не найдена на сервере."
                    )
                    return
            
            # Save configuration
            config = load_config()
            config['medical_lecture_allowed_roles'] = role_ids
            save_config(config)
            
            role_mentions = [f"<@&{role_id}>" for role_id in role_ids]
            await self.send_success_message(
                interaction,
                "Роли настроены",
                f"Роли доступа к лекциям настроены:\n{', '.join(role_mentions)}"
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке ролей: {str(e)}"
            )


# Show functions
async def show_blacklist_config(interaction: discord.Interaction):
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
            ping_roles.append(role.mention if role else f"<@&{role_id}> (роль не найдена)")
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


async def show_leave_requests_config(interaction: discord.Interaction):
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
            roles_text = helper.format_roles_list(config, 'leave_requests_allowed_roles', interaction.guild)
        else:
            roles_text = "❌ Роли не настроены"
        
        embed.add_field(
            name="👥 Кто может подавать заявки:",
            value=roles_text,
            inline=False
        )
        
        embed.add_field(
            name="🔧 Доступные действия:",
            value="Выберите действие для настройки системы отгулов:",
            inline=False
        )
        
        view = LeaveRequestsConfigView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        print(f"❌ ERROR in show_leave_requests_config: {e}")
        import traceback
        traceback.print_exc()
        # Try to send error message if interaction hasn't been responded to yet
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Произошла ошибка при загрузке настроек отгулов.",
                ephemeral=True
            )
        raise


async def show_medical_registration_config(interaction: discord.Interaction):
    """Show medical registration channel configuration"""
    try:
        embed = discord.Embed(
            title="🏥 Настройка канала записи к врачу",
            description="Управление каналом для записи к врачу медицинской роты.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        config = load_config()
        helper = ConfigDisplayHelper()
        
        # Show current channel
        embed.add_field(
            name="📂 Текущий канал:",
            value=helper.format_channel_info(config, 'medical_registration_channel', interaction.guild),
            inline=False
        )
        
        # Show medical role ID (for pings)
        medic_role_id = config.get('medical_role_id')
        if medic_role_id:
            role = interaction.guild.get_role(medic_role_id)
            medic_text = role.mention if role else f"❌ Роль не найдена (ID: {medic_role_id})"
        else:
            medic_text = "❌ Роль не настроена"
        
        embed.add_field(
            name="👩‍⚕️ Роль медицинской роты:",
            value=medic_text,
            inline=True
        )
        
        # Show allowed roles for VVK
        vvk_roles = config.get('medical_vvk_allowed_roles', [])
        if vvk_roles:
            vvk_text = helper.format_roles_list(config, 'medical_vvk_allowed_roles', interaction.guild)
        else:
            vvk_text = "❌ Роли не настроены"
        
        embed.add_field(
            name="🩺 Доступ к ВВК:",
            value=vvk_text,
            inline=True
        )
        
        # Show allowed roles for lectures
        lecture_roles = config.get('medical_lecture_allowed_roles', [])
        if lecture_roles:
            lecture_text = helper.format_roles_list(config, 'medical_lecture_allowed_roles', interaction.guild)
        else:
            lecture_text = "❌ Роли не настроены"
        
        embed.add_field(
            name="📚 Доступ к лекциям:",
            value=lecture_text,
            inline=True
        )
        
        embed.add_field(
            name="🔧 Доступные действия:",
            value="Выберите действие для настройки медицинского канала:",
            inline=False
        )
        
        view = MedicalRegistrationConfigView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        print(f"❌ ERROR in show_medical_registration_config: {e}")
        import traceback
        traceback.print_exc()
        # Try to send error message if interaction hasn't been responded to yet
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Произошла ошибка при загрузке настроек медицинского канала.",
                ephemeral=True
            )
        raise


# Safe Documents Channel Configuration
class SafeDocumentsChannelView(BaseSettingsView):
    """View for safe documents channel configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("safe_documents")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Удалить канал", style=discord.ButtonStyle.red)
    async def remove_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        config['safe_documents_channel'] = None
        save_config(config)
        
        await self.send_success_message(
            interaction,
            "Канал удален",
            "Канал для заявок на безопасные документы был удален из настроек."
        )


async def show_safe_documents_config(interaction: discord.Interaction):
    """Show safe documents channel configuration"""
    try:
        config = load_config()
        helper = ConfigDisplayHelper()
        
        embed = discord.Embed(
            title="📋 Настройка канала сейф документов",
            description="Настройте канал для заявок на безопасное хранение документов.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Текущий канал
        current_channel = helper.format_channel_info(config, 'safe_documents_channel', interaction.guild)
        embed.add_field(
            name="📂 Текущий канал:",
            value=current_channel,
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Описание системы:",
            value=(
                "Система безопасных документов позволяет пользователям подавать заявки на размещение "
                "документов в безопасном хранилище. Модераторы могут одобрять или отклонять заявки.\n\n"
                "**Возможности:**\n"
                "• Автозаполнение формы из профиля пользователя\n"
                "• Модерация заявок с проверкой прав\n"
                "• Редактирование заявок автором или модераторами\n"
                "• Уведомления о результатах рассмотрения\n"
                "• Пинги ролей при новых заявках"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Доступные действия:",
            value="Выберите действие для настройки канала сейф документов:",
            inline=False
        )
        
        view = SafeDocumentsChannelView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        print(f"❌ ERROR in show_safe_documents_config: {e}")
        import traceback
        traceback.print_exc()
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Произошла ошибка при загрузке настроек канала сейф документов.",
                ephemeral=True
            )
        raise
