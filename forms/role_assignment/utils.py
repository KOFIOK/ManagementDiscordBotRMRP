"""
Utility functions for role assignment system
"""

import discord
import re
from .views import RoleAssignmentView
from .base import create_approval_view


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
                    print(f"Updated existing pinned role assignment message {message.id}")
                    return
                except Exception as e:
                    print(f"Error updating pinned role assignment message: {e}")
                    # If update fails, unpin and delete old message, create new one
                    try:
                        await message.unpin()
                        await message.delete()
                        print(f"Removed old pinned role assignment message {message.id}")
                    except:
                        pass
                    break
    except Exception as e:
        print(f"Error checking pinned messages for role assignment: {e}")
    
    # Create new message if none exists or old one couldn't be updated
    embed = discord.Embed(
        title="🎖️ Получение ролей",
        description=(
            "Выберите ваш тип заявки для получения соответствующих ролей на сервере.\\n\\n"
            "# ⚠️ ВАЖНО:\\nЕсли вы прошли призыв или экскурсию, нажимайте кнопку `\\\"Призыв / Экскурсия\\\"`!"
        ),
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🪖 Призыв / Экскурсия", 
        value="Выберите эту опцию, если:\\n• Вы прошли набор/призыв\\n• Участвуете в экскурсии\\n• Являетесь действующим военнослужащим ВС РФ", 
        inline=True
    )
    
    embed.add_field(
        name="👤 Я госслужащий", 
        value="Выберите эту опцию, если:\\n• Вы работник другого госоргана\\n• Вы поставщик\\n• Вы представитель организации", 
        inline=True
    )
    
    embed.add_field(
        name="ℹ️ Инструкция", 
        value="1. Нажмите на соответствующую кнопку\\n2. Заполните форму\\n3. При необходимости можете изменить выбор, нажав другую кнопку", 
        inline=False
    )
    
    view = RoleAssignmentView()
    message = await channel.send(embed=embed, view=view)
    
    # Pin the new message for easy access
    try:
        await message.pin()
        print(f"Pinned new role assignment message {message.id}")
    except Exception as e:
        print(f"Error pinning role assignment message: {e}")


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
                    print(f"Restored role assignment view for pinned message {message.id}")
                    return  # Found and restored pinned message
                except discord.NotFound:
                    continue
                except Exception as e:
                    print(f"Error restoring view for pinned message {message.id}: {e}")
        
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
                    print(f"Restored role assignment view for message {message.id}")
                except discord.NotFound:
                    continue
                except Exception as e:
                    print(f"Error restoring view for message {message.id}: {e}")
                    
    except Exception as e:
        print(f"Error restoring role assignment views: {e}")


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
                            elif field.name == "🔢 Статик":
                                application_data["static"] = field.value
                            elif field.name == "🎖️ Звание":
                                application_data["rank"] = field.value
                            elif field.name == "📋 Порядок набора":
                                application_data["recruitment_type"] = field.value.lower()
                            elif field.name == "🏛️ Фракция, звание, должность":
                                application_data["faction"] = field.value
                            elif field.name == "🎯 Цель получения роли":
                                application_data["purpose"] = field.value
                            elif field.name == "🔗 Доказательства":
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
                            print(f"Restored approval view for {application_data['type']} application message {message.id}")
                        else:
                            print(f"Missing required data for application message {message.id}: {application_data}")
                        
                    except Exception as e:
                        print(f"Error parsing application data from message {message.id}: {e}")
                        continue
                        
                # For already processed applications, just skip them (don't restore views)
                elif ("Заявка на получение роли" in embed.title and 
                      any(field.name in ["✅ Статус", "❌ Статус"] for field in embed.fields)):
                    continue
                    
    except Exception as e:
        print(f"Error restoring approval views: {e}")
