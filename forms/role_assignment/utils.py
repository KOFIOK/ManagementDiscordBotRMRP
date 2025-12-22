"""
Utility functions for role assignment system
"""

import discord
import re
from .views import RoleAssignmentView
from .base import create_approval_view
from utils.config_manager import save_role_assignment_message_id
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


async def send_role_assignment_message(channel):
    """Send role assignment message with buttons, avoiding duplicates using pinned messages."""
    
    # Check pinned messages first for role assignment message
    try:
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and
                message.embeds[0].title and
                "Получение ролей" in message.embeds[0].title):
                  # Found pinned role assignment message, restore the view
                view = RoleAssignmentView()
                try:
                    await message.edit(view=view)
                    # Save the message ID for welcome system
                    save_role_assignment_message_id(message.id)
                    logger.info(f"Updated existing pinned role assignment message {message.id}")
                    return
                except Exception as e:
                    logger.error("Error updating pinned role assignment message: %s", e)
                    # If update fails, unpin and delete old message, create new one
                    try:
                        await message.unpin()
                        await message.delete()
                        logger.info(f"Removed old pinned role assignment message {message.id}")
                    except:
                        pass
                    break
    except Exception as e:
        logger.error("Error checking pinned messages for role assignment: %s", e)
    
    # Create new message if none exists or old one couldn't be updated
    embed = discord.Embed(
        title="🎖️ Получение ролей на сервере",
        description=(
            "Добро пожаловать! Для получения соответствующих ролей на сервере выберите подходящий вариант ниже.\n"
            "### 📋 Важная информация:\n"
            "> • **Одна заявка** - подавайте только одну заявку за раз\n"
            "> • **Достоверные данные** - указывайте только правдивую информацию\n"
            "> • **Доказательства** - приложите ссылки на подтверждающие документы (если требуется)\n"
            "> • **Терпение** - дождитесь рассмотрения (у нас есть 24 часа)\n\n"
            "## ⏰ Время рассмотрения: обычно до __24 часов__\n"
        ),
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🪖 Эта фракция", 
        value=(
            "> • Хотите поступить **именно** в **эту** фракцию\n"
        ), 
        inline=True
    )
    
    embed.add_field(
        name="📦 Доступ к поставкам", 
        value=(
            "> • Хотите сделать запрос поставки\n"
        ), 
        inline=True
    )
    
    embed.add_field(
        name="‍⚕️ Другая фракция", 
        value=(
            "> • Хотите получить роли другой гос. фракции\n"
        ),
        inline=True
    )
    
    embed.set_footer(
        text="Нажмите на соответствующую кнопку ниже для подачи заявки"
    )
    
    view = RoleAssignmentView()
    message = await channel.send(embed=embed, view=view)
    
    # Save the message ID for welcome system
    save_role_assignment_message_id(message.id)
    
    # Pin the new message for easy access
    try:
        await message.pin()
        logger.info(f"Pinned new role assignment message {message.id}")
    except Exception as e:
        logger.error("Error pinning role assignment message: %s", e)


async def restore_role_assignment_views(bot, channel):
    """Restore role assignment views for existing role assignment messages using pinned messages."""
    try:
        # Check pinned messages first
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == bot.user and 
                message.embeds and
                message.embeds[0].title and
                "Получение ролей" in message.embeds[0].title):
                  # Add the view back to the pinned message
                view = RoleAssignmentView()
                try:
                    await message.edit(view=view)
                    # Save the message ID for welcome system
                    save_role_assignment_message_id(message.id)
                    logger.info(f"Restored role assignment view for pinned message {message.id}")
                    return  # Found and restored pinned message
                except discord.NotFound:
                    continue
                except Exception as e:
                    logger.error(f"Error restoring view for pinned message {message.id}: %s", e)
        
        # If no pinned message found, check recent history as fallback
        async for message in channel.history(limit=50):
            # Check if message is from bot and has role assignment embed
            if (message.author == bot.user and 
                message.embeds and
                message.embeds[0].title and
                "Получение ролей" in message.embeds[0].title):
                
                # Add the view back to the message
                view = RoleAssignmentView()
                try:
                    await message.edit(view=view)
                    logger.info(f"Restored role assignment view for message {message.id}")
                except discord.NotFound:
                    continue
                except Exception as e:
                    logger.error(f"Error restoring view for message {message.id}: %s", e)
                    
    except Exception as e:
        logger.error("Error restoring role assignment views: %s", e)


async def restore_approval_views(bot, channel):
    """Restore approval views for existing application messages."""
    try:
        async for message in channel.history(limit=100):
            # Check if message is from bot and has application embed
            if (message.author == bot.user and 
                message.embeds and
                len(message.embeds) > 0):
                
                embed = message.embeds[0]
                if not embed.title:
                    continue
                    
                # Only restore views for PENDING applications (no status field)
                if ("Заявка на получение роли" in embed.title and 
                    not any(field.name in ["✅ Статус", "❌ Статус"] for field in embed.fields)):
                    
                    # Extract application data from embed
                    try:
                        application_data = {}
                        
                        # Determine type from title
                        if "военнослужащего" in embed.title:
                            application_data["type"] = "military"
                        elif "гражданского" in embed.title or "госслужащего" in embed.title:
                            application_data["type"] = "civilian"
                        else:
                            continue
                          # Extract all required fields from embed
                        for field in embed.fields:
                            if field.name == "👤 Заявитель":
                                user_mention = field.value
                                # Extract user ID from mention format <@!123456789> or <@123456789>
                                match = re.search(r'<@!?(\d+)>', user_mention)
                                if match:
                                    application_data["user_id"] = int(match.group(1))
                                    application_data["user_mention"] = user_mention
                            elif field.name == "📝 Имя Фамилия":
                                application_data["name"] = field.value
                            elif field.name == "🏛️ Фракция, звание, должность":
                                application_data["static"] = field.value
                            elif field.name == "🎯 Цель получения роли":
                                application_data["rank"] = field.value
                            elif field.name == "🏛️ Фракция, звание, должность":
                                application_data["faction"] = field.value
                            elif field.name == "🎯 Цель получения роли":
                                application_data["purpose"] = field.value
                            elif field.name == "🔢 Статик":
                                # Extract URL from markdown link [Ссылка](url)
                                url_match = re.search(r'\[.*?\]\((.*?)\)', field.value)
                                if url_match:
                                    application_data["proof"] = url_match.group(1)
                                else:
                                    application_data["proof"] = field.value
                        
                        # Verify we have minimum required data
                        if "user_id" in application_data and "name" in application_data and "type" in application_data:
                            # Create and add the approval view using factory function
                            view = create_approval_view(application_data)
                            await message.edit(view=view)
                            logger.info(f"Restored approval view for {application_data['type']} application message {message.id}")
                        else:
                            logger.debug("Недостаточно данных для сообщения %s: %s", message.id, application_data)
                        
                    except Exception as e:
                        logger.error("Ошибка разбора данных заявки из сообщения %s: %s", message.id, e)
                        continue
                        
                # For already processed applications, just skip them (don't restore views)
                elif ("Заявка на получение роли" in embed.title and 
                      any(field.name in ["✅ Статус", "❌ Статус"] for field in embed.fields)):
                    continue
                    
    except Exception as e:
        logger.error("Error restoring approval views: %s", e)