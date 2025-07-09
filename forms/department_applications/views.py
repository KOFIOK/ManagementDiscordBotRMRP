"""
Department Application Views - Persistent views for department applications
"""
import discord
from discord import ui
from typing import Dict, Any, List
import logging
from datetime import datetime, timezone, timedelta

from utils.config_manager import load_config
from utils.ping_manager import ping_manager
from utils.google_sheets import sheets_manager

logger = logging.getLogger(__name__)

class DepartmentApplicationView(ui.View):
    """View with moderation buttons for department applications"""
    
    def __init__(self, application_data: Dict[str, Any]):
        super().__init__(timeout=None)  # Persistent view
        self.application_data = application_data
        
        # Set STATIC custom_id for persistence (важно для восстановления после рестарта)
        self.approve_button.custom_id = "dept_app_approve_static"
        self.reject_button.custom_id = "dept_app_reject_static"
        self.delete_button.custom_id = "dept_app_delete_static"
    
    def _extract_application_data_from_embed(self, embed: discord.Embed) -> Dict[str, Any]:
        """Извлекает данные заявления из embed для статических views"""
        try:
            data = {
                'user_id': None,
                'department_code': None,
                'name': None,
                'static': None,
                'application_type': 'join'
            }
            
            # Извлекаем user_id из footer
            if embed.footer and embed.footer.text and "ID заявления:" in embed.footer.text:
                try:
                    data['user_id'] = int(embed.footer.text.split("ID заявления:")[-1].strip())
                except (ValueError, IndexError):
                    pass
            
            # Извлекаем department_code из description (новый формат)
            if embed.description:
                # Ищем в description после "в " и до " от"
                if " в " in embed.description and " от" in embed.description:
                    dept_part = embed.description.split(" в ")[-1].split(" от")[0]
                    # Убираем лишние слова
                    data['department_code'] = dept_part.strip()
                    
                # Определяем тип заявления
                if "перевод" in embed.description.lower():
                    data['application_type'] = 'transfer'
            # Fallback: извлекаем department_code из title (старый формат)
            elif embed.title:
                # Ищем в title после "в "
                if " в " in embed.title:
                    dept_part = embed.title.split(" в ")[-1]
                    # Убираем лишние слова
                    data['department_code'] = dept_part.strip()
                    
                # Определяем тип заявления
                if "перевод" in embed.title.lower():
                    data['application_type'] = 'transfer'
            
            # Извлекаем данные из полей
            for field in embed.fields:
                field_name = field.name.lower()
                field_value = field.value
                
                # Для отдельных полей (старый формат)
                if "имя фамилия" in field_name:
                    data['name'] = field_value
                elif "статик" in field_name:
                    data['static'] = field_value
                # Для нового формата, где данные внутри "📋 IC Информация"
                elif "ic информация" in field_name:
                    # Парсим строку вида:
                    # **Имя Фамилия:** Марко Толедо
                    # **Статик:** 135-583
                    # **Документ:** [Ссылка на документ](url)
                    lines = field_value.split('\n')
                    for line in lines:
                        if '**Имя Фамилия:**' in line:
                            data['name'] = line.split('**Имя Фамилия:**')[-1].strip()
                        elif '**Статик:**' in line:
                            data['static'] = line.split('**Статик:**')[-1].strip()
            
            return data
            
        except Exception as e:
            logger.error(f"Error extracting application data from embed: {e}")
            return self.application_data  # Fallback to original data
    
    @ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, row=0)
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        """Approve the application"""
        try:
            # Извлекаем актуальные данные из embed (для статических views)
            if interaction.message and interaction.message.embeds:
                self.application_data = self._extract_application_data_from_embed(interaction.message.embeds[0])
            
            # Check permissions - for approve, only first line roles can approve
            if not await self._check_approve_permissions(interaction):
                error_message = self._get_approve_permission_error_message(interaction)
                await interaction.response.send_message(error_message, ephemeral=True)
                return
            
            await interaction.response.defer()
            
            # Show "Processing..." state immediately to prevent double-clicks
            processing_embed = interaction.message.embeds[0].copy()
            
            # Update status field to show processing
            for i, field in enumerate(processing_embed.fields):
                if field.name == "📊 Статус":
                    processing_embed.set_field_at(
                        i,
                        name="📊 Статус", 
                        value="⏳ Обрабатывается...",
                        inline=True
                    )
                    break
            
            # Replace all buttons with single disabled "Processing" button
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(
                label="⏳ Обрабатывается...",
                style=discord.ButtonStyle.grey,
                disabled=True
            )
            processing_view.add_item(processing_button)
            
            # Update message with processing state
            await interaction.edit_original_response(content="", embed=processing_embed, view=processing_view)
            
            # Get target user
            target_user = interaction.guild.get_member(self.application_data['user_id'])
            if not target_user:
                # Restore original buttons on error
                await self._restore_original_buttons(interaction)
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
                    # Restore original buttons on error
                    await self._restore_original_buttons(interaction)
                    await interaction.followup.send(
                        f"❌ Пользователь уже состоит в подразделении {self.application_data['department_code']}.",
                        ephemeral=True
                    )
                    return
            
            # Process approval
            success = await self._process_approval(interaction, target_user)
            
            if success:
                # Clear user's cache since status changed
                _clear_user_cache(target_user.id)
                
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
                
                await interaction.edit_original_response(content="", embed=embed, view=self)
                
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
            else:
                # Restore original buttons if approval failed
                await self._restore_original_buttons(interaction)
            
        except Exception as e:
            logger.error(f"Error approving department application: {e}")
            # Restore original buttons on error
            await self._restore_original_buttons(interaction)
            await interaction.followup.send(
                "❌ Произошла ошибка при одобрении заявления.",
                ephemeral=True
            )
    
    @ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, row=0)
    async def reject_button(self, interaction: discord.Interaction, button: ui.Button):
        """Reject the application with reason"""
        try:
            # Извлекаем актуальные данные из embed (для статических views)
            if interaction.message and interaction.message.embeds:
                self.application_data = self._extract_application_data_from_embed(interaction.message.embeds[0])
            
            # Check permissions - for reject, any role from all lines can reject
            if not await self._check_reject_permissions(interaction):
                error_message = self._get_reject_permission_error_message(interaction)
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
            # Извлекаем актуальные данные из embed (для статических views)
            if interaction.message and interaction.message.embeds:
                self.application_data = self._extract_application_data_from_embed(interaction.message.embeds[0])
            
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
        - Higher hierarchy moderator can moderate lower hierarchy moderator applications
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
        is_moderator_by_user = user_id in moderators.get('users', [])
        moderator_roles = [role for role in interaction.user.roles if role.id in moderators.get('roles', [])]
        is_moderator_by_role = len(moderator_roles) > 0
        
        if not (is_moderator_by_user or is_moderator_by_role):
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
            app_is_moderator_by_user = application_user_id in moderators.get('users', [])
            app_moderator_roles = [role for role in application_user.roles if role.id in moderators.get('roles', [])]
            app_is_moderator_by_role = len(app_moderator_roles) > 0
            
            if not (app_is_moderator_by_user or app_is_moderator_by_role):
                return True  # Moderator can moderate regular user applications
            
            # Both are moderators - check hierarchy
            if is_moderator_by_role and app_is_moderator_by_role:
                # Find highest moderator role position for current user
                user_highest_mod_role_position = max(role.position for role in moderator_roles)
                
                # Find highest moderator role position for application author
                app_highest_mod_role_position = max(role.position for role in app_moderator_roles)
                
                # Higher role can moderate lower role
                return user_highest_mod_role_position > app_highest_mod_role_position
            
            # If one is moderator by user and other by role
            if is_moderator_by_user and app_is_moderator_by_role:
                return False  # User moderator cannot moderate role moderator
            
            if is_moderator_by_role and app_is_moderator_by_user:
                return True  # Role moderator can moderate user moderator
            
            # Both are user moderators - deny moderation
            if is_moderator_by_user and app_is_moderator_by_user:
                return False
        
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
    
    async def _restore_original_buttons(self, interaction: discord.Interaction):
        """Restore original buttons after error"""
        try:
            # Get the original embed (should already be set)
            original_embed = interaction.message.embeds[0].copy()
            
            # Restore original status if it was changed to "Processing"
            for i, field in enumerate(original_embed.fields):
                if field.name == "📊 Статус" and "Обрабатывается" in field.value:
                    original_embed.set_field_at(
                        i,
                        name="📊 Статус",
                        value="⏳ Ожидает рассмотрения",
                        inline=True
                    )
                    break
            
            # Create new view with original buttons
            restored_view = DepartmentApplicationView(self.application_data)
            
            # Update message back to original state
            await interaction.edit_original_response(content="", embed=original_embed, view=restored_view)
            
        except Exception as e:
            logger.error(f"Error restoring original buttons: {e}")
    
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
            
            # Step 6: Log to Google Sheets
            await self._log_to_google_sheets(interaction, target_user, dept_code)
            
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
        
        logger.info(f"Attempting to assign position roles for {dept_code} to {user.display_name}")
        logger.info(f"Assignable role IDs: {assignable_role_ids}")
        
        if not assignable_role_ids:
            logger.warning(f"No assignable position roles configured for department {dept_code}")
            return
        
        assigned_roles = []
        failed_roles = []
        
        for role_id in assignable_role_ids:
            role = user.guild.get_role(role_id)
            if not role:
                logger.error(f"Role with ID {role_id} not found on server for department {dept_code}")
                failed_roles.append(f"ID:{role_id}")
                continue
                
            logger.info(f"Attempting to assign role {role.name} (ID: {role_id}) to {user.display_name}")
            
            try:
                await user.add_roles(role, reason=f"Department application approved - automatic position assignment by {moderator}")
                assigned_roles.append(role.name)
                logger.info(f"Successfully assigned role {role.name} to {user.display_name}")
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
        
        logger.info(f"Position role assignment complete for {user.display_name}: {len(assigned_roles)} assigned, {len(failed_roles)} failed")
    
    async def _remove_old_department_roles(self, user: discord.Member, new_dept_code: str):
        """Legacy method - now calls the new comprehensive role removal"""
        await self._remove_all_department_roles(user)
    
    async def _update_user_nickname(self, user: discord.Member, dept_code: str):
        """Update user nickname with department abbreviation"""
        try:
            import re
            current_nick = user.display_name
            
            # Remove existing department abbreviations dynamically (improved cleaning)
            departments = ping_manager.get_all_departments()
            for dept in departments.keys():
                # First, handle complex patterns with regex - matches department at start with anything until |
                # This handles cases like "РОиО[1] |", "УВП|", "ССО| Опер|"
                pattern = rf"^{re.escape(dept)}[^\|]*\|"
                if re.match(pattern, current_nick):
                    current_nick = re.sub(pattern, "", current_nick).strip()
                    continue
                
                # Handle simple bracket format: [УВП]
                if current_nick.startswith(f"[{dept}]"):
                    current_nick = current_nick[len(f"[{dept}]"):].strip()
                    continue
                
                # Handle format with space: УВП |
                if current_nick.startswith(f"{dept} |"):
                    current_nick = current_nick[len(f"{dept} |"):].strip()
                    continue
                
                # Handle format without space: УВП|
                if current_nick.startswith(f"{dept}|"):
                    current_nick = current_nick[len(f"{dept}|"):].strip()
                    continue
                
                # Fallback: if starts with department name followed by space
                if current_nick.startswith(f"{dept} "):
                    current_nick = current_nick[len(f"{dept} "):].strip()
                    continue
            
            # Additional cleanup for complex cases with multiple departments/roles
            # Remove any remaining patterns like "| Опер|" or "| РОиО|" from the start
            while True:
                old_nick = current_nick
                # Remove any leading pipe and text until next pipe
                current_nick = re.sub(r"^\s*\|[^\|]*\|", "", current_nick).strip()
                # Remove any leading pipe and text if no closing pipe
                current_nick = re.sub(r"^\s*\|[^\|]*$", "", current_nick).strip()
                # Clean up any remaining orphaned pipes or brackets at the start
                current_nick = current_nick.lstrip("|[]() ").strip()
                
                # If no changes made, break the loop
                if current_nick == old_nick:
                    break
            
            # Try full format first: УВП | Имя Фамилия
            new_nick = f"{dept_code} | {current_nick}"
            
            # Check if nickname is within Discord limits (32 characters)
            if len(new_nick) <= 32:
                await user.edit(nick=new_nick, reason=f"Department application approved - {dept_code}")
                return
            
            # If too long, try abbreviated format: УВП | И. Фамилия
            name_parts = current_nick.split()
            if len(name_parts) >= 2:
                # Take first letter of first name + dot + last name
                first_name_initial = name_parts[0][0] + "."
                last_name = name_parts[-1]  # Take last part as surname
                abbreviated_name = f"{first_name_initial} {last_name}"
                
                new_nick = f"{dept_code} | {abbreviated_name}"
                
                if len(new_nick) <= 32:
                    await user.edit(nick=new_nick, reason=f"Department application approved - {dept_code}")
                    return
            
            # If still too long, truncate the base name
            max_base_length = 32 - len(f"{dept_code} | ")
            if max_base_length > 0:
                truncated_name = current_nick[:max_base_length]
                new_nick = f"{dept_code} | {truncated_name}"
                await user.edit(nick=new_nick, reason=f"Department application approved - {dept_code}")
            else:
                # If department code is too long, just use the code
                new_nick = dept_code[:32]
                await user.edit(nick=new_nick, reason=f"Department application approved - {dept_code}")
            
        except discord.Forbidden:
            logger.warning(f"Could not update nickname for {user} - insufficient permissions")
        except Exception as e:
            logger.error(f"Error updating nickname for {user}: {e}")
    
    async def _log_to_google_sheets(self, interaction: discord.Interaction, target_user: discord.Member, dept_code: str):
        """Log department application approval to Google Sheets"""
        try:
            # Initialize sheets manager if needed
            if not hasattr(sheets_manager, 'client') or not sheets_manager.client:
                await sheets_manager.async_initialize()
            
            # Determine action type
            application_type = self.application_data.get('application_type', 'join')
            action = "Принят в подразделение" if application_type == 'join' else "Переведён в подразделение"
            
            # Get department name from role name (not config)
            departments = ping_manager.get_all_departments()
            dept_config = departments.get(dept_code, {})
            
            # Get department role and use its name for table record
            dept_role_id = dept_config.get('role_id') or dept_config.get('key_role_id')
            if dept_role_id:
                dept_role = interaction.guild.get_role(dept_role_id)
                if dept_role:
                    department_name = dept_role.name
                else:
                    # Fallback if role not found
                    department_name = dept_config.get('name', dept_code)
                    logger.warning(f"Department role {dept_role_id} not found for {dept_code}, using config name")
            else:
                # Fallback if no role_id configured
                department_name = dept_config.get('name', dept_code)
                logger.warning(f"No role_id configured for department {dept_code}, using config name")
            
            # Get assigned position roles names (from user's actual roles, not config)
            assignable_role_ids = ping_manager.get_department_assignable_position_roles(dept_code)
            position_names = []
            user_role_ids = [role.id for role in target_user.roles]
            
            logger.info(f"Getting position roles for Google Sheets. Assignable IDs: {assignable_role_ids}")
            logger.info(f"User {target_user.display_name} has roles: {user_role_ids}")
            
            for role_id in assignable_role_ids:
                role = interaction.guild.get_role(role_id)
                if role and role.id in user_role_ids:
                    position_names.append(role.name)
                    logger.info(f"Added position role {role.name} to Google Sheets record")
                elif role:
                    logger.warning(f"User {target_user.display_name} doesn't have expected position role {role.name}")
                else:
                    logger.error(f"Position role ID {role_id} not found on server")
            
            position_roles_text = ", ".join(position_names) if position_names else ""
            logger.info(f"Final position roles text for Google Sheets: '{position_roles_text}'")
            
            # Get user rank from roles
            user_rank = sheets_manager.get_rank_from_roles(target_user) if hasattr(sheets_manager, 'get_rank_from_roles') else "Неизвестно"
            
            # Prepare form data for sheets logging (similar to dismissal system)
            form_data = {
                'name': self.application_data.get('name', target_user.display_name),
                'static': self.application_data.get('static', ''),
                'department': department_name,
                'rank': user_rank,
                'reason': '',  # Empty for applications as specified
                'action': action,
                'position': position_roles_text
            }
            
            # Log to "Общий Кадровый"
            success = await self._add_application_record_to_audit(
                form_data=form_data,
                target_user=target_user,
                approving_user=interaction.user,
                approval_time=datetime.now(timezone(timedelta(hours=3)))
            )
            
            if success:
                logger.info(f"Successfully logged department application to Google Sheets for {target_user.display_name}")
                
                # Update "Личный Состав"
                await self._update_personal_roster(target_user, department_name, position_roles_text)
                
                # Send audit notification after successful Google Sheets logging
                moderator_info = await self._get_moderator_info_from_users_sheet(interaction.user)
                audit_url = await self._send_audit_notification(interaction, target_user, form_data, moderator_info)
                if audit_url:
                    logger.info(f"Sent audit notification for {target_user.display_name}: {audit_url}")
                else:
                    logger.warning(f"Failed to send audit notification for {target_user.display_name}")
            else:
                logger.warning(f"Failed to log department application to Google Sheets for {target_user.display_name}")
                
        except Exception as e:
            logger.error(f"Error logging department application to Google Sheets: {e}")
    
    async def _send_audit_notification(self, interaction: discord.Interaction, target_user: discord.Member, form_data: dict, moderator_name: str) -> str:
        """Send audit notification to configured audit channel"""
        try:
            config = load_config()
            audit_channel_id = config.get('audit_channel')
            
            if not audit_channel_id:
                logger.warning("Audit channel ID not configured")
                return None
                
            audit_channel = interaction.guild.get_channel(audit_channel_id)
            if not audit_channel:
                logger.error(f"Audit channel not found: {audit_channel_id}")
                return None
            
            # Create audit notification embed (same format as dismissal system)
            audit_embed = discord.Embed(
                title="Кадровый аудит ВС РФ",
                color=0x055000,  # Green color as in template
                timestamp=discord.utils.utcnow()
            )
            
            # Format date as dd-MM-yyyy
            action_date = discord.utils.utcnow().strftime('%d-%m-%Y')
            
            # Combine name and static for "Имя Фамилия | 6 цифр статика" field
            name_with_static = f"{form_data.get('name', target_user.display_name)} | {form_data.get('static', '')}"
            
            # Set fields according to template
            audit_embed.add_field(name="Кадровую отписал", value=moderator_name, inline=False)
            audit_embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
            audit_embed.add_field(name="Действие", value=form_data.get('action', 'Принят на службу'), inline=False)
            
            # For applications, we don't usually have a reason field, but add it if exists
            reason = form_data.get('reason', '')
            if reason:
                audit_embed.add_field(name="Причина", value=reason, inline=False)
            
            audit_embed.add_field(name="Дата Действия", value=action_date, inline=False)
            audit_embed.add_field(name="Подразделение", value=form_data.get('department', 'Неизвестно'), inline=False)
            audit_embed.add_field(name="Воинское звание", value=form_data.get('rank', 'Неизвестно'), inline=False)
            
            # Add position field if available
            position = form_data.get('position', '')
            if position:
                audit_embed.add_field(name="Должность", value=position, inline=False)
            
            # Set thumbnail to default image as in template
            audit_embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
            
            # Send notification with user mention (the user who was approved)
            audit_message = await audit_channel.send(content=f"<@{target_user.id}>", embed=audit_embed)
            logger.info(f"Sent audit notification for department application approval of {target_user.display_name}")
            
            return audit_message.jump_url
            
        except Exception as e:
            logger.error(f"Error sending audit notification: {e}")
            return None
    
    async def _add_application_record_to_audit(self, form_data: dict, target_user: discord.Member, approving_user: discord.Member, approval_time: datetime) -> bool:
        """Add department application record to 'Общий Кадровый' sheet"""
        try:
            # Ensure connection
            if not sheets_manager._ensure_connection():
                logger.error("Failed to establish Google Sheets connection")
                return False
            
            # Get moderator info from "Пользователи" sheet
            moderator_info = await self._get_moderator_info_from_users_sheet(approving_user)
            
            # Extract data
            real_name = form_data.get('name', target_user.display_name)
            static = form_data.get('static', '')
            action = form_data.get('action', 'Принят в подразделение')
            department = form_data.get('department', 'Неизвестно')
            position = form_data.get('position', '')
            rank = form_data.get('rank', 'Неизвестно')
            discord_id = str(target_user.id)
            
            # Prepare row data for "Общий Кадровый" (columns A-L)
            row_data = [
                approval_time.strftime('%d.%m.%Y %H:%M'),  # A: Отметка времени
                f"{real_name} | {static}" if static else real_name,  # B: Имя Фамилия | 6 цифр статика
                real_name,  # C: Имя Фамилия
                static,  # D: Статик
                action,  # E: Действие
                approval_time.strftime('%d.%m.%Y'),  # F: Дата Действия
                department,  # G: Подразделение
                position,  # H: Должность
                rank,  # I: Звание
                discord_id,  # J: Discord ID бойца
                '',  # K: Причина увольнения (пустая)
                moderator_info  # L: Кадровую отписал
            ]
            
            # Insert record at the beginning (after headers)
            result = sheets_manager.worksheet.insert_row(row_data, index=2)
            
            if result:
                logger.info(f"Successfully added application record for {real_name} to 'Общий Кадровый'")
                return True
            else:
                logger.error(f"Failed to add application record for {real_name} to 'Общий Кадровый'")
                return False
                
        except Exception as e:
            logger.error(f"Error adding application record to 'Общий Кадровый': {e}")
            return False
    
    async def _get_moderator_info_from_users_sheet(self, moderator: discord.Member) -> str:
        """Get moderator info from 'Пользователи' sheet by Discord ID"""
        try:
            # Get "Пользователи" worksheet
            users_worksheet = None
            for worksheet in sheets_manager.spreadsheet.worksheets():
                if worksheet.title == 'Пользователи':
                    users_worksheet = worksheet
                    break
            
            if not users_worksheet:
                logger.warning("'Пользователи' worksheet not found")
                return moderator.display_name
            
            # Get all values from the worksheet
            all_values = users_worksheet.get_all_values()
            
            # Skip header row and search for moderator by Discord ID
            for row in all_values[1:]:  # Skip header row
                if len(row) >= 10:  # Ensure we have at least 10 columns (A-J)
                    discord_id_cell = str(row[5]).strip()  # Column F (index 5) - Discord ID
                    name_static_cell = str(row[9]).strip()  # Column J (index 9) - Имя Фамилия | Статик
                    
                    if discord_id_cell == str(moderator.id) and name_static_cell:
                        logger.info(f"Found moderator {moderator.display_name} in 'Пользователи': {name_static_cell}")
                        return name_static_cell
            
            # If not found in sheet, log warning and use Discord display name
            logger.warning(f"Moderator {moderator.display_name} (ID: {moderator.id}) not found in 'Пользователи' sheet")
            return moderator.display_name
            
        except Exception as e:
            logger.error(f"Error getting moderator info from 'Пользователи' sheet: {e}")
            return moderator.display_name
    
    async def _update_personal_roster(self, user: discord.Member, department: str, position: str):
        """Update or add user record in 'Личный Состав' sheet"""
        try:
            # Get user info from "Личный Состав" sheet
            if hasattr(sheets_manager, 'get_user_info_from_personal_list'):
                existing_info = await sheets_manager.get_user_info_from_personal_list(user.id)
                
                if existing_info:
                    # User exists - update department and position (columns E and F)
                    await self._update_existing_personal_record(user, department, position, existing_info)
                else:
                    # User doesn't exist - add new record at the end
                    await self._add_new_personal_record(user, department, position)
            else:
                logger.warning("Method 'get_user_info_from_personal_list' not available in sheets_manager")
                
        except Exception as e:
            logger.error(f"Error updating personal roster for {user.display_name}: {e}")
    
    async def _update_existing_personal_record(self, user: discord.Member, department: str, position: str, existing_info: dict):
        """Update existing user record in 'Личный Состав' sheet"""
        try:
            # Get personal roster worksheet
            personal_worksheet = None
            for worksheet in sheets_manager.spreadsheet.worksheets():
                if worksheet.title == 'Личный Состав':
                    personal_worksheet = worksheet
                    break
            
            if not personal_worksheet:
                logger.error("'Личный Состав' worksheet not found")
                return
            
            # Find the row with this user's Discord ID
            all_values = personal_worksheet.get_all_values()
            for i, row in enumerate(all_values[1:], start=2):  # Skip header row
                if len(row) >= 7 and str(row[6]).strip() == str(user.id):
                    # Update columns E (department) and F (position)
                    personal_worksheet.update_cell(i, 5, department)  # Column E
                    personal_worksheet.update_cell(i, 6, position)    # Column F
                    logger.info(f"Updated personal record for {user.display_name}: dept={department}, pos={position}")
                    return
            
            logger.warning(f"Could not find existing personal record for {user.display_name} (ID: {user.id})")
            
        except Exception as e:
            logger.error(f"Error updating existing personal record: {e}")
    
    async def _add_new_personal_record(self, user: discord.Member, department: str, position: str):
        """Add new user record to 'Личный Состав' sheet"""
        try:
            # Get personal roster worksheet
            personal_worksheet = None
            for worksheet in sheets_manager.spreadsheet.worksheets():
                if worksheet.title == 'Личный Состав':
                    personal_worksheet = worksheet
                    break
            
            if not personal_worksheet:
                logger.error("'Личный Состав' worksheet not found")
                return
            
            # Get user data from application
            first_name = ""
            last_name = ""
            full_name = self.application_data.get('name', user.display_name)
            static = self.application_data.get('static', '')
            
            # Try to split name into first and last name
            if full_name:
                name_parts = full_name.split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = " ".join(name_parts[1:])
                else:
                    first_name = full_name
            
            # Get user rank
            user_rank = sheets_manager.get_rank_from_roles(user) if hasattr(sheets_manager, 'get_rank_from_roles') else "Неизвестно"
            
            # Prepare row data for "Личный Состав" (columns A-G)
            row_data = [
                first_name,     # A: Имя
                last_name,      # B: Фамилия
                static,         # C: Статик
                user_rank,      # D: Звание
                department,     # E: Подразделение
                position,       # F: Должность
                str(user.id)    # G: Discord ID
            ]
            
            # Add record at the end
            personal_worksheet.append_row(row_data)
            logger.info(f"Added new personal record for {user.display_name}: {full_name}")
            
        except Exception as e:
            logger.error(f"Error adding new personal record: {e}")
    
    def _extract_role_mentions_from_content(self, content: str) -> List[List[int]]:
        """
        Extract role IDs from content lines
        Returns list of lists - each inner list contains role IDs from one line
        """
        import re
        
        lines = content.strip().split('\n') if content else []
        role_lines = []
        
        for line in lines:
            # Find all role mentions in format <@&role_id>
            role_pattern = r'<@&(\d+)>'
            role_ids = [int(match) for match in re.findall(role_pattern, line)]
            role_lines.append(role_ids)
        
        return role_lines
    
    async def _check_approve_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Check if user has permission to approve applications
        - Admins can approve anything
        - Moderators can only approve if they have at least one role from FIRST LINE of content
        """
        config = load_config()
        administrators = config.get('administrators', {})
        moderators = config.get('moderators', {})
        user_role_ids = [role.id for role in interaction.user.roles]
        
        # Check if user is administrator (can approve anything)
        is_admin = (
            interaction.user.id in administrators.get('users', []) or
            any(role_id in user_role_ids for role_id in administrators.get('roles', []))
        )
        
        if is_admin:
            return True
        
        # Check if user is moderator
        is_moderator = (
            interaction.user.id in moderators.get('users', []) or
            any(role_id in user_role_ids for role_id in moderators.get('roles', []))
        )
        
        if not is_moderator:
            return False
        
        # Extract roles from first line of content
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        if not role_lines or not role_lines[0]:
            # No roles in content or empty first line - fallback to old logic
            return await self._check_moderator_permissions(interaction)
        
        first_line_role_ids = role_lines[0]
        
        # Check if moderator has at least one role from first line
        has_required_role = any(role_id in user_role_ids for role_id in first_line_role_ids)
        
        return has_required_role
    
    async def _check_reject_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Check if user has permission to reject applications
        - Admins can reject anything
        - Moderators can reject if they have at least one role from ANY LINE of content
        """
        config = load_config()
        administrators = config.get('administrators', {})
        moderators = config.get('moderators', {})
        user_role_ids = [role.id for role in interaction.user.roles]
        
        # Check if user is administrator (can reject anything)
        is_admin = (
            interaction.user.id in administrators.get('users', []) or
            any(role_id in user_role_ids for role_id in administrators.get('roles', []))
        )
        
        if is_admin:
            return True
        
        # Check if user is moderator
        is_moderator = (
            interaction.user.id in moderators.get('users', []) or
            any(role_id in user_role_ids for role_id in moderators.get('roles', []))
        )
        
        if not is_moderator:
            return False
        
        # Extract roles from all lines of content
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        if not role_lines:
            # No roles in content - fallback to old logic
            return await self._check_moderator_permissions(interaction)
        
        # Collect all role IDs from all lines
        all_role_ids = []
        for line_roles in role_lines:
            all_role_ids.extend(line_roles)
        
        if not all_role_ids:
            # No roles found - fallback to old logic
            return await self._check_moderator_permissions(interaction)
        
        # Check if moderator has at least one role from any line
        has_required_role = any(role_id in user_role_ids for role_id in all_role_ids)
        
        return has_required_role
    
    def _get_approve_permission_error_message(self, interaction: discord.Interaction) -> str:
        """Get error message for approve permission denial"""
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        if role_lines and role_lines[0]:
            first_line_roles = [interaction.guild.get_role(role_id) for role_id in role_lines[0]]
            valid_roles = [role for role in first_line_roles if role is not None]
            
            if valid_roles:
                role_names = [role.name for role in valid_roles]
                return f"❌ Вы не можете одобрить это заявление.\n\n" \
                       f"**Для одобрения требуется одна из ролей:**\n" \
                       f"• {chr(10).join(f'`{name}`' for name in role_names)}"
        
        return "❌ У вас нет прав для одобрения этого заявления."
    
    def _get_reject_permission_error_message(self, interaction: discord.Interaction) -> str:
        """Get error message for reject permission denial"""
        content = interaction.message.content if interaction.message else ""
        role_lines = self._extract_role_mentions_from_content(content)
        
        all_role_ids = []
        for line_roles in role_lines:
            all_role_ids.extend(line_roles)
        
        if all_role_ids:
            all_roles = [interaction.guild.get_role(role_id) for role_id in all_role_ids]
            valid_roles = list(set([role for role in all_roles if role is not None]))  # Remove duplicates
            
            if valid_roles:
                role_names = [role.name for role in valid_roles]
                return f"❌ Вы не можете отклонить это заявление.\n\n" \
                       f"**Для отклонения требуется одна из ролей:**\n" \
                       f"• {chr(10).join(f'`{name}`' for name in role_names)}"
        
        return "❌ У вас нет прав для отклонения этого заявления."

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
            
            # Clear user's cache since status changed
            _clear_user_cache(self.application_data['user_id'])
            
            rejected_button = ui.Button(
                label="❌ Отклонено",
                style=discord.ButtonStyle.red,
                disabled=True
            )
            view.add_item(rejected_button)
            
            await interaction.edit_original_response(content="", embed=embed, view=view)
            
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
        
        # Set custom_id for persistence - ВАЖНО!
        self.custom_id = f"dept_select_{department_code}"
        
        # Update button custom_ids to be unique per department
        self.join_button.custom_id = f"dept_app_join_{department_code}"
        self.transfer_button.custom_id = f"dept_app_transfer_{department_code}"
    
    @ui.button(label="Заявление в подразделение", style=discord.ButtonStyle.green, emoji="➕")
    async def join_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle department join application"""
        await self._handle_application_type(interaction, "join")
    
    @ui.button(label="Перевод из другого подразделения", style=discord.ButtonStyle.blurple, emoji="🔄")
    async def transfer_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle department transfer application"""
        await self._handle_application_type(interaction, "transfer")
    
    async def _handle_application_type(self, interaction: discord.Interaction, app_type: str):
        """Handle department application type selection"""
        try:
            # Get department code from view's custom_id: dept_select_{department_code}
            if hasattr(self, 'custom_id') and self.custom_id.startswith('dept_select_'):
                department_code = self.custom_id.replace('dept_select_', '')
            else:
                # Fallback to instance variable
                department_code = getattr(self, 'department_code', 'ВВ')
            
            # Update instance variables for compatibility
            self.department_code = department_code
            
            # БЫСТРАЯ ОТПРАВКА МОДАЛЬНОГО ОКНА - отвечаем в течение 1 секунды
            from .modals import DepartmentApplicationStage1Modal
            modal = DepartmentApplicationStage1Modal(department_code, app_type, interaction.user.id, skip_data_loading=True)
            await interaction.response.send_modal(modal)
            
            # ПРОВЕРКА АКТИВНЫХ ЗАЯВЛЕНИЙ В ФОНЕ (асинхронно)
            # Если найдем активные заявления - закроем модальное окно через followup
            try:
                active_check = await check_user_active_applications(
                    interaction.guild, 
                    interaction.user.id
                )
                
                if active_check['has_active']:
                    # Модальное окно уже открыто, но мы можем отправить уведомление
                    # Discord автоматически закроет модальное окно при отправке followup
                    departments_list = ", ".join(active_check['departments'])
                    await interaction.followup.send(
                        f"❌ **У вас уже есть активное заявление на рассмотрении**\n\n"
                        f"📋 Подразделения: **{departments_list}**\n"
                        f"⏳ Дождитесь рассмотрения текущего заявления перед подачей нового.\n\n"
                        f"💡 Активные заявления можно найти в каналах заявлений соответствующих подразделений.",
                        ephemeral=True
                    )
                    # Пользователь увидит это сообщение, если попытается отправить заявление
                    
            except Exception as bg_error:
                logger.warning(f"Background check for active applications failed: {bg_error}")
                # Не останавливаем процесс - пользователь может продолжить подачу заявления
            
        except Exception as e:
            logger.error(f"Error in department application: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Произошла ошибка. Попробуйте еще раз.",
                    ephemeral=True
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "❌ Произошла ошибка. Попробуйте еще раз.",
                    ephemeral=True
                )

# Active applications cache for performance optimization
_active_applications_cache = {}
_cache_expiry = {}

def _is_cache_valid(user_id: int) -> bool:
    """Check if cache for user is still valid"""
    if user_id not in _cache_expiry:
        return False
    
    from datetime import datetime, timedelta
    return datetime.now() < _cache_expiry[user_id]

def _cache_user_active_status(user_id: int, has_active: bool, departments: list):
    """Cache user's active application status for 30 seconds"""
    from datetime import datetime, timedelta
    
    _active_applications_cache[user_id] = {
        'has_active': has_active,
        'departments': departments
    }
    _cache_expiry[user_id] = datetime.now() + timedelta(seconds=30)

def _get_cached_active_status(user_id: int) -> Dict:
    """Get cached active status if available and valid"""
    if _is_cache_valid(user_id):
        cached = _active_applications_cache.get(user_id, {})
        return {
            'has_active': cached.get('has_active', False),
            'applications': [],  # Don't cache message objects
            'departments': cached.get('departments', [])
        }
    return None

def _clear_user_cache(user_id: int):
    """Clear cache for user (call when application is submitted/processed)"""
    _active_applications_cache.pop(user_id, None)
    _cache_expiry.pop(user_id, None)

async def check_user_active_applications(guild: discord.Guild, user_id: int, department_code: str = None) -> Dict:
    """
    Check if user has any active (pending) applications - OPTIMIZED WITH CACHE
    
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
    # Try cache first (30 second expiry)
    cached_result = _get_cached_active_status(user_id)
    if cached_result is not None:
        logger.info(f"⚡ Using cached active applications status for user {user_id}")
        return cached_result
    
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
        
        # OPTIMIZATION: Limit search and use timeout
        max_messages_per_channel = 50  # Reduced from 100
        search_timeout = 2.0  # Maximum 2 seconds per channel
        
        for dept_code in depts_to_check:
            dept_config = departments.get(dept_code, {})
            channel_id = dept_config.get('application_channel_id')
            
            if not channel_id:
                continue
                
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            
            try:
                # Use asyncio.timeout for faster failure
                import asyncio
                
                async def check_channel_for_user():
                    # Check recent messages for user's applications
                    async for message in channel.history(limit=max_messages_per_channel):
                        if not message.embeds:
                            continue
                            
                        embed = message.embeds[0]
                        
                        # Quick check if this is a department application
                        if not embed.footer or not embed.footer.text:
                            continue
                            
                        if f"ID заявления: {user_id}" in embed.footer.text:
                            # Quick check if application is still pending (has view with enabled buttons)
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
                                            return True  # Early exit when found
                            break  # Only check the most recent application per user per department
                    return False
                
                # Apply timeout to channel check
                found_active = await asyncio.wait_for(check_channel_for_user(), timeout=search_timeout)
                
                # If found active application, we can stop checking other departments
                if found_active and not department_code:
                    break
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout checking active applications in department {dept_code} - skipping")
                continue
            except Exception as channel_error:
                logger.error(f"Error checking applications in department {dept_code}: {channel_error}")
                continue
        
        # Cache the result for 30 seconds
        _cache_user_active_status(user_id, result['has_active'], result['departments'])
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking user active applications: {e}")
        return result
