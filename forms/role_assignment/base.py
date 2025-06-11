"""
Base utilities for role assignment system
"""

import discord


def create_approval_view(application_data):
    """
    Factory function to create approval view, avoiding circular imports.
    
    Args:
        application_data: Dictionary containing application information
        
    Returns:
        RoleApplicationApprovalView instance
    """
    # Import here to avoid circular dependency
    from .approval import RoleApplicationApprovalView
    return RoleApplicationApprovalView(application_data)


async def get_channel_with_fallback(bot_or_guild, channel_id, channel_name="audit channel"):
    """
    Safely get a channel with fallback mechanisms.
    
    Args:
        bot_or_guild: Either bot instance or guild instance
        channel_id: The channel ID to find
        channel_name: Description of the channel for logging
        
    Returns:
        discord.TextChannel or None
    """
    if not channel_id:
        return None
    
    try:
        # Try 1: Use guild.get_channel() (fastest, cached)
        if hasattr(bot_or_guild, 'get_channel'):
            channel = bot_or_guild.get_channel(channel_id)
            if channel:
                return channel
        
        # Try 2: Use bot.fetch_channel() (slower, API call)
        if hasattr(bot_or_guild, 'fetch_channel'):
            try:
                channel = await bot_or_guild.fetch_channel(channel_id)
                if channel:
                    return channel
            except discord.NotFound:
                pass  # Channel doesn't exist
            except discord.Forbidden:
                pass  # No access to channel
            except Exception:
                pass  # Other API errors
        
        # Try 3: If we have a guild object, try to find in all channels
        guild = bot_or_guild if hasattr(bot_or_guild, 'channels') else getattr(bot_or_guild, 'guild', None)
        if guild and hasattr(guild, 'channels'):
            for channel in guild.channels:
                if channel.id == channel_id and isinstance(channel, discord.TextChannel):
                    return channel
        
        return None
        
    except Exception:
        return None
