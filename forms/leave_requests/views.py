"""
Views for leave request system
"""
import discord
from discord import ui
from utils.moderator_auth import is_moderator, is_administrator
from utils.leave_request_storage import LeaveRequestStorage


class LeaveRequestButton(ui.View):
    """Persistent button for submitting leave requests"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(
        label="🏖️ Подать заявку на отгул",
        style=discord.ButtonStyle.green,
        custom_id="leave_request_submit"
    )
    async def submit_request(self, interaction: discord.Interaction, button: ui.Button):
        # Check if user already has a request today
        from .utils import LeaveRequestValidator
        
        daily_check = LeaveRequestValidator.check_daily_limit(interaction.user.id)
        if not daily_check["can_request"]:
            embed = discord.Embed(
                title="❌ Заявка уже подана",
                description=daily_check["reason"],
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="Вы можете подать новую заявку завтра")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # If no existing request, show modal
        from .modals import LeaveRequestModal
        modal = LeaveRequestModal()
        await interaction.response.send_modal(modal)


class LeaveRequestApprovalView(ui.View):
    """View with approval/rejection buttons for leave requests"""
    
    def __init__(self, request_id: str):
        super().__init__(timeout=None)
        self.request_id = request_id    
    @ui.button(
        label="✅ Одобрить",
        style=discord.ButtonStyle.green,
        custom_id="leave_request_approve"
    )
    async def approve_request(self, interaction: discord.Interaction, button: ui.Button):
        try:
            # Check permissions
            is_admin = interaction.user.guild_permissions.administrator
            is_mod = await is_moderator(interaction.user.id)
            
            if not (is_admin or is_mod):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="У вас нет прав для рассмотрения заявок.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Get request
            request = LeaveRequestStorage.get_request_by_id(self.request_id)
            if not request:
                embed = discord.Embed(
                    title="❌ Заявка не найдена",
                    description="Заявка не существует или уже была обработана.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if request["status"] != "pending":
                embed = discord.Embed(
                    title="❌ Заявка уже обработана",
                    description="Эта заявка уже была рассмотрена.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check if trying to approve own request (moderators can't)
            if (request["user_id"] == interaction.user.id and 
                not interaction.user.guild_permissions.administrator):
                embed = discord.Embed(
                    title="❌ Нельзя рассматривать свою заявку",
                    description="Модераторы не могут рассматривать собственные заявки.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Update request status
            success = LeaveRequestStorage.update_request_status(
                self.request_id, "approved", interaction.user.id, str(interaction.user)
            )
            
            if success:
                # Update embed
                await self._update_request_embed(interaction)
                
                # Send DM to user
                await self._send_dm_notification(interaction, request)
                
                embed = discord.Embed(
                    title="✅ Заявка одобрена",
                    description=f"Заявка пользователя {request['name']} была одобрена.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Не удалось одобрить заявку.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Произошла ошибка",
                description=f"Ошибка при одобрении заявки: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @ui.button(
        label="❌ Отклонить",
        style=discord.ButtonStyle.red,
        custom_id="leave_request_reject"
    )
    async def reject_request(self, interaction: discord.Interaction, button: ui.Button):
        try:
            # Check permissions
            is_admin = interaction.user.guild_permissions.administrator
            is_mod = await is_moderator(interaction.user.id)
            
            if not (is_admin or is_mod):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="У вас нет прав для рассмотрения заявок.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Get request
            request = LeaveRequestStorage.get_request_by_id(self.request_id)
            if not request:
                embed = discord.Embed(
                    title="❌ Заявка не найдена",
                    description="Заявка не существует или уже была обработана.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if request["status"] != "pending":
                embed = discord.Embed(
                    title="❌ Заявка уже обработана",
                    description="Эта заявка уже была рассмотрена.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check if trying to reject own request (moderators can't)
            if (request["user_id"] == interaction.user.id and 
                not interaction.user.guild_permissions.administrator):
                embed = discord.Embed(
                    title="❌ Нельзя рассматривать свою заявку",
                    description="Модераторы не могут рассматривать собственные заявки.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Show rejection reason modal
            from .modals import RejectReasonModal
            modal = RejectReasonModal(self.request_id)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Произошла ошибка",
                description=f"Ошибка при отклонении заявки: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @ui.button(
        label="🗑️ Удалить",
        style=discord.ButtonStyle.secondary,
        custom_id="leave_request_delete"
    )
    async def delete_request(self, interaction: discord.Interaction, button: ui.Button):
        try:
            # Get request
            request = LeaveRequestStorage.get_request_by_id(self.request_id)
            if not request:
                embed = discord.Embed(
                    title="❌ Заявка не найдена",
                    description="Заявка не существует или уже была обработана.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check permissions
            is_admin = interaction.user.guild_permissions.administrator
            is_mod = await is_moderator(interaction.user.id)
            is_request_owner = request["user_id"] == interaction.user.id
            
            # Admin/mod can delete any request, user can only delete own pending requests
            if not (is_admin or is_mod or is_request_owner):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="Вы можете удалить только свою собственную заявку.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # User can only delete pending requests, admin/mod can delete any
            if is_request_owner and not (is_admin or is_mod) and request["status"] != "pending":
                status_text = {
                    "approved": "одобрена",
                    "rejected": "отклонена"
                }.get(request["status"], request["status"])
                
                embed = discord.Embed(
                    title="❌ Нельзя удалить заявку",
                    description=f"Заявка уже была рассмотрена ({status_text}). Удалить можно только заявки, ожидающие рассмотрения.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Delete request completely
            success = LeaveRequestStorage.delete_request(
                self.request_id, 
                interaction.user.id,
                is_admin=(is_admin or is_mod)
            )
            
            if success:
                # Delete the message completely
                await interaction.response.defer()
                await interaction.delete_original_response()
            else:
                embed = discord.Embed(
                    title="❌ Ошибка удаления",
                    description="Не удалось удалить заявку. Возможно, она уже была обработана.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Произошла ошибка",
                description=f"Ошибка при удалении заявки: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _update_request_embed(self, interaction):
        """Update the original request embed with approval info"""
        try:
            # Get updated request
            updated_request = LeaveRequestStorage.get_request_by_id(self.request_id)
            
            # Update embed
            embed = interaction.message.embeds[0]
            
            # Update status field
            for i, field in enumerate(embed.fields):
                if field.name == "📢 Статус:":
                    embed.set_field_at(
                        i, 
                        name="📢 Статус:",
                        value=f"✅ ОДОБРЕНА пользователем {interaction.user.mention}\n⏰ {discord.utils.format_dt(discord.utils.utcnow(), 'f')}",
                        inline=True
                    )
                    break
            
            embed.color = discord.Color.green()
            
            # Remove buttons
            await interaction.message.edit(embed=embed, view=None)
            
        except Exception as e:
            print(f"Error updating request embed: {e}")
    
    async def _send_dm_notification(self, interaction, request):
        """Send DM notification to user about approval"""
        try:
            user = interaction.guild.get_member(request["user_id"])
            if not user:
                return
            
            embed = discord.Embed(
                title="✅ Ваша заявка на отгул была одобрена",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="📋 Детали заявки:",
                value=(
                    f"**Время:** {request['start_time']} - {request['end_time']}\n"
                    f"**Дата:** {discord.utils.format_dt(discord.utils.utcnow(), 'd')}\n"
                    f"**Причина:** {request['reason']}"
                ),
                inline=False
            )
            
            embed.add_field(
                name="👤 Одобрил:",
                value=str(interaction.user),
                inline=True
            )
            
            embed.add_field(
                name="ℹ️ Важно:",
                value="Не забудьте уведомить о начале и окончании отгула в соответствии с регламентом.",
                inline=False
            )
            
            await user.send(embed=embed)
            
        except Exception as e:
            print(f"Error sending DM notification: {e}")
