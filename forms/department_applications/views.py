"""
Department Application Views - Persistent views for department applications
"""
import discord
from discord import ui
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from utils.config_manager import load_config
from utils.ping_manager import ping_manager

logger = logging.getLogger(__name__)

class DepartmentApplicationView(ui.View):
    """View with moderation buttons for department applications"""
    
    def __init__(self, application_data: Dict[str, Any]):
        super().__init__(timeout=None)  # Persistent view
        self.application_data = application_data
        
        # Set custom_id for persistence
        self.approve_button.custom_id = f"dept_app_approve_{application_data['user_id']}_{application_data['department_code']}"
        self.reject_button.custom_id = f"dept_app_reject_{application_data['user_id']}_{application_data['department_code']}"
        self.delete_button.custom_id = f"dept_app_delete_{application_data['user_id']}_{application_data['department_code']}"
    
    @ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, row=0)
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        """Approve the application"""
        try:
            # Check permissions
            if not await self._check_moderator_permissions(interaction):
                await interaction.response.send_message(
                    "❌ У вас нет прав для модерации заявлений.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # Get target user
            target_user = interaction.guild.get_member(self.application_data['user_id'])
            if not target_user:
                await interaction.followup.send(
                    "❌ Пользователь не найден на сервере.",
                    ephemeral=True
                )
                return
            
            # Check if user already has department role
            dept_role_id = ping_manager.get_department_role_id(self.application_data['department_code'])
            if dept_role_id:
                dept_role = interaction.guild.get_role(dept_role_id)
                if dept_role and dept_role in target_user.roles:
                    await interaction.followup.send(
                        f"❌ Пользователь уже состоит в подразделении {self.application_data['department_code']}.",
                        ephemeral=True
                    )
                    return
            
            # Process approval
            success = await self._process_approval(interaction, target_user)
            
            if success:
                # Update embed
                embed = interaction.message.embeds[0]
                embed.color = discord.Color.green()
                
                # Update status field
                for i, field in enumerate(embed.fields):
                    if field.name == "📊 Статус":
                        embed.set_field_at(
                            i,
                            name="📊 Статус",
                            value=f"✅ Одобрено {interaction.user.mention}",
                            inline=True
                        )
                        break
                
                embed.add_field(
                    name="⏰ Время обработки",
                    value=f"<t:{int(datetime.utcnow().timestamp())}:R>",
                    inline=True
                )
                
                # Disable buttons
                for item in self.children:
                    item.disabled = True
                
                await interaction.edit_original_response(embed=embed, view=self)
                
                # Send success message
                await interaction.followup.send(
                    f"✅ Заявление пользователя {target_user.mention} одобрено!",
                    ephemeral=True
                )
                
                # Send DM to user
                try:
                    dm_embed = discord.Embed(
                        title="✅ Заявление одобрено!",
                        description=f"Ваше заявление в подразделение **{self.application_data['department_code']}** было одобрено!",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    await target_user.send(embed=dm_embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send DM to {target_user} about approved application")
            
        except Exception as e:
            logger.error(f"Error approving department application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при одобрении заявления.",
                ephemeral=True
            )
    
    @ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, row=0)
    async def reject_button(self, interaction: discord.Interaction, button: ui.Button):
        """Reject the application with reason"""
        try:
            # Check permissions
            if not await self._check_moderator_permissions(interaction):
                await interaction.response.send_message(
                    "❌ У вас нет прав для модерации заявлений.",
                    ephemeral=True
                )
                return
            
            # Show rejection reason modal
            modal = RejectionReasonModal(self.application_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error rejecting department application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отклонении заявления.",
                ephemeral=True
            )
    
    @ui.button(label="🗑️ Удалить", style=discord.ButtonStyle.grey, row=0)  
    async def delete_button(self, interaction: discord.Interaction, button: ui.Button):
        """Delete the application (admin or author only)"""
        try:
            # Check if user is admin or application author
            is_admin = await self._check_admin_permissions(interaction)
            is_author = interaction.user.id == self.application_data['user_id']
            
            if not (is_admin or is_author):
                await interaction.response.send_message(
                    "❌ Только администратор или автор заявления может удалить его.",
                    ephemeral=True
                )
                return
            
            # Confirm deletion
            confirm_view = ConfirmDeletionView()
            await interaction.response.send_message(
                "⚠️ Вы уверены, что хотите удалить это заявление? Это действие нельзя отменить.",
                view=confirm_view,
                ephemeral=True
            )
            
            # Wait for confirmation
            await confirm_view.wait()
            
            if confirm_view.confirmed:
                await interaction.delete_original_response()
                await interaction.message.delete()
            else:
                await interaction.edit_original_response(
                    content="❌ Удаление отменено.",
                    view=None
                )
            
        except Exception as e:
            logger.error(f"Error deleting department application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при удалении заявления.",
                ephemeral=True
            )
    
    async def _check_moderator_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has moderator permissions"""
        config = load_config()
        moderators = config.get('moderators', {})
        
        # Check moderator users
        if interaction.user.id in moderators.get('users', []):
            return True
        
        # Check moderator roles
        user_role_ids = [role.id for role in interaction.user.roles]
        moderator_role_ids = moderators.get('roles', [])
        
        return any(role_id in user_role_ids for role_id in moderator_role_ids)
    
    async def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions"""
        config = load_config()
        administrators = config.get('administrators', {})
        
        # Check admin users
        if interaction.user.id in administrators.get('users', []):
            return True
        
        # Check admin roles
        user_role_ids = [role.id for role in interaction.user.roles]
        admin_role_ids = administrators.get('roles', [])
        
        return any(role_id in user_role_ids for role_id in admin_role_ids)
    
    async def _process_approval(self, interaction: discord.Interaction, target_user: discord.Member) -> bool:
        """Process application approval - assign role and update nickname"""
        try:
            dept_code = self.application_data['department_code']
            
            # Get department role
            dept_role_id = ping_manager.get_department_role_id(dept_code)
            if not dept_role_id:
                await interaction.followup.send(
                    f"❌ Роль для подразделения {dept_code} не настроена.",
                    ephemeral=True
                )
                return False
            
            dept_role = interaction.guild.get_role(dept_role_id)
            if not dept_role:
                await interaction.followup.send(
                    f"❌ Роль подразделения {dept_code} не найдена.",
                    ephemeral=True
                )
                return False
            
            # Handle transfer (remove old department role)
            if self.application_data['application_type'] == 'transfer':
                await self._remove_old_department_roles(target_user, dept_code)
            
            # Assign new department role
            await target_user.add_roles(dept_role, reason=f"Approved department application by {interaction.user}")
            
            # Update nickname with department abbreviation
            await self._update_user_nickname(target_user, dept_code)
            
            return True
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Боту не хватает прав для назначения роли или изменения никнейма.",
                ephemeral=True
            )
            return False
        except Exception as e:
            logger.error(f"Error processing application approval: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке заявления.",
                ephemeral=True
            )
            return False
    
    async def _remove_old_department_roles(self, user: discord.Member, new_dept_code: str):
        """Remove old department roles during transfer"""
        departments = ping_manager.get_all_departments()
        
        for dept_code, dept_config in departments.items():
            if dept_code != new_dept_code:
                role_id = dept_config.get('role_id')
                if role_id:
                    role = user.guild.get_role(role_id)
                    if role and role in user.roles:
                        await user.remove_roles(role, reason="Department transfer")
    
    async def _update_user_nickname(self, user: discord.Member, dept_code: str):
        """Update user nickname with department abbreviation"""
        try:
            current_nick = user.display_name
            
            # Remove existing department abbreviations dynamically
            departments = ping_manager.get_all_departments()
            for dept in departments.keys():
                current_nick = current_nick.replace(f"[{dept}]", "").replace(f" {dept}", "").strip()
            
            # Add new department abbreviation
            new_nick = f"[{dept_code}] {current_nick}"
            
            # Ensure nickname length is within Discord limits
            if len(new_nick) > 32:
                # Truncate the base name if needed
                base_name = current_nick[:32 - len(f"[{dept_code}] ")]
                new_nick = f"[{dept_code}] {base_name}"
            
            await user.edit(nick=new_nick, reason=f"Department application approved - {dept_code}")
            
        except discord.Forbidden:
            logger.warning(f"Could not update nickname for {user} - insufficient permissions")
        except Exception as e:
            logger.error(f"Error updating nickname for {user}: {e}")

class RejectionReasonModal(ui.Modal):
    """Modal for entering rejection reason"""
    
    def __init__(self, application_data: Dict[str, Any]):
        super().__init__(title="Причина отклонения", timeout=300)
        self.application_data = application_data
        
        self.reason = ui.TextInput(
            label="Причина отклонения",
            placeholder="Укажите причину отклонения заявления...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle rejection with reason"""
        try:
            await interaction.response.defer()
            
            # Get target user
            target_user = interaction.guild.get_member(self.application_data['user_id'])
            
            # Update embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            
            # Update status field
            for i, field in enumerate(embed.fields):
                if field.name == "📊 Статус":
                    embed.set_field_at(
                        i,
                        name="📊 Статус",
                        value=f"❌ Отклонено {interaction.user.mention}",
                        inline=True
                    )
                    break
            
            # Add rejection reason
            embed.add_field(
                name="📝 Причина отклонения",
                value=self.reason.value,
                inline=False
            )
            
            embed.add_field(
                name="⏰ Время обработки",
                value=f"<t:{int(datetime.utcnow().timestamp())}:R>",
                inline=True
            )
            
            # Disable buttons
            view = DepartmentApplicationView(self.application_data)
            for item in view.children:
                item.disabled = True
            
            await interaction.edit_original_response(embed=embed, view=view)
            
            # Send success message
            await interaction.followup.send(
                f"❌ Заявление пользователя {target_user.mention if target_user else 'неизвестного пользователя'} отклонено.",
                ephemeral=True
            )
            
            # Send DM to user if possible
            if target_user:
                try:
                    dm_embed = discord.Embed(
                        title="❌ Заявление отклонено",
                        description=f"Ваше заявление в подразделение **{self.application_data['department_code']}** было отклонено.",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    dm_embed.add_field(
                        name="📝 Причина",
                        value=self.reason.value,
                        inline=False
                    )
                    await target_user.send(embed=dm_embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send DM to {target_user} about rejected application")
            
        except Exception as e:
            logger.error(f"Error processing application rejection: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при отклонении заявления.",
                ephemeral=True
            )

class ConfirmDeletionView(ui.View):
    """Confirmation view for deletion"""
    
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = False
    
    @ui.button(label="✅ Да, удалить", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = True
        self.stop()
    
    @ui.button(label="❌ Отмена", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = False
        self.stop()

class DepartmentSelectView(ui.View):
    """Select menu for choosing department to apply to"""
    
    def __init__(self, department_code: str):
        super().__init__(timeout=None)  # Persistent view
        self.department_code = department_code
        
        # Set custom_id for persistence
        self.select_menu.custom_id = f"dept_select_{department_code}"
    
    @ui.select(
        placeholder="Выберите тип заявления...",
        options=[
            discord.SelectOption(
                label="Вступление в подразделение",
                description="Подать заявление на вступление в подразделение",
                value="join",
                emoji="➕"
            ),
            discord.SelectOption(
                label="Перевод в подразделение", 
                description="Подать заявление на перевод из другого подразделения",
                value="transfer",
                emoji="🔄"
            )
        ]
    )
    async def select_menu(self, interaction: discord.Interaction, select: ui.Select):
        """Handle department application type selection"""
        try:
            app_type = select.values[0]
            
            # Check if user already has an active application
            # This would need proper database implementation
            
            # Get user IC data
            from utils.user_database import UserDatabase
            user_data = await UserDatabase.get_user_info(interaction.user.id)
            if not user_data:
                await interaction.response.send_message(
                    "❌ Ваши данные не найдены в системе. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create and send application modal
            from .modals import DepartmentApplicationModal
            modal = DepartmentApplicationModal(self.department_code, app_type, user_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in department select: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                ephemeral=True
            )
