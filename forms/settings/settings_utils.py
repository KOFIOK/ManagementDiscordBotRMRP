"""
Utility functions for settings forms
"""
import discord
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.config_manager import load_config


def get_user_department_role(user: discord.Member, ping_settings: dict) -> discord.Role:
    """Get the user's department role that has ping settings configured"""
    for department_role_id in ping_settings.keys():
        department_role = user.guild.get_role(int(department_role_id))
        if department_role and department_role in user.roles:
            return department_role
    return None


def get_ping_roles_for_department(department_role: discord.Role, ping_settings: dict, guild: discord.Guild) -> list[discord.Role]:
    """Get ping roles for a specific department"""
    if not department_role:
        return []
    
    ping_role_ids = ping_settings.get(str(department_role.id), [])
    ping_roles = []
    
    for role_id in ping_role_ids:
        role = guild.get_role(role_id)
        if role:
            ping_roles.append(role)
    
    return ping_roles


def get_user_ping_roles(user: discord.Member) -> list[discord.Role]:
    """Get all ping roles for a user based on their department roles"""
    config = load_config()
    ping_settings = config.get('ping_settings', {})
    
    ping_roles = []
    department_role = get_user_department_role(user, ping_settings)
    
    if department_role:
        ping_roles = get_ping_roles_for_department(department_role, ping_settings, user.guild)
    
    return ping_roles


def format_ping_settings_display(ping_settings: dict, guild: discord.Guild) -> str:
    """Format ping settings for display in embeds"""
    if not ping_settings:
        return "❌ Настройки пингов не настроены"
    
    ping_text = ""
    for department_role_id, ping_roles_ids in ping_settings.items():
        department_role = guild.get_role(int(department_role_id))
        if department_role:
            ping_roles = []
            for ping_role_id in ping_roles_ids:
                ping_role = guild.get_role(ping_role_id)
                if ping_role:
                    ping_roles.append(ping_role.mention)
            if ping_roles:
                ping_text += f"• {department_role.mention} → {', '.join(ping_roles)}\n"
    
    return ping_text or "❌ Настройки пингов не найдены"


def validate_channel_permissions(channel: discord.TextChannel, bot_member: discord.Member) -> tuple[bool, str]:
    """Validate that bot has necessary permissions in the channel"""
    permissions = channel.permissions_for(bot_member)
    
    missing_permissions = []
    
    if not permissions.send_messages:
        missing_permissions.append("Отправка сообщений")
    if not permissions.embed_links:
        missing_permissions.append("Встраивание ссылок")
    if not permissions.use_external_emojis:
        missing_permissions.append("Использование внешних эмодзи")
    if not permissions.add_reactions:
        missing_permissions.append("Добавление реакций")
    
    if missing_permissions:
        return False, f"Боту не хватает следующих разрешений в канале {channel.mention}:\n• " + "\n• ".join(missing_permissions)
    
    return True, "Все необходимые разрешения присутствуют"


def validate_role_hierarchy(role: discord.Role, bot_member: discord.Member) -> tuple[bool, str]:
    """Validate that bot can manage the role"""
    if role.position >= bot_member.top_role.position:
        return False, f"Роль {role.mention} находится выше роли бота в иерархии. Бот не сможет управлять этой ролью."
    
    if role.managed:
        return False, f"Роль {role.mention} управляется интеграцией и не может быть изменена ботом."
    
    return True, "Роль может быть управляема ботом"


def create_channel_select(placeholder: str = "Выберите канал") -> discord.ui.ChannelSelect:
    """Создает селектор каналов"""
    return discord.ui.ChannelSelect(
        placeholder=placeholder,
        channel_types=[discord.ChannelType.text],
        min_values=1,
        max_values=1
    )


def create_role_select(placeholder: str = "Выберите роль") -> discord.ui.RoleSelect:
    """Создает селектор ролей"""
    return discord.ui.RoleSelect(
        placeholder=placeholder,
        min_values=1,
        max_values=1
    )
