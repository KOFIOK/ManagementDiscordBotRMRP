"""
Leave request system main file
"""
import discord
from forms.leave_requests.views import LeaveRequestButton, LeaveRequestApprovalView


async def send_leave_request_button_message(channel: discord.TextChannel):
    """Send leave request button message to channel"""
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
                "• Статик (будет автоматически отформатирован)\n"
                "• Время начала и конца отгула (формат HH:MM)\n"
                "• Причина взятия отгула\n\n"
                "**🔍 Рассмотрение заявок:**\n"
                "• Заявки рассматривают модераторы и администраторы\n"
                "• Уведомление о результате придет в личные сообщения\n"
                "• Вы можете удалить свою заявку до рассмотрения\n"
                "• При отклонении можно подать новую заявку в тот же день"
            ),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="ℹ️ Время работы системы:",
            value="Система доступна 24/7, но отгулы можно брать только в рабочее время по МСК",
            inline=False
        )
        
        embed.set_footer(text="Нажмите кнопку ниже, чтобы подать заявку")
        
        view = LeaveRequestButton()
        message = await channel.send(embed=embed, view=view)
        
        print(f"✅ Leave request button message sent to #{channel.name}")
        return message
        
    except Exception as e:
        print(f"❌ Error sending leave request button message: {e}")
        return None


async def restore_leave_request_views(bot):
    """Restore leave request views on bot startup"""
    try:
        from utils.leave_request_storage import LeaveRequestStorage
        
        # Get all pending requests
        all_requests = LeaveRequestStorage.get_all_requests_today()
        pending_requests = [req for req in all_requests if req["status"] == "pending"]
        
        print(f"🔄 Restoring {len(pending_requests)} leave request approval views...")
        
        # Add views for pending requests
        for request in pending_requests:
            view = LeaveRequestApprovalView(request["id"])
            bot.add_view(view)
        
        print(f"✅ Leave request views restored: {len(pending_requests)} approval views")
        
    except Exception as e:
        print(f"❌ Error restoring leave request views: {e}")


# Export main components
__all__ = [
    'send_leave_request_button_message',
    'restore_leave_request_views',
    'LeaveRequestButton',
    'LeaveRequestApprovalView'
]
