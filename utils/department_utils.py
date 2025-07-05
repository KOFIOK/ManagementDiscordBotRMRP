"""
Утилиты для системы заявлений в подразделения - создание закрепленных сообщений и восстановление views
"""

import discord
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

async def restore_department_applications_messages(bot):
    """Восстановить сообщения заявлений в подразделения для всех настроенных каналов"""
    try:
        from utils.config_manager import load_config
        from forms.department_applications.manager import DepartmentApplicationManager
        
        config = load_config()
        departments = config.get('departments', {})
        
        if not departments:
            logger.info("No departments configured for applications - skipping restoration")
            print("ℹ️ No departments configured for applications in config.json - skipping")
            print("ℹ️ To configure departments, use /settings -> Channels -> Departments")
            return True
        
        manager = DepartmentApplicationManager(bot)
        restored_count = 0
        created_count = 0
        
        for dept_code, dept_config in departments.items():
            channel_id = dept_config.get('application_channel_id')
            if not channel_id:
                continue
            
            channel = bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} for {dept_code} not found")
                continue
            
            print(f"🔄 Processing department {dept_code} in channel {channel.name}")
            
            # Сначала пытаемся восстановить существующее закрепленное сообщение
            pinned_restored = await restore_department_pinned_message(channel, dept_code, manager, bot)
            
            if pinned_restored:
                restored_count += 1
                print(f"✅ Restored existing pinned message for {dept_code}")
            else:
                # Если нет закреплённого, проверяем есть ли любое сообщение
                message_exists = await check_department_message_exists(channel, dept_code)
                if message_exists:
                    print(f"ℹ️ Message already exists for {dept_code} (but not pinned)")
                    # Пытаемся найти и закрепить существующее сообщение
                    pinned_existing = await try_pin_existing_message(channel, dept_code, manager, bot)
                    if pinned_existing:
                        restored_count += 1
                        print(f"✅ Restored and pinned existing message for {dept_code}")
                    else:
                        print(f"⚠️ Found message for {dept_code} but could not restore view")
                else:
                    print(f"📝 Creating new message for {dept_code} in {channel.name}")
                    try:
                        success = await manager.setup_department_channel(dept_code, channel)
                        if success:
                            created_count += 1
                            print(f"✅ Created new message for {dept_code}")
                        else:
                            print(f"❌ Failed to create message for {dept_code}")
                    except Exception as e:
                        print(f"❌ Error creating message for {dept_code}: {e}")
        
        print(f"Department applications: restored {restored_count}, created {created_count} messages")
        return True
        
    except Exception as e:
        logger.error(f"Error restoring department applications messages: {e}")
        return False

async def restore_department_pinned_message(channel: discord.TextChannel, dept_code: str, manager, bot) -> bool:
    """Восстановить закрепленное сообщение для конкретного подразделения"""
    try:
        from forms.department_applications.views import DepartmentSelectView
        from utils.config_manager import load_config
        
        config = load_config()
        dept_config = config.get('departments', {}).get(dept_code, {})
        persistent_message_id = dept_config.get('persistent_message_id')
        
        # Сначала проверяем по ID из конфигурации
        if persistent_message_id:
            try:
                message = await channel.fetch_message(persistent_message_id)
                if message and message.author == channel.guild.me:
                    # Восстанавливаем view для найденного сообщения
                    view = DepartmentSelectView(dept_code)
                    await message.edit(view=view)
                    
                    # Регистрируем view в боте для persistence
                    bot.add_view(view, message_id=message.id)
                    
                    # Закрепляем сообщение, если оно не закреплено
                    if not message.pinned:
                        try:
                            await message.pin()
                            print(f"📌 Pinned message for {dept_code} (ID: {message.id})")
                        except Exception as pin_error:
                            print(f"⚠️ Could not pin message for {dept_code}: {pin_error}")
                    
                    logger.info(f"✅ Restored view for {dept_code} by persistent_message_id (ID: {message.id})")
                    print(f"✅ Restored view for {dept_code} from config (ID: {message.id})")
                    return True
            except discord.NotFound:
                print(f"⚠️ Message ID {persistent_message_id} for {dept_code} not found, clearing from config")
                # Очищаем неактуальный ID из конфигурации
                dept_config.pop('persistent_message_id', None)
                await manager._save_department_config(dept_code, dept_config)
            except Exception as e:
                print(f"⚠️ Error fetching message {persistent_message_id} for {dept_code}: {e}")
        
        # Если не нашли по ID, ищем среди закрепленных сообщений
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and 
                len(message.embeds) > 0 and
                message.embeds[0].title and
                dept_code in message.embeds[0].title and
                "заявление" in message.embeds[0].title.lower()):
                
                # Восстанавливаем view для закрепленного сообщения
                view = DepartmentSelectView(dept_code)
                await message.edit(view=view)
                
                # Регистрируем view в боте для persistence
                bot.add_view(view, message_id=message.id)
                
                logger.info(f"✅ Restored view for {dept_code} pinned message (ID: {message.id})")
                print(f"✅ Restored view for {dept_code} from pinned messages (ID: {message.id})")
                
                # Обновляем конфигурацию с message_id
                await manager._save_department_message_info(dept_code, channel.id, message.id)
                
                return True
        
        # Закрепленное сообщение не найдено
        logger.info(f"⚠️ No pinned message found for {dept_code}")
        return False
        
    except Exception as e:
        logger.error(f"Error restoring pinned message for {dept_code}: {e}")
        return False

async def check_department_message_exists(channel: discord.TextChannel, dept_code: str) -> bool:
    """Проверить, есть ли уже сообщение для подразделения в канале"""
    try:
        from utils.config_manager import load_config
        
        config = load_config()
        dept_config = config.get('departments', {}).get(dept_code, {})
        persistent_message_id = dept_config.get('persistent_message_id')
        
        # Сначала проверяем по ID из конфигурации
        if persistent_message_id:
            try:
                message = await channel.fetch_message(persistent_message_id)
                if message and message.author == channel.guild.me:
                    logger.info(f"Found existing message for {dept_code} by ID (ID: {message.id}, pinned: {message.pinned})")
                    print(f"ℹ️ Found existing message for {dept_code} by ID: '{message.embeds[0].title if message.embeds else 'No title'}' (ID: {message.id})")
                    return True
            except discord.NotFound:
                print(f"⚠️ Message ID {persistent_message_id} for {dept_code} not found in channel, will clear from config")
                # Не очищаем здесь, только логируем - очистка будет в restore_department_pinned_message
            except Exception as e:
                print(f"⚠️ Error fetching message {persistent_message_id} for {dept_code}: {e}")
        
        # Если не нашли по ID, проверяем последние сообщения в канале
        async for message in channel.history(limit=50):  # Увеличил лимит
            if (message.author == channel.guild.me and 
                message.embeds and
                len(message.embeds) > 0 and
                message.embeds[0].title):
                
                title = message.embeds[0].title.lower()
                dept_code_lower = dept_code.lower()
                
                # Более широкий поиск - ищем код подразделения в заголовке
                if (dept_code_lower in title and 
                    ("заявление" in title or "подразделение" in title)):
                    logger.info(f"Found existing message for {dept_code} by search (ID: {message.id}, pinned: {message.pinned})")
                    print(f"ℹ️ Found existing message for {dept_code} by search: '{message.embeds[0].title}' (ID: {message.id})")
                    return True
        
        logger.info(f"No existing message found for {dept_code}")
        print(f"⚠️ No existing message found for {dept_code}")
        return False
    except Exception as e:
        logger.error(f"Error checking for department message in {channel.name}: {e}")
        return False

async def try_pin_existing_message(channel: discord.TextChannel, dept_code: str, manager, bot) -> bool:
    """Попытаться найти и закрепить существующее сообщение подразделения"""
    try:
        from forms.department_applications.views import DepartmentSelectView
        from utils.config_manager import load_config
        
        config = load_config()
        dept_config = config.get('departments', {}).get(dept_code, {})
        persistent_message_id = dept_config.get('persistent_message_id')
        
        # Сначала проверяем по ID из конфигурации
        if persistent_message_id:
            try:
                message = await channel.fetch_message(persistent_message_id)
                if message and message.author == channel.guild.me:
                    # Восстанавливаем view для найденного сообщения
                    view = DepartmentSelectView(dept_code)
                    await message.edit(view=view)
                    
                    # Регистрируем view в боте для persistence
                    bot.add_view(view, message_id=message.id)
                    
                    # Пытаемся закрепить сообщение, если оно не закреплено
                    if not message.pinned:
                        try:
                            await message.pin()
                            print(f"📌 Pinned existing message for {dept_code} (ID: {message.id})")
                            logger.info(f"✅ Pinned existing message for {dept_code} (ID: {message.id})")
                        except discord.Forbidden:
                            logger.warning(f"⚠️ Could not pin message for {dept_code} - insufficient permissions")
                        except discord.HTTPException as e:
                            logger.warning(f"⚠️ Could not pin message for {dept_code}: {e}")
                    
                    logger.info(f"✅ Restored and updated existing message for {dept_code} by ID (ID: {message.id})")
                    print(f"✅ Restored existing message for {dept_code} from config (ID: {message.id})")
                    return True
            except discord.NotFound:
                print(f"⚠️ Message ID {persistent_message_id} for {dept_code} not found, will search manually")
            except Exception as e:
                print(f"⚠️ Error fetching message {persistent_message_id} for {dept_code}: {e}")
        
        # Если не нашли по ID, ищем сообщение подразделения среди последних сообщений
        async for message in channel.history(limit=20):
            if (message.author == channel.guild.me and 
                message.embeds and
                len(message.embeds) > 0 and
                message.embeds[0].title and
                dept_code in message.embeds[0].title and
                "заявление" in message.embeds[0].title.lower()):
                
                # Восстанавливаем view для найденного сообщения
                view = DepartmentSelectView(dept_code)
                await message.edit(view=view)
                
                # Регистрируем view в боте для persistence
                bot.add_view(view, message_id=message.id)
                
                # Пытаемся закрепить сообщение, если оно не закреплено
                if not message.pinned:
                    try:
                        await message.pin()
                        logger.info(f"✅ Pinned existing message for {dept_code} (ID: {message.id})")
                        print(f"📌 Pinned existing message for {dept_code} (ID: {message.id})")
                    except discord.Forbidden:
                        logger.warning(f"⚠️ Could not pin message for {dept_code} - insufficient permissions")
                    except discord.HTTPException as e:
                        logger.warning(f"⚠️ Could not pin message for {dept_code}: {e}")
                
                # Обновляем конфигурацию с message_id
                await manager._save_department_message_info(dept_code, channel.id, message.id)
                
                logger.info(f"✅ Restored and updated existing message for {dept_code} by search (ID: {message.id})")
                print(f"✅ Restored existing message for {dept_code} by search (ID: {message.id})")
                return True
        
        logger.info(f"⚠️ No existing message found for {dept_code} to pin")
        return False
        
    except Exception as e:
        logger.error(f"Error trying to pin existing message for {dept_code}: {e}")
        return False
