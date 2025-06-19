"""
Dismissal system views
Contains interactive components (buttons and views) for dismissal reports
"""

import discord
from discord import ui
import asyncio
import re
import traceback
from datetime import datetime
from utils.config_manager import load_config, is_moderator_or_admin, can_moderate_user
from utils.google_sheets import sheets_manager
from utils.user_database import UserDatabase


# Constants for UI elements and messages
class DismissalConstants:
    # UI Labels
    PROCESSING_LABEL = "⏳ Обрабатывается..."
    APPROVED_LABEL = "✅ Одобрено"
    REJECTED_LABEL = "❌ Отказано"
    
    # Error Messages
    NO_PERMISSION_APPROVAL = "❌ У вас нет прав для одобрения рапортов на увольнение. Только модераторы могут выполнять это действие."
    NO_PERMISSION_REJECTION = "❌ У вас нет прав для отказа рапортов на увольнение. Только модераторы могут выполнять это действие."
    AUTHORIZATION_ERROR = "❌ Ошибка проверки авторизации модератора."
    GENERAL_ERROR = "❌ Произошла ошибка при обработке рапорта. Пожалуйста, обратитесь к администратору."
    PROCESSING_ERROR_APPROVAL = "❌ Произошла ошибка при обработке одобрения заявки."
    PROCESSING_ERROR_REJECTION = "❌ Произошла ошибка при обработке отказа"
    AUTH_DATA_ERROR = "❌ Произошла ошибка при обработке данных авторизации."
    DISMISSAL_PROCESSING_ERROR = "❌ Произошла ошибка при обработке увольнения."
    
    # Success Messages
    STATIC_RECEIVED = "✅ Статик получен, продолжаем обработку..."
    
    # Form Field Names
    FIELD_NAME = "Имя Фамилия"
    FIELD_STATIC = "Статик"
    FIELD_DEPARTMENT = "Подразделение"
    FIELD_RANK = "Воинское звание"
    FIELD_REASON = "Причина увольнения"
    
    # Automatic Report Indicators
    AUTO_REPORT_INDICATOR = "🚨 Автоматический рапорт на увольнение"
    STATIC_INPUT_REQUIRED = "Требуется ввод"
    
    # Nickname Prefixes
    DISMISSED_PREFIX = "Уволен | "
    
    # Self-moderation errors
    SELF_APPROVAL_ERROR = "Вы не можете одобрить свой собственный рапорт на увольнение."
    SELF_REJECTION_ERROR = "Вы не можете отклонить свой собственный рапорт на увольнение."
    MODERATOR_HIERARCHY_APPROVAL = "Вы не можете одобрить рапорт модератора того же или более высокого уровня."
    MODERATOR_HIERARCHY_REJECTION = "Вы не можете отклонить рапорт модератора того же или более высокого уровня."
    INSUFFICIENT_PERMISSIONS_APPROVAL = "У вас недостаточно прав для одобрения этого рапорта."
    INSUFFICIENT_PERMISSIONS_REJECTION = "У вас недостаточно прав для отклонения этого рапорта."
    
    # Footer and audit text patterns
    REPORT_SENDER_PREFIX = "Отправлено:"
    AUDIT_NAME_STATIC_FIELD = "Имя Фамилия | 6 цифр статика"
    BLACKLIST_SHEET_NAME = "Отправлено (НЕ РЕДАКТИРОВАТЬ)"
    
    # Default values
    UNKNOWN_VALUE = "Неизвестно"
    
    # Rejection button label
    REJECT_BUTTON_LABEL = "❌ Отказать"


class DismissalReportButton(ui.View):
    """Simple button view for creating dismissal reports"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Отправить рапорт на увольнение", style=discord.ButtonStyle.red, custom_id="dismissal_report")
    async def dismissal_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .modals import DismissalReportModal
        modal = await DismissalReportModal.create_with_user_data(interaction.user.id)
        await interaction.response.send_modal(modal)


class DismissalApprovalView(ui.View):
    """Approval/Rejection view for dismissal reports with complex processing logic"""
    def __init__(self, user_id=None, is_automatic=False):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.is_automatic = is_automatic  # Flag for automatic dismissal reports
    
    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, custom_id="approve_dismissal")
    async def approve_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Load configuration and validate permissions
            config = load_config()
            if not await self._validate_moderator_permissions(interaction, config):
                return
                
            # Extract all required data
            target_user, user_has_left_server = self._extract_target_user(interaction)
            if not await self._validate_hierarchical_permissions(interaction, target_user, user_has_left_server, config):
                return
                  # Get audit and form data
            current_time = discord.utils.utcnow()
            embed = interaction.message.embeds[0]
            user_rank_for_audit, user_unit_for_audit = self._extract_audit_data(embed, target_user, user_has_left_server, config.get('ping_settings', {}))
            form_data, is_automatic_report = self._extract_form_data(embed)
            
            # Add is_automatic_report to form_data for passing to modals
            form_data['is_automatic_report'] = is_automatic_report
            
            # Handle authorization flow
            auth_result = await self._handle_moderator_authorization(interaction, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server)
            if not auth_result:
                return  # Authorization handled via modal or error occurred
                
            signed_by_name = auth_result
            
            # Handle automatic reports requiring static
            if await self._handle_automatic_report_static(interaction, is_automatic_report, form_data, target_user, user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server, signed_by_name):
                return  # Static request handled via modal
                  # Continue with normal processing
            await self._finalize_approval_processing(interaction, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, signed_by_name, config, user_has_left_server)
            
        except Exception as e:
            await self._handle_approval_error(interaction, e)
    
    @discord.ui.button(label=DismissalConstants.REJECT_BUTTON_LABEL, style=discord.ButtonStyle.red, custom_id="reject_dismissal")
    async def reject_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Load configuration and validate permissions
            config = load_config()
            if not await self._validate_moderator_permissions(interaction, config):
                return
                
            # Extract target user and validate permissions
            target_user, user_has_left_server = self._extract_target_user(interaction)
            if not await self._validate_hierarchical_permissions(interaction, target_user, user_has_left_server, config):
                return
            
            # Directly request rejection reason without authorization check
            await self._request_rejection_reason(interaction, target_user)
                    
        except Exception as e:
            await self._handle_rejection_error(interaction, e)

    def _extract_target_user(self, interaction: discord.Interaction):
        """Extract target user from view or embed footer, creating MockUser if user left server"""
        target_user = None
        
        if self.user_id:
            target_user = interaction.guild.get_member(self.user_id)
        else:
            # Try to extract user info from embed footer
            embed = interaction.message.embeds[0]
            if embed.footer and embed.footer.text:
                footer_text = embed.footer.text
                if DismissalConstants.REPORT_SENDER_PREFIX in footer_text:
                    username = footer_text.replace(DismissalConstants.REPORT_SENDER_PREFIX, "").strip()
                    # Try to find user by username
                    for member in interaction.guild.members:
                        if member.name == username or member.display_name == username:
                            target_user = member
                            break
        
        # Handle case when user has already left the server or doesn't exist
        user_has_left_server = target_user is None
        
        if user_has_left_server:
            # Create a comprehensive mock user class for users who left
            class MockUser:
                def __init__(self, name, user_id=None):
                    self.display_name = name
                    self.name = name
                    self.id = user_id or 0
                    self.mention = f"@{name}"
                    self.roles = []  # Empty roles list for compatibility
                    self.guild = None  # No guild reference
                    self._is_mock = True  # Flag to identify mock users
                    
                def __str__(self):
                    return self.display_name
                    
                # Add missing methods that might be called
                async def remove_roles(self, *roles, reason=None):
                    # Mock method - do nothing for users who left
                    pass
                    
                async def edit(self, **kwargs):
                    # Mock method - do nothing for users who left
                    pass
                    
                async def send(self, content=None, **kwargs):
                    # Mock method - do nothing for users who left
                    pass
            
            # Extract user info from embed to create mock user
            embed = interaction.message.embeds[0]
            user_name_for_logging = "Покинул сервер"
            user_id_for_logging = None
              # Try to extract user info from embed footer
            if embed.footer and embed.footer.text:
                footer_text = embed.footer.text
                if DismissalConstants.REPORT_SENDER_PREFIX in footer_text:
                    user_name_for_logging = footer_text.replace(DismissalConstants.REPORT_SENDER_PREFIX, "").strip()
            
            # Try to extract user ID from embed description or fields
            if embed.description:
                # Look for user ID in description (format: <@123456789>)
                import re
                user_id_match = re.search(r'<@(\d+)>', embed.description)
                if user_id_match:
                    user_id_for_logging = int(user_id_match.group(1))
            
            target_user = MockUser(user_name_for_logging, user_id_for_logging)
            print(f"Created MockUser for left server user: {user_name_for_logging} (ID: {user_id_for_logging})")
        
        return target_user, user_has_left_server
    
    def _extract_form_data(self, embed):
        """Extract form data from embed fields"""
        form_data = {}
        is_automatic_report = False
          # Check if this is an automatic report by looking for specific indicators
        if embed.description and DismissalConstants.AUTO_REPORT_INDICATOR in embed.description:
            is_automatic_report = True
        
        for field in embed.fields:
            if field.name == DismissalConstants.FIELD_NAME:
                form_data['name'] = field.value
            elif field.name == DismissalConstants.FIELD_STATIC:
                # Check if static is missing (automatic report)
                if DismissalConstants.STATIC_INPUT_REQUIRED in field.value:
                    form_data['static'] = None  # Will be requested from moderator
                    is_automatic_report = True
                else:
                    form_data['static'] = field.value
            elif field.name == DismissalConstants.FIELD_DEPARTMENT:
                form_data['department'] = field.value
            elif field.name == DismissalConstants.FIELD_RANK:
                form_data['rank'] = field.value
            elif field.name == DismissalConstants.FIELD_REASON:
                form_data['reason'] = field.value
            
        return form_data, is_automatic_report
    def _extract_audit_data(self, embed, target_user, user_has_left_server, ping_settings):
        """Extract rank and department data for audit"""
        user_rank_for_audit = DismissalConstants.UNKNOWN_VALUE
        user_unit_for_audit = DismissalConstants.UNKNOWN_VALUE
          # Extract from embed fields (works for both present and absent users)
        for field in embed.fields:
            if field.name == DismissalConstants.FIELD_RANK:
                user_rank_for_audit = field.value
            elif field.name == DismissalConstants.FIELD_DEPARTMENT:
                user_unit_for_audit = field.value
                # If embed doesn't have the data and user is present, try to get from roles
        if (user_rank_for_audit == DismissalConstants.UNKNOWN_VALUE or user_unit_for_audit == DismissalConstants.UNKNOWN_VALUE) and not user_has_left_server:
            try:
                if user_rank_for_audit == DismissalConstants.UNKNOWN_VALUE:
                    role_rank = sheets_manager.get_rank_from_roles(target_user)
                    if role_rank != DismissalConstants.UNKNOWN_VALUE:
                        user_rank_for_audit = role_rank
                
                if user_unit_for_audit == DismissalConstants.UNKNOWN_VALUE:
                    role_unit = sheets_manager.get_department_from_roles(target_user, ping_settings)
                    if role_unit != DismissalConstants.UNKNOWN_VALUE:
                        user_unit_for_audit = role_unit
            except Exception as e:
                print(f"Error getting data from roles: {e}")
        
        print(f"Audit data - User: {target_user.display_name}, Rank: {user_rank_for_audit}, Unit: {user_unit_for_audit}, Left server: {user_has_left_server}")
        
        return user_rank_for_audit, user_unit_for_audit
    
    async def _continue_dismissal_with_manual_auth(self, interaction, moderator_data, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server=False):
        """Continue dismissal process with manually entered moderator data."""
        try:
            print(f"DEBUG: _continue_dismissal_with_manual_auth called with moderator_data: {moderator_data}")
            
            # Moderator is already registered in Google Sheets by the unified auth module
            # Just extract the signed_by_name
            signed_by_name = moderator_data['full_info']  # "Имя Фамилия | Статик"
            print(f"DEBUG: signed_by_name set to: {signed_by_name}")
            
            # Check if we still need to request static (for automatic reports)
            is_automatic_report = form_data.get('is_automatic_report', False)
            
            print(f"DEBUG: is_automatic_report: {is_automatic_report}, form_data static: {form_data.get('static')}")
            
            # If we need static, inform user to click Approve again
            if is_automatic_report and not form_data.get('static'):
                print(f"Manual auth completed, but still need static for automatic dismissal")
                
                # Since we can't open a second modal from a modal callback,
                # we'll ask the user to click "Approve" again to enter static
                try:
                    await interaction.followup.send(
                        "✅ **Авторизация модератора завершена успешно!**\n\n"
                        "📋 **Следующий шаг:** Для автоматического рапорта на увольнение требуется указать статик покинувшего сервера пользователя.\n\n"
                        "🔄 **Действие:** Нажмите кнопку \"✅ Одобрить\" ещё раз для ввода статика и завершения обработки увольнения.\n\n"
                        "ℹ️ Это необходимо из-за ограничений Discord на открытие нескольких модальных окон подряд.",
                        ephemeral=True
                    )
                except Exception as followup_error:
                    print(f"Warning: Could not send followup message: {followup_error}")
                
                return  # User needs to click Approve again
            
            print(f"DEBUG: Proceeding with manual auth processing")
            
            # For modal interactions, response is already handled in the modal
            # We should only send followup messages, not defer again
            print(f"DEBUG: Interaction response is_done: {interaction.response.is_done()}")
            
            # Send processing notification via followup (safer for modal interactions)
            try:
                await interaction.followup.send(
                    "🔄 **Обработка увольнения...**\nПожалуйста, подождите...",
                    ephemeral=True
                )
            except Exception as followup_error:
                print(f"Warning: Could not send followup message: {followup_error}")
                # Continue processing anyway
            config = load_config()  # Load config for this method
            await self._process_dismissal_approval(
                interaction, target_user, form_data,
                user_rank_for_audit, user_unit_for_audit,
                current_time, signed_by_name, config, override_moderator_info=signed_by_name, user_has_left_server=user_has_left_server
            )
        except Exception as e:
            print(f"Error in manual auth dismissal continuation: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(DismissalConstants.AUTH_DATA_ERROR, ephemeral=True)
                else:
                    await interaction.followup.send(DismissalConstants.AUTH_DATA_ERROR, ephemeral=True)
            except Exception as follow_error:
                print(f"Failed to send auth error message: {follow_error}")

    async def _continue_dismissal_with_static_after_auth(self, interaction, static, original_interaction, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server, signed_by_name):
        """Continue dismissal process after receiving static from moderator when authorization is already done."""
        try:
            # Update form_data with the provided static
            form_data['static'] = static
            
            # Update the embed to show the provided static
            embed = original_interaction.message.embeds[0]
            
            # Find and update the static field
            for i, field in enumerate(embed.fields):
                if field.name == "Статик":
                    embed.set_field_at(i, name="Статик", value=static, inline=True)
                    break            # Show processing state
            await self._show_processing_state_for_original_interaction(original_interaction, embed)
            
            # Small delay to show processing state
            await asyncio.sleep(0.5)
            
            # Send response to static input modal
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "✅ Статик получен, продолжаем обработку...",
                    ephemeral=True
                )
              # Continue with normal dismissal processing (authorization already done)
            config = load_config()  # Load config for this method
            await self._process_dismissal_approval(
                original_interaction, target_user, form_data,
                user_rank_for_audit, user_unit_for_audit,
                current_time, signed_by_name, config, override_moderator_info=None, user_has_left_server=user_has_left_server
            )
        except Exception as e:
            print(f"Error in dismissal continuation with static after auth: {e}")
            await interaction.followup.send("❌ Произошла ошибка при обработке увольнения.", ephemeral=True)
    async def _process_dismissal_approval(self, interaction, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, signed_by_name, config, override_moderator_info=None, user_has_left_server=False):
        """Complete dismissal approval process with moderator information."""
        try:
            excluded_roles_ids = config.get('excluded_roles', [])
            ping_settings = config.get('ping_settings', {})
              # Log to Google Sheets BEFORE removing roles (to capture rank and department correctly)
            try:
                success = await sheets_manager.add_dismissal_record(
                    form_data=form_data,
                    dismissed_user=target_user,
                    approving_user=interaction.user,
                    dismissal_time=current_time,
                    ping_settings=ping_settings,
                    override_moderator_info=override_moderator_info
                )
                if success:
                    print(f"Successfully logged dismissal to Google Sheets for {target_user.display_name}")
                else:
                    print(f"Failed to log dismissal to Google Sheets for {target_user.display_name}")
            except Exception as e:
                print(f"Error logging to Google Sheets: {e}")
            
            # Remove user from personnel database
            try:
                user_id = getattr(target_user, 'id', None)
                if user_id:
                    registry_success = await UserDatabase.remove_user(user_id)
                    if not registry_success:
                        print(f"⚠️ Could not remove user {target_user.display_name} from personnel registry")
                        # Send error notification to moderator
                        try:
                            await interaction.followup.send(
                                "⚠️ **Внимание:** Не удалось удалить пользователя из реестра личного состава. Обратитесь к руководству бригады.",
                                ephemeral=True
                            )
                        except:
                            pass  # If followup fails, continue silently
                else:
                    print(f"⚠️ Could not get user ID for {target_user.display_name}")
            except Exception as e:
                print(f"❌ Error removing user from personnel registry: {e}")
                # Send error notification to moderator
                try:
                    await interaction.followup.send(
                        "⚠️ **Внимание:** Ошибка при удалении из реестра личного состава. Обратитесь к руководству бригады.",
                        ephemeral=True
                    )
                except:
                    pass  # If followup fails, continue silently
            
            # Remove all roles from the user (except @everyone and excluded roles)
            # Skip if user has left the server or is a MockUser
            roles_removed = False
            if not user_has_left_server and not getattr(target_user, '_is_mock', False):
                roles_to_remove = []
                for role in target_user.roles:
                    if role.name != "@everyone" and role.id not in excluded_roles_ids:
                        roles_to_remove.append(role)
                
                if roles_to_remove:
                    try:
                        await target_user.remove_roles(*roles_to_remove, reason="Рапорт на увольнение одобрен")
                        roles_removed = True
                        print(f"Successfully removed {len(roles_to_remove)} roles from {target_user.display_name}")
                    except discord.HTTPException as e:
                        print(f"Failed to remove roles from {target_user.display_name}: {e}")
                else:
                    print(f"No roles to remove from {target_user.display_name}")
            else:
                print(f"Skipping role removal for {target_user.display_name} - user has left server or is MockUser")
            
            # Change nickname to "Уволен | Имя Фамилия"
            # Skip if user has left the server or is a MockUser
            nickname_changed = False
            if not user_has_left_server and not getattr(target_user, '_is_mock', False):
                try:
                    # Extract name from current nickname or username
                    current_name = target_user.display_name
                    
                    new_nickname = self._format_dismissal_nickname(current_name)
                    
                    await target_user.edit(nick=new_nickname, reason="Рапорт на увольнение одобрен")
                    nickname_changed = True
                    print(f"Successfully changed nickname for {target_user.display_name} to {new_nickname}")
                except discord.Forbidden:
                    # Bot doesn't have permission to change nickname
                    print(f"Cannot change nickname for {target_user.name} - insufficient permissions")
                except Exception as e:
                    print(f"Error changing nickname for {target_user.name}: {e}")
            else:
                print(f"Skipping nickname change for {target_user.display_name} - user has left server or is MockUser")
              # Update the embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
              # Create status message based on what actions were performed
            status_parts = [f"Сотрудник: {interaction.user.mention}", f"Время: {discord.utils.format_dt(discord.utils.utcnow(), 'F')}"]
            
            if user_has_left_server:
                status_parts.append("⚠️ Роли и никнейм не изменены")
            
            embed.add_field(
                name="Обработано", 
                value="\n".join(status_parts),
                inline=False
            )
              # Create new view with only "Approved" button (disabled)
            approved_view = ui.View(timeout=None)
            approved_button = ui.Button(label=DismissalConstants.APPROVED_LABEL, style=discord.ButtonStyle.green, disabled=True)
            approved_view.add_item(approved_button)
            
            # Safe message editing - check if interaction has message attribute
            try:
                if hasattr(interaction, 'message') and interaction.message:
                    await interaction.followup.edit_message(interaction.message.id, content="", embed=embed, view=approved_view)
                else:
                    # This interaction is from modal, find original message via webhook
                    # For now, we'll skip the message update and just log success
                    print("✅ Dismissal processed successfully (message update skipped - modal interaction)")
            except Exception as edit_error:
                print(f"⚠️ Could not update message: {edit_error}")
            
            # Send notification to audit channel
            audit_message_url = None
            try:
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        # Create audit notification embed
                        audit_embed = discord.Embed(
                            title="Кадровый аудит ВС РФ",
                            color=0x055000,  # Green color as in template
                            timestamp=discord.utils.utcnow()
                        )
                        
                        # Format date as dd-MM-yyyy
                        action_date = discord.utils.utcnow().strftime('%d-%m-%Y')
                          # Combine name and static for "Имя Фамилия | 6 цифр статика" field
                        name_with_static = f"{form_data.get('name', DismissalConstants.UNKNOWN_VALUE)} | {form_data.get('static', '')}"
                          # Set fields according to template
                        audit_embed.add_field(name="Кадровую отписал", value=signed_by_name, inline=False)
                        audit_embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
                        audit_embed.add_field(name="Действие", value="Уволен со службы", inline=False)
                        
                        # Add reason field only if reason exists
                        reason = form_data.get('reason', '')
                        if reason:
                            audit_embed.add_field(name="Причина увольнения", value=reason, inline=False)
                        
                        audit_embed.add_field(name="Дата Действия", value=action_date, inline=False)
                        audit_embed.add_field(name="Подразделение", value=user_unit_for_audit, inline=False)
                        audit_embed.add_field(name="Воинское звание", value=user_rank_for_audit, inline=False)
                        
                        # Set thumbnail to default image as in template
                        audit_embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
                        
                        # Send notification with user mention (the user who was dismissed)
                        audit_message = await audit_channel.send(content=f"<@{target_user.id}>", embed=audit_embed)
                        audit_message_url = audit_message.jump_url
                        print(f"Sent audit notification for dismissal of {target_user.display_name}")
                    else:
                        print(f"Audit channel not found: {audit_channel_id}")
                else:
                    print("Audit channel ID not configured")
            except Exception as e:
                print(f"Error sending audit notification: {e}")
              
            # Check for early dismissal penalty (less than 5 days of service)
            try:
                static = form_data.get('static', '')
                print(f"🔍 CHECKING EARLY DISMISSAL: Static = {static}")
                
                if static:
                    print(f"🔍 Searching for hiring record by static: {static}")
                    hiring_record = await sheets_manager.get_latest_hiring_record_by_static(static)
                    
                    if hiring_record:
                        print(f"✅ Found hiring record: {hiring_record}")
                        hire_date_str = str(hiring_record.get('Дата Действия', '')).strip()
                        print(f"🔍 Hire date string: '{hire_date_str}'")
                        
                        if hire_date_str:
                            try:
                                # Parse hire date
                                hire_date = None
                                
                                # If date contains time, extract date part
                                if ' ' in hire_date_str:
                                    date_part = hire_date_str.split(' ')[0]
                                else:
                                    date_part = hire_date_str
                                
                                print(f"🔍 Parsing date part: '{date_part}'")
                                  
                                # Try different date formats
                                try:
                                    hire_date = datetime.strptime(date_part, '%d.%m.%Y')
                                    print(f"✅ Parsed date with format %d.%m.%Y: {hire_date}")
                                except ValueError:
                                    try:
                                        hire_date = datetime.strptime(date_part, '%d-%m-%Y')
                                        print(f"✅ Parsed date with format %d-%m-%Y: {hire_date}")
                                    except ValueError:
                                        # Try full datetime format
                                        try:
                                            hire_date = datetime.strptime(hire_date_str, '%d.%m.%Y %H:%M:%S')
                                            print(f"✅ Parsed date with format %d.%m.%Y %H:%M:%S: {hire_date}")
                                        except ValueError:
                                            hire_date = datetime.strptime(hire_date_str, '%d-%m-%Y %H:%M:%S')
                                            print(f"✅ Parsed date with format %d-%m-%Y %H:%M:%S: {hire_date}")
                                
                                # Calculate days difference
                                dismissal_date = current_time.replace(tzinfo=None)
                                days_difference = (dismissal_date - hire_date).days
                                print(f"📊 DAYS CALCULATION:")
                                print(f"   Hire Date: {hire_date}")
                                print(f"   Dismissal Date: {dismissal_date}")
                                print(f"   Days Difference: {days_difference}")
                                
                                if days_difference < 5:
                                    print(f"🚨 EARLY DISMISSAL DETECTED: {days_difference} days of service for {form_data.get('name', 'Unknown')}")
                                    # Send to blacklist channel with audit message URL and approving user
                                    blacklist_result = await sheets_manager.send_to_blacklist(
                                        guild=interaction.guild,
                                        form_data=form_data,
                                        days_difference=days_difference,
                                        audit_message_url=audit_message_url,
                                        approving_user=interaction.user,
                                        override_moderator_info=override_moderator_info
                                    )
                                    print(f"📋 Blacklist channel result: {blacklist_result}")
                                    
                                    # Log penalty to "Отправлено (НЕ РЕДАКТИРОВАТЬ)" sheet
                                    try:
                                        penalty_logged = await sheets_manager.add_blacklist_record(
                                            form_data=form_data,
                                            dismissed_user=target_user,
                                            approving_user=interaction.user,
                                            dismissal_time=current_time,
                                            days_difference=days_difference,
                                            override_moderator_info=override_moderator_info
                                        )
                                        print(f"📊 Google Sheets blacklist result: {penalty_logged}")
                                        
                                        if penalty_logged:
                                            print(f"✅ Successfully logged early dismissal penalty for {form_data.get('name', 'Unknown')}")
                                        else:
                                            print(f"❌ Failed to log early dismissal penalty for {form_data.get('name', 'Unknown')}")
                                    except Exception as penalty_error:
                                        print(f"❌ Error logging penalty to blacklist sheet: {penalty_error}")
                                else:
                                    print(f"✅ Normal dismissal: {days_difference} days of service (≥5 days)")
                            
                            except ValueError as date_error:
                                print(f"❌ Error parsing hire date '{hire_date_str}': {date_error}")
                        else:
                            print(f"⚠️ Hire date string is empty in record: {hiring_record}")
                    else:
                        print(f"⚠️ No hiring record found for static {static}")
                else:
                    print(f"⚠️ No static provided in form_data: {form_data}")
            except Exception as e:
                print(f"❌ Error checking for early dismissal: {e}")
                import traceback
                traceback.print_exc()
            
            # Send DM to the user (only if they're still on the server and not a MockUser)
            if not user_has_left_server and not getattr(target_user, '_is_mock', False):
                try:
                    await target_user.send(
                        f"## ✅ Ваш рапорт на увольнение был **одобрен** сотрудником {interaction.user.mention}.\n"
                        f"С вас были сняты все роли.\n\n"
                        f"## 📋 Что делать дальше?\n"
                        f"> Как только вы снова зайдёте в игру, то, возможно, окажитесь на территории В/Ч.\n"
                        f"> В таком случае вежливо попросите любого офицера вас провести до выхода.\n"
                        f"> - *Самостоятельно по территории В/Ч разгуливать запрещено!*"
                    )
                except discord.Forbidden:
                    pass  # User has DMs disabled            else:
                print(f"Skipping DM to {target_user.display_name} - user has left server or is MockUser")
            
        except Exception as e:
            print(f"Error in _process_dismissal_approval: {e}")
            await interaction.followup.send(
                DismissalConstants.PROCESSING_ERROR_APPROVAL,
                ephemeral=True
            )
    
    async def _validate_moderator_permissions(self, interaction: discord.Interaction, config: dict) -> bool:
        """Validate basic moderator permissions."""
        if not is_moderator_or_admin(interaction.user, config):
            await interaction.response.send_message(
                DismissalConstants.NO_PERMISSION_APPROVAL,
                ephemeral=True
            )
            return False
        
        print(f"User {interaction.user.display_name} found in config moderators - proceeding")
        return True
    
    async def _validate_hierarchical_permissions(self, interaction: discord.Interaction, target_user, user_has_left_server: bool, config: dict) -> bool:
        """Validate hierarchical moderation permissions."""
        if not user_has_left_server and not can_moderate_user(interaction.user, target_user, config):
            # Determine the reason for denial
            if interaction.user.id == target_user.id:
                reason = "Вы не можете одобрить свой собственный рапорт на увольнение."
            elif is_moderator_or_admin(target_user, config):
                reason = "Вы не можете одобрить рапорт модератора того же или более высокого уровня."
            else:
                reason = "У вас недостаточно прав для одобрения этого рапорта."
            
            await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
            return False
        return True
    
    async def _validate_rejection_permissions(self, interaction: discord.Interaction, target_user, config: dict) -> bool:
        """Validate hierarchical permissions for rejection."""
        if target_user and not can_moderate_user(interaction.user, target_user, config):
            # Restore original buttons since permission check failed
            original_view = DismissalApprovalView(self.user_id)
            embed = interaction.message.embeds[0]
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=original_view)
            
            # Determine the reason for denial
            if interaction.user.id == target_user.id:
                reason = "Вы не можете отклонить свой собственный рапорт на увольнение."
            elif is_moderator_or_admin(target_user, config):
                reason = "Вы не можете отклонить рапорт модератора того же или более высокого уровня."
            else:
                reason = "У вас недостаточно прав для отклонения этого рапорта."            
            await interaction.followup.send(f"❌ {reason}", ephemeral=True)
            return False
        return True

    async def _finalize_rejection(self, interaction: discord.Interaction, target_user, rejection_reason=None):
        """Finalize the rejection process with UI updates and notifications."""
        # Update the embed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        
        embed.add_field(
            name="Обработано", 
            value=f"Сотрудник: {interaction.user.mention}\nВремя: {discord.utils.format_dt(discord.utils.utcnow(), 'F')}", 
            inline=False
        )
        
        # Add rejection reason if provided
        if rejection_reason:
            embed.add_field(
                name="Причина отказа",
                value=rejection_reason,
                inline=False
            )
        
        # Create new view with only "Rejected" button (disabled)
        rejected_view = ui.View(timeout=None)
        rejected_button = ui.Button(label=DismissalConstants.REJECTED_LABEL, style=discord.ButtonStyle.red, disabled=True)
        rejected_view.add_item(rejected_button)
        
        await interaction.followup.edit_message(interaction.message.id, content="", embed=embed, view=rejected_view)
        
        # Send DM to the user if they're still on the server
        if target_user and not getattr(target_user, '_is_mock', False):
            try:
                dm_content = f"## Ваш рапорт на увольнение был **отклонён** сотрудником {interaction.user.mention}."
                if rejection_reason:
                    dm_content += f"\n**Причина отказа:** {rejection_reason}"
                await target_user.send(dm_content)
            except discord.Forbidden:
                pass  # User has DMs disabled
    
    async def _handle_rejection_error(self, interaction: discord.Interaction, error: Exception):
        """Handle errors in rejection process with fallback responses."""
        print(f"Error in dismissal rejection: {error}")
        try:
            await interaction.followup.send(
                f"Произошла ошибка при обработке отказа: {error}", 
                ephemeral=True
            )
        except:
            try:
                await interaction.response.send_message(
                    f"Произошла ошибка при обработке отказа: {error}", 
                    ephemeral=True
                )
            except:
                pass

    def _format_dismissal_nickname(self, current_name: str) -> str:
        """Format nickname for dismissed user: 'Уволен | Имя Фамилия'."""
        # Extract name part based on different nickname formats
        name_part = None
        
        # Format 1: "{Подразделение} | Имя Фамилия"
        if " | " in current_name:
            name_part = current_name.split(" | ", 1)[1]
        # Format 2: "[Должность] Имя Фамилия" or "!![Должность] Имя Фамилия" or "![Должность] Имя Фамилия"
        elif "]" in current_name:
            # Find the last occurrence of "]" to handle nested brackets
            bracket_end = current_name.rfind("]")
            if bracket_end != -1:
                # Extract everything after "]", removing leading exclamation marks and spaces
                after_bracket = current_name[bracket_end + 1:]
                # Remove leading exclamation marks and spaces
                name_part = re.sub(r'^[!\s]+', '', after_bracket).strip()
        
        # If no specific format found, use the display name as is
        if not name_part or not name_part.strip():
            name_part = current_name
        
        # Smart nickname formatting - check length
        full_nickname = f"Уволен | {name_part}"
        
        # Discord nickname limit is 32 characters
        if len(full_nickname) <= 32:
            return full_nickname
        else:            # Format as "Уволен | И. Фамилия" if too long
            name_parts = name_part.split()
            if len(name_parts) >= 2:
                first_name_initial = name_parts[0][0] if name_parts[0] else "И"
                last_name = name_parts[-1]
                return f"Уволен | {first_name_initial}. {last_name}"
            else:
                # Fallback if name format is unusual
                return f"Уволен | {name_part[:23]}"  # Truncate to fit ("Уволен | " is 9 chars)
    
    async def _show_processing_state_for_interaction(self, interaction: discord.Interaction):
        """Show processing UI state for regular interaction."""
        processing_view = ui.View(timeout=None)
        processing_button = ui.Button(label=DismissalConstants.PROCESSING_LABEL, style=discord.ButtonStyle.gray, disabled=True)
        processing_view.add_item(processing_button)
        
        embed = interaction.message.embeds[0]
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=processing_view)
    
    async def _show_processing_state_for_original_interaction(self, original_interaction: discord.Interaction, embed):
        """Show processing UI state for original interaction with custom embed."""
        processing_view = ui.View(timeout=None)
        processing_button = ui.Button(label=DismissalConstants.PROCESSING_LABEL, style=discord.ButtonStyle.gray, disabled=True)
        processing_view.add_item(processing_button)
        
        await original_interaction.followup.edit_message(original_interaction.message.id, embed=embed, view=processing_view)
    
    async def _show_processing_state(self, interaction: discord.Interaction):
        """Show processing UI state (generic method for compatibility)."""
        await self._show_processing_state_for_interaction(interaction)
    
    async def _handle_moderator_authorization(self, interaction, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server):
        """Handle moderator authorization flow and return signed_by_name if successful."""
        from utils.moderator_auth import ModeratorAuthHandler
        
        # Use unified authorization handler
        signed_by_name = await ModeratorAuthHandler.handle_moderator_authorization(
            interaction,
            self._continue_dismissal_with_manual_auth,
            target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server
        )        
        if signed_by_name:
            # Show processing state with just button change
            await self._show_processing_state_for_interaction(interaction)
        
        return signed_by_name
    async def _handle_automatic_report_static(self, interaction, is_automatic_report, form_data, target_user, user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server, signed_by_name):
        """Handle static input for automatic reports and return True if modal was shown."""
        if is_automatic_report and not form_data.get('static'):
            print(f"Automatic dismissal detected, requesting static from moderator")
            
            from .modals import StaticRequestModal
            
            # Show modal to request static
            static_modal = StaticRequestModal(
                self._continue_dismissal_with_static_after_auth,
                interaction, target_user, form_data,
                user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server, signed_by_name
            )
            
            # For automatic static request, we need to handle the case where interaction was already deferred
            # In this case, we need to create a fresh interaction response
            try:
                if not interaction.response.is_done():
                    # Fresh interaction - can send modal directly
                    await interaction.response.send_modal(static_modal)
                    print(f"✅ Static modal sent via fresh interaction response")
                else:
                    # Interaction already processed (deferred) - we need to send modal differently
                    # Since we can't send modal via followup, we need to edit the message to show a new button
                    # that will trigger the static modal when clicked
                    print(f"⚠️ Interaction already processed, cannot send modal via followup")
                    print(f"Creating new view with static input button...")
                    
                    # Create a temporary view with a static input button
                    static_input_view = ui.View(timeout=300)  # 5 minute timeout
                    static_button = ui.Button(
                        label="📝 Ввести статик", 
                        style=discord.ButtonStyle.primary,
                        custom_id="static_input_button"
                    )
                    
                    async def static_button_callback(button_interaction):
                        await button_interaction.response.send_modal(static_modal)
                    
                    static_button.callback = static_button_callback
                    static_input_view.add_item(static_button)
                    
                    # Update the message with the new view
                    embed = interaction.message.embeds[0]
                    await interaction.followup.edit_message(
                        interaction.message.id, 
                        embed=embed, 
                        view=static_input_view
                    )
                    
                    # Send instruction message
                    await interaction.followup.send(
                        "📋 **Требуется ввод статика для автоматического рапорта**\n\n"
                        "🔽 Нажмите кнопку **\"📝 Ввести статик\"** ниже для ввода статика покинувшего сервер пользователя.",
                        ephemeral=True
                    )
                
                return True  # Modal handling initiated
                
            except Exception as modal_error:
                print(f"❌ Error handling static modal: {modal_error}")
                # Fallback: ask user to try again
                await interaction.followup.send(
                    "❌ Не удалось открыть форму для ввода статика.\n"
                    "🔄 Пожалуйста, нажмите кнопку \"✅ Одобрить\" еще раз.",
                    ephemeral=True
                )
                return True
        
        return False  # No modal needed
    
    async def _finalize_approval_processing(self, interaction, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, signed_by_name, config, user_has_left_server):
        """Finalize the approval processing."""
        # Show processing state with button change
        await self._show_processing_state_for_interaction(interaction)
        
        # Small delay to show processing state
        await asyncio.sleep(0.5)
        
        # Continue with processing
        await self._process_dismissal_approval(
            interaction, target_user, form_data,
            user_rank_for_audit, user_unit_for_audit,
            current_time, signed_by_name, config, override_moderator_info=None, user_has_left_server=user_has_left_server
        )
    
    async def _handle_approval_error(self, interaction: discord.Interaction, error: Exception):
        """Handle errors in approval process with fallback responses."""
        print(f"Error in dismissal approval: {error}")
        try:            await interaction.followup.send(
                DismissalConstants.PROCESSING_ERROR_APPROVAL,
                ephemeral=True
            )
        except:
            try:
                await interaction.response.send_message(
                    DismissalConstants.PROCESSING_ERROR_APPROVAL,
                    ephemeral=True
                )
            except:
                pass

    async def _request_rejection_reason(self, interaction, target_user):
        """Request rejection reason from moderator via modal."""
        try:
            from .modals import RejectionReasonModal
            
            # Store the original message for later reference
            original_message = interaction.message            # Create modal to request rejection reason
            reason_modal = RejectionReasonModal(
                self._finalize_rejection_with_reason,
                original_message,
                None  # No view instance for regular dismissals
            )
            
            # If interaction hasn't been responded to yet, send modal
            if not interaction.response.is_done():
                await interaction.response.send_modal(reason_modal)
            else:
                # Fallback case - ask user to try again
                await interaction.followup.send(
                    "Пожалуйста, нажмите кнопку 'Отказать' еще раз для ввода причины отказа.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error in _request_rejection_reason: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при запросе причины отказа.",
                ephemeral=True
            )

    async def _finalize_rejection_with_reason(self, interaction, rejection_reason, target_user, original_message):
        """Finalize the rejection process with the provided reason."""
        try:
            # Respond to the modal interaction first
            await interaction.response.defer()
            
            # Show processing state
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(label=DismissalConstants.PROCESSING_LABEL, style=discord.ButtonStyle.gray, disabled=True)
            processing_view.add_item(processing_button)
            await original_message.edit(view=processing_view)
            
            # Small delay to show processing state
            await asyncio.sleep(0.5)
            
            embed = original_message.embeds[0]
            embed.color = discord.Color.red()
            
            embed.add_field(
                name="Обработано", 
                value=f"Сотрудник: {interaction.user.mention}\nВремя: {discord.utils.format_dt(discord.utils.utcnow(), 'F')}", 
                inline=False
            )
            
            embed.add_field(
                name="Причина отказа",
                value=rejection_reason,
                inline=False
            )
            
            # Create new view with only "Rejected" button (disabled)
            rejected_view = ui.View(timeout=None)
            rejected_button = ui.Button(label=DismissalConstants.REJECTED_LABEL, style=discord.ButtonStyle.red, disabled=True)
            rejected_view.add_item(rejected_button)
            
            await original_message.edit(content="", embed=embed, view=rejected_view)
            
            # Send DM to the user if they're still on the server
            if target_user and not getattr(target_user, '_is_mock', False):
                try:
                    await target_user.send(
                        f"## ❌ Ваш рапорт на увольнение был **отклонён**\n"
                        f"> **Сотрудник:** {interaction.user.mention}\n"
                        f"> **Причина отказа:** {rejection_reason}"
                    )
                except discord.Forbidden:
                    pass  # User has DMs disabled
            
        except Exception as e:
            print(f"Error in _finalize_rejection_with_reason: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при финализации отказа.",
                ephemeral=True
            )


class AutomaticDismissalApprovalView(ui.View):
    """
    Special view for automatic dismissal reports with three buttons: Approve, Reject, Edit
    
    This view is persistent (survives bot restarts) due to:
    - timeout=None (never expires)
    - custom_id on all buttons
    - Registration in app.py as persistent view
    """
    
    def __init__(self, user_id=None):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, custom_id="auto_approve_dismissal")
    async def approve_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle approval of automatic dismissal report"""
        try:
            # Check moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="У вас нет прав для рассмотрения автоматических рапортов на увольнение.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
              # Extract user information from embed description
            target_user = await self._extract_target_user_from_embed(interaction)
            
            if not target_user:
                await interaction.response.send_message(
                    "❌ Не удалось извлечь информацию о пользователе из рапорта.",
                    ephemeral=True
                )
                return
            
            # Proceed with standard dismissal approval process
            await self._process_automatic_dismissal_approval(interaction, target_user, config)
            
        except Exception as e:
            print(f"Error in automatic dismissal approval: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при одобрении автоматического рапорта.",
                ephemeral=True
            )
    
    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, custom_id="auto_reject_dismissal")
    async def reject_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle rejection of automatic dismissal report"""
        try:
            # Check moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="У вас нет прав для рассмотрения автоматических рапортов на увольнение.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
              # Request rejection reason
            from .modals import RejectionReasonModal
            modal = RejectionReasonModal(None, interaction.message, self)  # Pass message and view instead of callback
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Error in automatic dismissal rejection: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отклонении автоматического рапорта.",
                ephemeral=True
            )
    
    @discord.ui.button(label="✏️ Изменить", style=discord.ButtonStyle.secondary, custom_id="auto_edit_dismissal")
    async def edit_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle editing of automatic dismissal report data"""
        try:
            # Check moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                embed = discord.Embed(
                    title="❌ Недостаточно прав",
                    description="У вас нет прав для редактирования автоматических рапортов на увольнение.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
              # Extract current data from embed
            current_data = self._extract_current_data_from_embed(interaction)
            
            # Show edit modal
            from .modals import AutomaticDismissalEditModal
            modal = AutomaticDismissalEditModal(current_data, interaction.message, self)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Error in automatic dismissal edit: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при редактировании автоматического рапорта.",
                ephemeral=True
            )
    
    async def _extract_target_user_from_embed(self, interaction):
        """Extract target user from embed description (mention)"""
        try:
            embed = interaction.message.embeds[0]
            description = embed.description
            
            # Extract user ID from mention in description
            import re
            user_mention_pattern = r'<@(\d+)>'
            match = re.search(user_mention_pattern, description)
            if match:
                user_id = int(match.group(1))
                # Try to get member object (may be None if user left)
                target_user = interaction.guild.get_member(user_id)
                
                if not target_user:
                    # Create mock user for users who left
                    class MockUser:
                        def __init__(self, user_id, name):
                            self.id = user_id
                            self.name = name
                            self.display_name = name
                            self.mention = f"<@{user_id}>"
                            self.roles = []
                            self._is_mock = True
                        
                        def __str__(self):
                            return self.display_name
                    
                    target_user = MockUser(user_id, "Покинувший пользователь")
                
                return target_user
            
            return None
            
        except Exception as e:
            print(f"Error extracting target user: {e}")
            return None
    
    def _extract_current_data_from_embed(self, interaction):
        """Extract current data from embed fields"""
        try:
            embed = interaction.message.embeds[0]
            data = {}
            
            for field in embed.fields:
                if field.name == "Имя Фамилия":
                    data['name'] = field.value
                elif field.name == "Статик":
                    data['static'] = field.value
                elif field.name == "Подразделение":
                    data['department'] = field.value
                elif field.name == "Воинское звание":
                    data['rank'] = field.value
            
            return data
            
        except Exception as e:
            print(f"Error extracting current data: {e}")
            return {}
    
    async def _process_automatic_dismissal_approval(self, interaction, target_user, config):
        """Process automatic dismissal approval (similar to standard approval but simplified)"""
        try:
            # Show processing state
            await interaction.response.defer()
              # Extract form data from embed
            embed = interaction.message.embeds[0]
            form_data = {}
            
            for field in embed.fields:
                if field.name == "Имя Фамилия":
                    form_data['name'] = field.value
                elif field.name == "Статик":
                    form_data['static'] = field.value
                elif field.name == "Подразделение":
                    form_data['department'] = field.value
                elif field.name == "Воинское звание":
                    form_data['rank'] = field.value
                elif field.name == "Причина увольнения":
                    form_data['reason'] = field.value
            
            # Process standard dismissal approval
            current_time = discord.utils.utcnow()
            ping_settings = config.get('ping_settings', {})
            
            # Get user info for audit
            user_rank_for_audit = target_user and sheets_manager.get_rank_from_roles(target_user) or "Неизвестно"
            user_unit_for_audit = target_user and sheets_manager.get_department_from_roles(target_user, ping_settings) or "Неизвестно"
            
            # Process dismissal with automatic approval logic
            await self._finalize_automatic_approval(
                interaction, target_user, form_data, user_rank_for_audit, 
                user_unit_for_audit, current_time, config
            )
            
        except Exception as e:
            print(f"Error processing automatic dismissal approval: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке одобрения.",
                ephemeral=True
            )
    
    async def _finalize_automatic_approval(self, interaction, target_user, form_data, 
                                         user_rank_for_audit, user_unit_for_audit, 
                                         current_time, config):
        """Finalize automatic dismissal approval"""
        try:
            ping_settings = config.get('ping_settings', {})
            
            # Log to Google Sheets
            try:
                success = await sheets_manager.add_dismissal_record(
                    form_data=form_data,
                    dismissed_user=target_user,
                    approving_user=interaction.user,
                    dismissal_time=current_time,
                    ping_settings=ping_settings
                )
                if success:
                    print(f"Successfully logged automatic dismissal to Google Sheets")
                else:
                    print(f"Failed to log automatic dismissal to Google Sheets")
            except Exception as e:
                print(f"Error logging automatic dismissal to Google Sheets: {e}")
            
            # Remove user from personnel database
            try:
                user_id = getattr(target_user, 'id', None)
                if user_id:
                    registry_success = await UserDatabase.remove_user(user_id)
                    if not registry_success:
                        print(f"⚠️ Could not remove user from personnel registry")
            except Exception as e:
                print(f"❌ Error removing user from personnel registry: {e}")
            
            # Update embed to show approval
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
              # Add approval status field
            embed.add_field(
                name="✅ Обработано",
                value=f"**Одобрено:** {interaction.user.mention}\n**Время:** {discord.utils.format_dt(current_time, 'F')}",
                inline=False
            )
            
            # Remove buttons
            await interaction.edit_original_response(content='', embed=embed, view=None)

        except Exception as e:
            print(f"Error finalizing automatic approval: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при финализации одобрения.",
                ephemeral=True
            )
  
