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
    
    @discord.ui.button(label="⭐ Начальное звание", style=discord.ButtonStyle.primary)
    async def set_default_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure default recruit rank"""
        view = DefaultRankConfigView()
        await view.show_default_rank_config(interaction)
    
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


class DefaultRankConfigView(BaseSettingsView):
    """View for configuring default recruit rank"""
    
    def __init__(self):
        super().__init__()
    
    async def show_default_rank_config(self, interaction: discord.Interaction):
        """Show default rank configuration interface"""
        embed = discord.Embed(
            title="⭐ Настройка начального звания",
            description="Выберите звание, которое будет присваиваться новым рекрутам по умолчанию.",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        config = load_config()
        helper = ConfigDisplayHelper()
        
        # Get current default rank
        default_rank_id = config.get('default_recruit_rank_id')
        current_rank_text = "❌ Не настроено"
        
        if default_rank_id:
            from utils.database_manager.rank_manager import RankManager
            rank_manager = RankManager()
            try:
                rank = await rank_manager.get_rank_by_id(default_rank_id)
                if rank:
                    role = interaction.guild.get_role(rank.role_id)
                    current_rank_text = f"✅ {rank.name} ({role.mention if role else 'Роль не найдена'})"
                else:
                    current_rank_text = "❌ Звание не найдено в базе данных"
            except Exception as e:
                current_rank_text = f"❌ Ошибка загрузки: {str(e)}"
        
        embed.add_field(
            name="🎖️ Текущее начальное звание:",
            value=current_rank_text,
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Информация:",
            value="Выберите звание из списка доступных. Новые рекруты будут получать это звание автоматически при вступлении в армию.",
            inline=False
        )
        
        view = DefaultRankButtonsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class DefaultRankButtonsView(BaseSettingsView):
    """Buttons for default rank configuration"""
    
    @discord.ui.button(label="🎖️ Выбрать звание", style=discord.ButtonStyle.primary)
    async def select_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show rank selection modal"""
        modal = DefaultRankSelectionModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔄 Сбросить", style=discord.ButtonStyle.danger)
    async def reset_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reset default rank to none"""
        config = load_config()
        if 'default_recruit_rank_id' in config:
            del config['default_recruit_rank_id']
            save_config(config)
        
        embed = discord.Embed(
            title="✅ Сброшено",
            description="Начальное звание сброшено. Новые рекруты не будут получать автоматическое звание.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class DefaultRankSelectionModal(BaseSettingsModal):
    """Modal for selecting default recruit rank"""
    
    def __init__(self):
        super().__init__(title="🎖️ Выбор начального звания")
    
    rank_selection = ui.TextInput(
        label="ID звания",
        placeholder="Введите ID звания из базы данных",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle rank selection submission"""
        try:
            rank_id = int(self.rank_selection.value.strip())
            
            from utils.database_manager.rank_manager import RankManager
            rank_manager = RankManager()
            
            # Validate rank exists
            rank = await rank_manager.get_rank_by_id(rank_id)
            if not rank:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Звание с ID {rank_id} не найдено в базе данных.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check if role exists in guild
            role = interaction.guild.get_role(rank.role_id)
            if not role:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Роль для звания '{rank.name}' не найдена на сервере.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Save configuration
            config = load_config()
            config['default_recruit_rank_id'] = rank_id
            save_config(config)
            
            embed = discord.Embed(
                title="✅ Настроено",
                description=f"Начальное звание установлено: **{rank.name}** ({role.mention})",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="ID звания должен быть числом.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Произошла ошибка: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


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
    
    # Show default recruit rank
    default_rank_id = config.get('default_recruit_rank_id')
    default_rank_text = "❌ Не настроено"
    
    if default_rank_id:
        from utils.database_manager.rank_manager import RankManager
        rank_manager = RankManager()
        try:
            rank = await rank_manager.get_rank_by_id(default_rank_id)
            if rank:
                role = interaction.guild.get_role(rank.role_id)
                default_rank_text = f"✅ {rank.name} ({role.mention if role else 'Роль не найдена'})"
            else:
                default_rank_text = "❌ Звание не найдено в базе данных"
        except Exception as e:
            default_rank_text = f"❌ Ошибка загрузки: {str(e)}"
    
    embed.add_field(
        name="⭐ Начальное звание для рекрутов:",
        value=default_rank_text,
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Доступные действия:",
        value=(
            "• **Настроить канал** - установить канал для получения ролей\n"
            "• **Настроить роли** - настроить роли для военных, доступа к поставкам и госслужащих\n"
            "• **Настроить пинги** - настроить роли для уведомлений\n"
            "• **Начальное звание** - настроить звание для новых рекрутов\n"
            "• **Полная настройка** - настроить всё сразу"
        ),
        inline=False
    )
    
    view = RoleAssignmentChannelView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
