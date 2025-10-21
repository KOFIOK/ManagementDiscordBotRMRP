"""
Constants for message service - colors, emojis, and standard values
"""
import discord

class MessageColors:
    """Standardized colors for different message types"""
    SUCCESS = discord.Color.green()
    ERROR = discord.Color.red()
    WARNING = discord.Color.orange()
    INFO = discord.Color.blue()
    NEUTRAL = discord.Color.from_rgb(128, 128, 128)  # Gray

    # Additional colors for specific use cases
    APPROVAL = discord.Color.green()
    REJECTION = discord.Color.red()
    NOTIFICATION = discord.Color.blue()
    MODERATION = discord.Color.orange()

class MessageEmojis:
    """Standardized emojis for different message types"""
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    LOADING = "⏳"
    APPROVAL = "✅"
    REJECTION = "❌"
    NOTIFICATION = "📢"
    MODERATION = "🛡️"

class MessageTypes:
    """Message type constants"""
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"
    INFO = "info"
    APPROVAL = "approval"
    REJECTION = "rejection"
    NOTIFICATION = "notification"