"""
Dismissal system utilities
Contains helper functions for message management and view restoration
"""

import discord
from discord import ui
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


async def send_dismissal_button_message(channel):
    """Send dismissal button message, avoiding duplicates using pinned messages."""
    
    # Check pinned messages first for dismissal message
    try:
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and
                message.embeds[0].title and
                "Рапорты на увольнение" in message.embeds[0].title):
                
                # Found pinned dismissal message, restore the view
                from .views import DismissalReportButton
                view = DismissalReportButton()
                try:
                    await message.edit(view=view)
                    logger.info(f"Updated existing pinned dismissal message {message.id}")
                    return
                except Exception as e:
                    logger.error("Error updating pinned dismissal message: %s", e)
                    # If update fails, unpin and delete old message, create new one
                    try:
                        await message.unpin()
                        await message.delete()
                        logger.info(f"Removed old pinned dismissal message {message.id}")
                    except:
                        pass
                    break
    except Exception as e:
        logger.error("Error checking pinned messages for dismissal: %s", e)
    # Create new message if none exists or old one couldn't be updated
    embed = discord.Embed(
        title="Рапорты на увольнение",
        description="Выберите причину увольнения и заполните форму.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Доступные варианты", 
        value="• **ПСЖ** - По собственному желанию\n• **Перевод** - Перевод в другую фракцию",
        inline=False
    )
    
    embed.add_field(
        name="Инструкция", 
        value="1. Выберите причину увольнения\n2. Заполните автоматически открывшуюся форму\n3. Ваш рапорт будет рассматриваться в течении __24 часов__.", 
        inline=False
    )
    
    from .views import DismissalReportButton
    view = DismissalReportButton()
    message = await channel.send(embed=embed, view=view)
    
    # Pin the new message for easy access
    try:
        await message.pin()
        logger.info(f"Pinned new dismissal message {message.id}")
        
        # TODO: Save message ID for footer links when we implement clickable solution
        # from utils.config_manager import save_dismissal_message_id
        # save_dismissal_message_id(message.id)
        # print(f"Saved dismissal message ID: {message.id}")
        
    except Exception as e:
        logger.error("Error pinning dismissal message: %s", e)


async def restore_dismissal_approval_views(bot, channel):
    """Restore approval views for existing dismissal report messages."""
    try:
        async for message in channel.history(limit=50):
            # Check if message is from bot and has dismissal report embed
            if (message.author == bot.user and 
                message.embeds and
                message.embeds[0].title and
                "Рапорт на увольнение" in message.embeds[0].title):
                
                embed = message.embeds[0]
                
                # Check if report is still pending (not approved/rejected)
                # We check if there's no "✅ Обработано" field, which means it's still pending
                status_pending = True
                for field in embed.fields:
                    if field.name in ["✅ Обработано", "Отказано"]:
                        status_pending = False
                        break
                
                if status_pending:
                    # Try to extract user ID from content mention
                    user_id = None
                    if message.content:
                        import re
                        user_mention_pattern = r'<@(\d+)>'
                        match = re.search(user_mention_pattern, message.content)
                        if match:
                            user_id = int(match.group(1))
                    
                    # Use the new SimplifiedDismissalApprovalView
                    from .views import SimplifiedDismissalApprovalView
                    view = SimplifiedDismissalApprovalView(user_id=user_id)
                      
                    # Edit message to restore the view
                    try:
                        await message.edit(view=view)
                        logger.info(f"Restored simplified approval view for dismissal report message {message.id}")
                    except discord.NotFound:
                        continue
                    except Exception as e:
                        logger.error(f"Error restoring view for message {message.id}: %s", e)
                        
    except Exception as e:
        logger.error("Error restoring dismissal approval views: %s", e)


async def restore_dismissal_button_views(bot, channel):
    """Restore dismissal button views for existing dismissal button messages using pinned messages."""
    try:
        # Check pinned messages first
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == bot.user and 
                message.embeds and
                message.embeds[0].title and
                "Рапорты на увольнение" in message.embeds[0].title):
                
                # Add the view back to the pinned message
                from .views import DismissalReportButton
                view = DismissalReportButton()
                try:
                    await message.edit(view=view)
                    logger.info(f"Restored dismissal button view for pinned message {message.id}")
                    return  # Found and restored pinned message
                except discord.NotFound:
                    continue
                except Exception as e:
                    logger.error(f"Error restoring dismissal button view for pinned message {message.id}: %s", e)
        
        # If no pinned message found, check recent history as fallback
        async for message in channel.history(limit=50):
            # Check if message is from bot and has dismissal button embed
            if (message.author == bot.user and 
                message.embeds and
                message.embeds[0].title and
                "Рапорты на увольнение" in message.embeds[0].title):
                
                # Add the view back to the message
                from .views import DismissalReportButton
                view = DismissalReportButton()
                try:
                    await message.edit(view=view)
                    logger.info(f"Restored dismissal button view for message {message.id}")
                except discord.NotFound:
                    continue
                except Exception as e:
                    logger.error(f"Error restoring dismissal button view for message {message.id}: %s", e)                    
    except Exception as e:
        logger.error("Error restoring dismissal button views: %s", e)
