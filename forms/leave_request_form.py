"""
Leave request system main file
"""
import discord
from forms.leave_requests.views import LeaveRequestButton, LeaveRequestApprovalView
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


async def send_leave_request_button_message(channel: discord.TextChannel):
    """Send leave request button message, avoiding duplicates using pinned messages."""
    
    # Check pinned messages first for leave request message
    try:
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and
                message.embeds[0].title and
                "Система подачи заявок на отгулы" in message.embeds[0].title):
                
                # Found pinned leave request message, restore the view
                view = LeaveRequestButton()
                try:
                    await message.edit(view=view)
                    logger.info(f" Updated existing pinned leave request message {message.id}")
                    return message
                except Exception as e:
                    logger.warning("Error updating pinned leave request message: %s", e)
                    # If update fails, unpin and delete old message, create new one
                    try:
                        await message.unpin()
                        await message.delete()
                        logger.info(f" Removed old pinned leave request message {message.id}")
                    except:
                        pass
                    break
    except Exception as e:
        logger.warning("Error checking pinned messages for leave requests: %s", e)
        
    # Create new message if none exists or old one couldn't be updated
    try:
        embed = discord.Embed(
            title="🏖️ Система подачи заявок на отгулы",
            description=(
                "Здесь вы можете подать заявку на отгул в рабочее время.\n\n"
                "**⚠️ Важные ограничения:**\n"
                "• Максимальная длительность отгула: **1 час**\n"
                "• Можно подать только на **сегодняшний день**\n"
                "• Отгул разрешен только в **рабочее время**\n"
                "• Можно подать **только одну заявку в день**\n"
                "• Время должно быть **в будущем** относительно текущего момента\n\n"
                "**📝 Что нужно указать:**\n"
                "• Имя и фамилия\n"
                "• Статик (123-456)\n"
                "• Время начала и конца отгула (формат HH:MM)\n"
                "• Причина взятия отгула\n\n"
                "**🔍 Рассмотрение заявок:**\n"
                "• Заявки рассматривают командиры вашего подразделения\n"
                "• Уведомление о результате придет в личные сообщения\n"
                "• Вы можете удалить свою заявку до рассмотрения\n"
                "• При отклонении можно подать новую заявку в тот же день"
            ),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.set_footer(text="Нажмите кнопку ниже, чтобы подать заявку")
        
        view = LeaveRequestButton()
        message = await channel.send(embed=embed, view=view)
        
        # Pin the new message for easy access
        try:
            await message.pin()
            logger.info(f" Pinned new leave request message {message.id}")
        except Exception as e:
            logger.warning("Error pinning leave request message: %s", e)
        
        logger.info(f" Leave request button message sent to #{channel.name}")
        return message
        
    except Exception as e:
        logger.warning("Error sending leave request button message: %s", e)
        return None


async def restore_leave_request_views(bot):
    """Restore leave request views on bot startup"""
    try:
        logger.info("Restoring leave request views...")
        
        # First restore button view for pinned message
        from utils.config_manager import load_config
        config = load_config()
        channel_id = config.get('leave_requests_channel')
        
        if channel_id:
            channel = bot.get_channel(channel_id)
            if channel:
                # Check and update pinned message
                try:
                    pinned_messages = await channel.pins()
                    for message in pinned_messages:
                        if (message.author == channel.guild.me and 
                            message.embeds and
                            message.embeds[0].title and
                            "Система подачи заявок на отгулы" in message.embeds[0].title):
                            
                            # Found pinned leave request message, restore the view
                            view = LeaveRequestButton()
                            try:
                                await message.edit(view=view)
                                logger.info(f" Restored leave request button view for pinned message {message.id}")
                            except Exception as e:
                                logger.warning("Error restoring pinned message view: %s", e)
                            break
                except Exception as e:
                    logger.warning("Error checking pinned messages: %s", e)
                
                # Restore approval views for pending requests
                await restore_leave_request_approval_views(bot, channel)
        
        # Get all pending requests and add persistent views
        from utils.leave_request_storage import LeaveRequestStorage
        all_requests = LeaveRequestStorage.get_all_requests_today()
        pending_requests = [req for req in all_requests if req["status"] == "pending"]
        
        # Add views for pending requests
        for request in pending_requests:
            view = LeaveRequestApprovalView(request["id"])
            bot.add_view(view)
        
        logger.info(f"Leave request views restored: {len(pending_requests)} approval views")
        
    except Exception as e:
        logger.warning("Error restoring leave request views: %s", e)


async def restore_leave_request_approval_views(bot, channel):
    """Restore approval views for existing leave request messages."""
    try:
        approval_views_restored = 0
        
        async for message in channel.history(limit=100):
            # Check if message is from bot and has leave request embed
            if (message.author == bot.user and 
                message.embeds and
                message.embeds[0].title and
                "Заявка на отгул" in message.embeds[0].title):
                
                embed = message.embeds[0]
                
                # Check if request is still pending (not approved/rejected)
                status_pending = True
                for field in embed.fields:
                    if field.name in ["✅ Одобрено", "❌ Отклонено"]:
                        status_pending = False
                        break
                
                if status_pending:
                    # Extract request ID from embed if possible
                    request_id = None
                    for field in embed.fields:
                        if field.name == "🆔 ID заявки":
                            request_id = field.value
                            break
                    
                    if request_id:
                        # Restore the approval view
                        view = LeaveRequestApprovalView(request_id)
                        try:
                            await message.edit(view=view)
                            approval_views_restored += 1
                            logger.info("Restored approval view for leave request %s", request_id)
                        except discord.NotFound:
                            continue
                        except Exception as e:
                            logger.warning(f"Error restoring view for message {message.id}: %s", e)
        
        logger.info("Restoring %s leave request approval views...", approval_views_restored)
        
    except Exception as e:
        logger.warning("Error restoring leave request approval views: %s", e)


# Export main components
__all__ = [
    'send_leave_request_button_message',
    'restore_leave_request_views',
    'restore_leave_request_approval_views',
    'LeaveRequestButton',
    'LeaveRequestApprovalView'
]