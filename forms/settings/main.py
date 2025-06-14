"""
Main settings interface
"""
import discord
from discord import ui
from utils.config_manager import load_config
from .base import BaseSettingsView, ConfigDisplayHelper


class MainSettingsSelect(ui.Select):
    """Main settings dropdown menu"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Настройка каналов",
                description="Настроить каналы для различных систем бота",
                emoji="📂",
                value="channels"
            ),
            discord.SelectOption(
                label="Настройки пингов",
                description="Настроить пинги для уведомлений по подразделениям",
                emoji="📢",
                value="ping_settings"
            ),
            discord.SelectOption(
                label="Роли-исключения",
                description="Настроить роли, которые не снимаются при увольнении",
                emoji="🛡️",
                value="excluded_roles"
            ),
            discord.SelectOption(
                label="Показать текущие настройки",
                description="Посмотреть все текущие настройки",
                emoji="⚙️",
                value="show_config"
            )
        ]
        
        super().__init__(
            placeholder="Выберите категорию настроек...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="main_settings_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_option = self.values[0]
        
        if selected_option == "channels":
            await self.show_channels_menu(interaction)
        elif selected_option == "ping_settings":
            await self.show_ping_settings_menu(interaction)
        elif selected_option == "show_config":
            await self.show_current_config(interaction)
        elif selected_option == "excluded_roles":
            await self.show_excluded_roles_config(interaction)
    
    async def show_channels_menu(self, interaction: discord.Interaction):
        """Show submenu for channel configuration"""
        from .channels import ChannelsConfigView
        
        embed = discord.Embed(
            title="📂 Настройка каналов",
            description="Выберите канал для настройки из списка ниже.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Доступные каналы:",
            value=(
                "• **Канал увольнений** - для рапортов на увольнение\n"
                "• **Канал аудита** - для кадрового аудита\n"
                "• **Канал чёрного списка** - для записей чёрного списка\n"
                "• **Канал получения ролей** - для выбора военной/гражданской роли\n"
                "• **Регистрация модераторов** - для регистрации модераторов в системе\n"
                "• **Каналы отчётов на повышение** - для отчётов по подразделениям\n"
                "• **Канал отгулов** - для заявок на отгулы"
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Инструкция:",
            value="1. Выберите тип канала из списка\n2. Укажите канал (ID, упоминание или название)\n3. Бот автоматически настроит канал и добавит кнопки",
            inline=False
        )
        
        view = ChannelsConfigView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_ping_settings_menu(self, interaction: discord.Interaction):
        """Show ping settings configuration menu"""
        from .ping_settings import PingSettingsView
        
        config = load_config()
        ping_settings = config.get('ping_settings', {})
        
        embed = discord.Embed(
            title="📢 Настройки пингов",
            description="Управление пингами для уведомлений по подразделениям при подаче рапортов.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        # Show current ping settings
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
            ping_text = ping_text or "❌ Настроенные пинги не найдены"
        else:
            ping_text = "❌ Пинги не настроены"
        
        embed.add_field(
            name="🔔 Текущие настройки пингов:",
            value=ping_text,
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Принцип работы:",
            value=(
                "• При подаче рапорта на увольнение будут пинговаться указанные роли\n"
                "• Настройки привязаны к ролям подразделений\n"
                "• Можно настроить несколько ролей для пинга на одно подразделение"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Доступные действия:",
            value=(
                "• **Добавить настройку** - настроить пинги для нового подразделения\n"
                "• **Удалить настройку** - убрать пинги для подразделения\n"
                "• **Очистить все** - удалить все настройки пингов"
            ),
            inline=False
        )
        
        view = PingSettingsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_current_config(self, interaction: discord.Interaction):
        """Show current configuration"""
        config = load_config()
        helper = ConfigDisplayHelper()
        
        embed = discord.Embed(
            title="⚙️ Текущие настройки",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Channel configurations
        embed.add_field(
            name="📝 Канал увольнений", 
            value=helper.format_channel_info(config, 'dismissal_channel', interaction.guild), 
            inline=False
        )
        embed.add_field(
            name="🔍 Канал аудита", 
            value=helper.format_channel_info(config, 'audit_channel', interaction.guild), 
            inline=False
        )
        embed.add_field(
            name="🚫 Канал чёрного списка", 
            value=helper.format_channel_info(config, 'blacklist_channel', interaction.guild), 
            inline=False
        )
        embed.add_field(
            name="🎖️ Канал получения ролей", 
            value=helper.format_channel_info(config, 'role_assignment_channel', interaction.guild), 
            inline=False
        )
        # Role configurations
        embed.add_field(
            name="🛡️ Роли-исключения", 
            value=helper.format_roles_list(config, 'excluded_roles', interaction.guild), 
            inline=False
        )
        embed.add_field(
            name="🪖 Роли военнослужащих", 
            value=helper.format_roles_list(config, 'military_roles', interaction.guild), 
            inline=False
        )
        embed.add_field(
            name="👤 Роли гражданских", 
            value=helper.format_roles_list(config, 'civilian_roles', interaction.guild), 
            inline=False
        )
        embed.add_field(
            name="📢 Ping-роли для военных заявок", 
            value=helper.format_roles_list(config, 'military_role_assignment_ping_roles', interaction.guild), 
            inline=False
        )
        embed.add_field(
            name="📢 Ping-роли для гражданских заявок", 
            value=helper.format_roles_list(config, 'civilian_role_assignment_ping_roles', interaction.guild), 
            inline=False
        )
        
        # Ping settings
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
            ping_text = ping_text or "❌ Настройки не найдены"
        else:
            ping_text = "❌ Не настроены"
        embed.add_field(name="📢 Настройки пингов (увольнения)", value=ping_text, inline=False)
        
        # Blacklist ping settings
        blacklist_role_mentions = config.get('blacklist_role_mentions', [])
        if blacklist_role_mentions:
            blacklist_ping_roles = []
            for role_id in blacklist_role_mentions:
                role = interaction.guild.get_role(role_id)
                if role:
                    blacklist_ping_roles.append(role.mention)
                else:
                    blacklist_ping_roles.append(f"❌ Роль не найдена (ID: {role_id})")
            blacklist_ping_text = ", ".join(blacklist_ping_roles)
        else:
            blacklist_ping_text = "❌ Не настроены"
        
        embed.add_field(name="📢 Пинги чёрного списка", value=blacklist_ping_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def show_excluded_roles_config(self, interaction: discord.Interaction):
        """Show interface for managing excluded roles"""
        from .excluded_roles import ExcludedRolesView
        
        config = load_config()
        excluded_roles_ids = config.get('excluded_roles', [])
        
        embed = discord.Embed(
            title="🛡️ Управление ролями-исключениями",
            description="Роли, которые не будут сниматься при одобрении рапорта на увольнение.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Show current excluded roles
        if excluded_roles_ids:
            excluded_roles = []
            for role_id in excluded_roles_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    excluded_roles.append(f"• {role.mention}")
                else:
                    excluded_roles.append(f"• ❌ Роль не найдена (ID: {role_id})")
            excluded_text = "\n".join(excluded_roles)
        else:
            excluded_text = "❌ Роли-исключения не настроены"
        
        embed.add_field(name="Текущие роли-исключения:", value=excluded_text, inline=False)
        
        embed.add_field(
            name="ℹ️ Действия:",
            value=(
                "• **Добавить роли** - добавить новые роли в список исключений\n"
                "• **Удалить роли** - убрать роли из списка исключений\n"
                "• **Очистить список** - удалить все роли-исключения"
            ),
            inline=False
        )
        
        view = ExcludedRolesView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class SettingsView(BaseSettingsView):
    """Main settings view with persistent functionality"""
    
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(MainSettingsSelect())
    
    async def on_timeout(self):
        # This won't be called for persistent views, but good to have
        for item in self.children:
            item.disabled = True


async def send_settings_message(interaction: discord.Interaction):
    """Send the main settings interface"""
    embed = discord.Embed(
        title="⚙️ Панель настроек бота",
        description="Добро пожаловать в панель управления настройками бота! Здесь вы можете настроить все основные параметры работы системы.",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name="📝 Доступные категории:",
        value=(
            "• **📂 Настройка каналов** - настроить каналы для различных систем\n"
            "• **🛡️ Роли-исключения** - роли, не снимаемые при увольнении\n"
            "• **⚙️ Показать настройки** - просмотр текущих настроек"
        ),
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Как использовать:",
        value="1. Выберите категорию из главного меню\n2. Используйте подменю для настройки конкретных параметров\n3. Бот автоматически сохранит изменения",
        inline=False
    )
    
    embed.set_footer(text="Доступно только администраторам")
    
    view = SettingsView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
