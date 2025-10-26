"""
Constants for message service - colors, emojis, and standard values

ARCHITECTURE NOTE:
This file contains PROGRAMMATIC constants used directly in Python code.
These are separate from YAML message templates for the following reasons:

1. COLORS: discord.Color objects cannot be serialized to YAML
2. EMOJIS: While emojis appear in both places, they serve different purposes:
   - Here: Direct programmatic use in message_service.py
   - YAML: Template building blocks for configurable message composition
3. TYPES: String constants for programmatic message type checking

YAML (messages-default.yml) handles USER-CONFIGURABLE text and templates,
while this file handles SYSTEM constants that code depends on.
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