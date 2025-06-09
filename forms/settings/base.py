"""
Base classes and utilities for settings forms
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config


class BaseSettingsView(ui.View):
    """Base class for all settings views with common functionality"""
    
    def __init__(self, timeout=300):
        super().__init__(timeout=timeout)
    
    async def send_success_message(self, interaction: discord.Interaction, title: str, description: str):
        """Send a standardized success message"""
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def send_error_message(self, interaction: discord.Interaction, title: str, description: str):
        """Send a standardized error message"""
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BaseSettingsModal(ui.Modal):
    """Base class for all settings modals with common functionality"""
    
    async def send_success_message(self, interaction: discord.Interaction, title: str, description: str):
        """Send a standardized success message"""
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def send_error_message(self, interaction: discord.Interaction, title: str, description: str):
        """Send a standardized error message"""
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfigDisplayHelper:
    """Helper class for displaying configuration information"""
    
    @staticmethod
    def format_channel_info(config: dict, channel_key: str, guild: discord.Guild) -> str:
        """Format channel information for display"""
        channel_id = config.get(channel_key)
        if channel_id:
            channel = guild.get_channel(channel_id)
            return channel.mention if channel else f"❌ Канал не найден (ID: {channel_id})"
        return "❌ Не настроен"
    
    @staticmethod
    def format_role_info(config: dict, role_key: str, guild: discord.Guild) -> str:
        """Format role information for display"""
        role_id = config.get(role_key)
        if role_id:
            role = guild.get_role(role_id)
            return role.mention if role else f"❌ Роль не найдена (ID: {role_id})"
        return "❌ Не настроена"
    
    @staticmethod
    def format_roles_list(config: dict, roles_key: str, guild: discord.Guild) -> str:
        """Format list of roles for display"""
        role_ids = config.get(roles_key, [])
        if role_ids:
            roles = []
            for role_id in role_ids:
                role = guild.get_role(role_id)
                if role:
                    roles.append(role.mention)
                else:
                    roles.append(f"❌ Роль не найдена (ID: {role_id})")
            return "\n".join(roles) if roles else "❌ Роли не найдены"
        return "❌ Не настроены"


class RoleParser:
    """Helper class for parsing role inputs"""
    
    @staticmethod
    def parse_role_input(role_text: str, guild: discord.Guild) -> discord.Role:
        """Parse role from mention, ID, or name"""
        role_text = role_text.strip()
        
        # Try to parse role mention
        if role_text.startswith('<@&') and role_text.endswith('>'):
            role_id = int(role_text[3:-1])
            return guild.get_role(role_id)
        
        # Try to parse role ID
        if role_text.isdigit():
            return guild.get_role(int(role_text))
        
        # Try to find role by name
        return discord.utils.get(guild.roles, name=role_text)
    
    @staticmethod
    def parse_multiple_roles(roles_text: str, guild: discord.Guild) -> list[discord.Role]:
        """Parse multiple roles from comma-separated input"""
        roles = []
        for role_part in roles_text.split(','):
            role = RoleParser.parse_role_input(role_part.strip(), guild)
            if role:
                roles.append(role)
        return roles


class ChannelParser:
    """Helper class for parsing channel inputs"""
    
    @staticmethod
    def parse_channel_input(channel_text: str, guild: discord.Guild) -> discord.TextChannel:
        """Parse channel from mention, ID, or name"""
        channel_text = channel_text.strip()
        
        # Try to parse channel mention
        if channel_text.startswith('<#') and channel_text.endswith('>'):
            channel_id = int(channel_text[2:-1])
            return guild.get_channel(channel_id)
        
        # Try to parse channel ID
        if channel_text.isdigit():
            return guild.get_channel(int(channel_text))
        
        # Try to find channel by name (with smart normalization)
        return ChannelParser._find_channel_by_name(guild, channel_text)
    
    @staticmethod
    def _normalize_channel_name(channel_name: str, is_text_channel=True) -> str:
        """Normalize channel name by removing cosmetic elements"""
        # Remove # prefix if present
        if channel_name.startswith('#'):
            channel_name = channel_name[1:]
        
        # Remove common cosmetic patterns
        import re
        cosmetic_patterns = [
            r'^[├└┬┴│┌┐┘┤┼─┴┬]+[「『【\[].*?[」』】\]][^a-zA-Zа-яё0-9\-_\s]*',
            r'^[├└┬┴│┌┐┘┤┼─┴┬]+[^a-zA-Zа-яё0-9\-_\s]*',
            r'^[「『【\[].*?[」』】\]][^a-zA-Zа-яё0-9\-_\s]*',
            r'^[^\w\-а-яё\s]*',
        ]
        
        for pattern in cosmetic_patterns:
            channel_name = re.sub(pattern, '', channel_name, flags=re.UNICODE)
        
        # Remove trailing non-word characters
        channel_name = re.sub(r'[^\w\-а-яё\s]*$', '', channel_name, flags=re.UNICODE)
        
        # Convert spaces to hyphens for text channels
        if is_text_channel:
            channel_name = channel_name.replace(' ', '-')
        
        return channel_name.strip()
    
    @staticmethod
    def _find_channel_by_name(guild: discord.Guild, search_name: str) -> discord.TextChannel:
        """Smart channel search that ignores cosmetic elements"""
        normalized_search_text = ChannelParser._normalize_channel_name(search_name, is_text_channel=True).lower()
        
        if normalized_search_text:
            # Try exact match
            for channel in guild.text_channels:
                normalized_channel_name = ChannelParser._normalize_channel_name(channel.name, is_text_channel=True).lower()
                if normalized_channel_name == normalized_search_text:
                    return channel
            
            # Try partial match
            for channel in guild.text_channels:
                normalized_channel_name = ChannelParser._normalize_channel_name(channel.name, is_text_channel=True).lower()
                if normalized_search_text in normalized_channel_name or normalized_channel_name in normalized_search_text:
                    return channel
        
        # Fallback to Discord's built-in search
        return discord.utils.get(guild.text_channels, name=search_name)
