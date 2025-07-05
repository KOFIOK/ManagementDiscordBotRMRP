"""
Department Application Views - Persistent views for department applications
"""
import discord
from discord import ui
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timezone, timedelta

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
            # Check permissions with enhanced hierarchy
            if not await self._check_moderator_permissions(interaction):
                error_message = "❌ **Недостаточно прав для модерации**\n"
                
                # Check if user has any moderator/admin rights at all
                config = load_config()
                administrators = config.get('administrators', {})
                moderators = config.get('moderators', {})
                user_role_ids = [role.id for role in interaction.user.roles]
                
                is_admin = (
                    interaction.user.id in administrators.get('users', []) or
                    any(role_id in user_role_ids for role_id in administrators.get('roles', []))
                )
                
                is_moderator = (
                    interaction.user.id in moderators.get('users', []) or
                    any(role_id in user_role_ids for role_id in moderators.get('roles', []))
                )
                
                if not (is_admin or is_moderator):
                    error_message += "У вас нет прав модератора или администратора."
                elif is_moderator and interaction.user.id == self.application_data['user_id']:
                    error_message += "Модераторы не могут модерировать собственные заявления.\n(Администраторы могут модерировать любые заявления)"
                elif is_moderator:
                    error_message += "Модераторы не могут модерировать заявления других модераторов/администраторов."
                else:
                    error_message += "Произошла ошибка проверки прав доступа."
                
                await interaction.response.send_message(error_message, ephemeral=True)
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
                    value=f"<t:{int((datetime.now(timezone(timedelta(hours=3)))).timestamp())}:R>",
                    inline=True
                )
                
                # Disable all buttons and replace with single status button
                self.clear_items()
                
                # Add single disabled "Approved" button
                approved_button = ui.Button(
                    label="✅ Одобрено",
                    style=discord.ButtonStyle.green,
                    disabled=True
                )
                self.add_item(approved_button)
                
                await interaction.edit_original_response(embed=embed, view=self)
                
                # Send success message
                await interaction.followup.send(
                    f"✅ Заявление пользователя {target_user.mention} одобрено! Роли подразделения и должности назначены автоматически.",
                    ephemeral=True
                )
                
                # Send DM to user
                try:
                    dm_embed = discord.Embed(
                        title="✅ Заявление одобрено!",
                        description=f"Ваше заявление в подразделение **{self.application_data['department_code']}** было одобрено!",
                        color=discord.Color.green(),
                        timestamp=datetime.now(timezone(timedelta(hours=3)))
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
            # Check permissions with enhanced hierarchy
            if not await self._check_moderator_permissions(interaction):
                error_message = "❌ **Недостаточно прав для модерации**\n"
                
                # Check if user has any moderator/admin rights at all
                config = load_config()
                administrators = config.get('administrators', {})
                moderators = config.get('moderators', {})
                user_role_ids = [role.id for role in interaction.user.roles]
                
                is_admin = (
                    interaction.user.id in administrators.get('users', []) or
                    any(role_id in user_role_ids for role_id in administrators.get('roles', []))
                )
                
                is_moderator = (
                    interaction.user.id in moderators.get('users', []) or
                    any(role_id in user_role_ids for role_id in moderators.get('roles', []))
                )
                
                if not (is_admin or is_moderator):
                    error_message += "У вас нет прав модератора или администратора."
                elif is_moderator and interaction.user.id == self.application_data['user_id']:
                    error_message += "Модераторы не могут модерировать собственные заявления.\n(Администраторы могут модерировать любые заявления)"
                elif is_moderator:
                    error_message += "Модераторы не могут модерировать заявления других модераторов/администраторов."
                else:
                    error_message += "Произошла ошибка проверки прав доступа."
                
                await interaction.response.send_message(error_message, ephemeral=True)
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
        """
        Check if user has moderator permissions with proper hierarchy
        - Admin can moderate ANYTHING (including their own applications)
        - Moderator cannot moderate their own applications
        - Moderator cannot moderate applications from equal/higher hierarchy members
        """
        user_id = interaction.user.id
        application_user_id = self.application_data['user_id']
        
        config = load_config()
        administrators = config.get('administrators', {})
        moderators = config.get('moderators', {})
        user_role_ids = [role.id for role in interaction.user.roles]
        
        # Check if user is administrator FIRST (can moderate anything including own applications)
        is_admin = (
            user_id in administrators.get('users', []) or
            any(role_id in user_role_ids for role_id in administrators.get('roles', []))
        )
        
        if is_admin:
            return True  # Admins can moderate everything
        
        # Check if user is moderator
        is_moderator = (
            user_id in moderators.get('users', []) or
            any(role_id in user_role_ids for role_id in moderators.get('roles', []))
        )
        
        if not is_moderator:
            return False  # Not admin, not moderator
        
        # Moderators have restrictions:
        # 1. Cannot moderate own application
        if user_id == application_user_id:
            return False
        
        # 2. Moderator hierarchy check: cannot moderate other moderators/admins
        application_user = interaction.guild.get_member(application_user_id)
        if application_user:
            app_user_role_ids = [role.id for role in application_user.roles]
            
            # Check if application author is admin
            app_user_is_admin = (
                application_user_id in administrators.get('users', []) or
                any(role_id in app_user_role_ids for role_id in administrators.get('roles', []))
            )
            
            if app_user_is_admin:
                return False  # Moderator cannot moderate admin applications
            
            # Check if application author is also moderator
            app_user_is_moderator = (
                application_user_id in moderators.get('users', []) or
                any(role_id in app_user_role_ids for role_id in moderators.get('roles', []))
            )
            
            if app_user_is_moderator:
                return False  # Moderator cannot moderate other moderator applications
        
        return True  # Moderator can moderate regular user applications
    
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
        """Process application approval - assign roles and update nickname"""
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
            
            # Step 1: Remove ALL department roles (regardless of transfer/join)
            await self._remove_all_department_roles(target_user)
            
            # Step 2: Remove ALL position roles (regardless of transfer/join)
            await self._remove_all_position_roles(target_user)
            
            # Step 3: Assign new department role
            await target_user.add_roles(dept_role, reason=f"Approved department application by {interaction.user}")
            
            # Step 4: Assign assignable position roles for this department
            await self._assign_department_position_roles(target_user, dept_code, interaction.user)
            
            # Step 5: Update nickname with department abbreviation
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
    
    async def _remove_all_department_roles(self, user: discord.Member):
        """Remove ALL department roles from user"""
        all_dept_role_ids = ping_manager.get_all_department_role_ids()
        
        for role_id in all_dept_role_ids:
            role = user.guild.get_role(role_id)
            if role and role in user.roles:
                try:
                    await user.remove_roles(role, reason="Department application approval - cleaning roles")
                except discord.Forbidden:
                    logger.warning(f"Could not remove department role {role.name} from {user} - insufficient permissions")
                except Exception as e:
                    logger.error(f"Error removing department role {role.name} from {user}: {e}")
    
    async def _remove_all_position_roles(self, user: discord.Member):
        """Remove ALL position roles from user"""
        all_position_role_ids = ping_manager.get_all_position_role_ids()
        
        for role_id in all_position_role_ids:
            role = user.guild.get_role(role_id)
            if role and role in user.roles:
                try:
                    await user.remove_roles(role, reason="Department application approval - cleaning position roles")
                except discord.Forbidden:
                    logger.warning(f"Could not remove position role {role.name} from {user} - insufficient permissions")
                except Exception as e:
                    logger.error(f"Error removing position role {role.name} from {user}: {e}")
    
    async def _assign_department_position_roles(self, user: discord.Member, dept_code: str, moderator: discord.Member):
        """Assign assignable position roles for the department"""
        assignable_role_ids = ping_manager.get_department_assignable_position_roles(dept_code)
        
        assigned_roles = []
        failed_roles = []
        
        for role_id in assignable_role_ids:
            role = user.guild.get_role(role_id)
            if role:
                try:
                    await user.add_roles(role, reason=f"Department application approved - automatic position assignment by {moderator}")
                    assigned_roles.append(role.name)
                except discord.Forbidden:
                    logger.warning(f"Could not assign position role {role.name} to {user} - insufficient permissions")
                    failed_roles.append(role.name)
                except Exception as e:
                    logger.error(f"Error assigning position role {role.name} to {user}: {e}")
                    failed_roles.append(role.name)
        
        # Log results
        if assigned_roles:
            logger.info(f"Assigned position roles to {user}: {', '.join(assigned_roles)}")
        if failed_roles:
            logger.warning(f"Failed to assign position roles to {user}: {', '.join(failed_roles)}")
    
    async def _remove_old_department_roles(self, user: discord.Member, new_dept_code: str):
        """Legacy method - now calls the new comprehensive role removal"""
        await self._remove_all_department_roles(user)
    
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
                value=f"<t:{int((datetime.now(timezone(timedelta(hours=3)))).timestamp())}:R>",
                inline=True
            )
            
            # Clear all buttons and add single disabled "Rejected" button
            view = DepartmentApplicationView(self.application_data)
            view.clear_items()
            
            rejected_button = ui.Button(
                label="❌ Отклонено",
                style=discord.ButtonStyle.red,
                disabled=True
            )
            view.add_item(rejected_button)
            
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
                        timestamp=datetime.now(timezone(timedelta(hours=3)))
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
    """Button view for choosing department application type"""
    
    def __init__(self, department_code: str):
        super().__init__(timeout=None)  # Persistent view
        self.department_code = department_code
        
        # Set custom_id for persistence
        self.add_item(DepartmentApplicationButton("Заявление в подразделение", "join", department_code))
        self.add_item(DepartmentApplicationButton("Перевод из другого подразделения", "transfer", department_code))


class DepartmentApplicationButton(ui.Button):
    """Button for department application type selection"""
    
    def __init__(self, label: str, app_type: str, department_code: str):
        self.app_type = app_type
        self.department_code = department_code
        
        style = discord.ButtonStyle.green if app_type == "join" else discord.ButtonStyle.blurple
        emoji = "➕" if app_type == "join" else "🔄"
        
        super().__init__(
            label=label,
            style=style,
            emoji=emoji,
            custom_id=f"dept_app_{app_type}_{department_code}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle department application type selection"""
        try:
            # Check if user already has active applications
            active_check = await check_user_active_applications(
                interaction.guild, 
                interaction.user.id
            )
            
            if active_check['has_active']:
                departments_list = ", ".join(active_check['departments'])
                await interaction.response.send_message(
                    f"❌ **У вас уже есть активное заявление на рассмотрении**\n\n"
                    f"📋 Подразделения: **{departments_list}**\n"
                    f"⏳ Дождитесь рассмотрения текущего заявления перед подачей нового.\n\n"
                    f"💡 Активные заявления можно найти в каналах заявлений соответствующих подразделений.",
                    ephemeral=True
                )
                return
            
            # Get user IC data
            from utils.user_database import UserDatabase
            user_data = await UserDatabase.get_user_info(interaction.user.id)
            if not user_data:
                await interaction.response.send_message(
                    "❌ Ваши данные не найдены в системе. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create and send Stage 1 modal (IC Information)
            from .modals import DepartmentApplicationStage1Modal
            modal = DepartmentApplicationStage1Modal(self.department_code, self.app_type, user_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in department application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                ephemeral=True
            )

async def check_user_active_applications(guild: discord.Guild, user_id: int, department_code: str = None) -> Dict:
    """
    Check if user has any active (pending) applications
    
    Args:
        guild: Discord guild to search in
        user_id: User ID to check applications for
        department_code: Optional - check for specific department only
        
    Returns:
        dict: {
            'has_active': bool,
            'applications': [list of active application messages],
            'departments': [list of department codes with active applications]
        }
    """
    result = {
        'has_active': False,
        'applications': [],
        'departments': []
    }
    
    try:
        config = load_config()
        departments = config.get('departments', {})
        
        # Check each department or specific department
        depts_to_check = [department_code] if department_code else departments.keys()
        
        for dept_code in depts_to_check:
            dept_config = departments.get(dept_code, {})
            channel_id = dept_config.get('application_channel_id')
            
            if not channel_id:
                continue
                
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            
            # Check recent messages for user's applications
            async for message in channel.history(limit=100):
                if not message.embeds:
                    continue
                    
                embed = message.embeds[0]
                
                # Check if this is a department application
                if not embed.footer or not embed.footer.text:
                    continue
                    
                if f"ID заявления: {user_id}" in embed.footer.text:
                    # Check if application is still pending (has view with enabled buttons)
                    if message.components:
                        # Check if buttons are not disabled
                        for action_row in message.components:
                            for component in action_row.children:
                                if hasattr(component, 'disabled') and not component.disabled:
                                    # Found active application
                                    result['has_active'] = True
                                    result['applications'].append(message)
                                    if dept_code not in result['departments']:
                                        result['departments'].append(dept_code)
                                    break
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking user active applications: {e}")
        return result
