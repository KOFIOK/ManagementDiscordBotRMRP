"""
Dismissal system views
Contains interactive components (buttons and views) for dismissal reports
"""

import discord
from discord import ui
import re
from datetime import datetime
from utils.config_manager import load_config, is_moderator_or_admin, can_moderate_user
from utils.google_sheets import sheets_manager


class DismissalReportButton(ui.View):
    """Simple button view for creating dismissal reports"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Отправить рапорт на увольнение", style=discord.ButtonStyle.red, custom_id="dismissal_report")
    async def dismissal_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .modals import DismissalReportModal
        await interaction.response.send_modal(DismissalReportModal())


class DismissalApprovalView(ui.View):
    """Approval/Rejection view for dismissal reports with complex processing logic"""
    
    def __init__(self, user_id=None, is_automatic=False):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.is_automatic = is_automatic  # Flag for automatic dismissal reports
    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, custom_id="approve_dismissal")
    async def approve_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:            
            # Load configuration once for the entire operation
            config = load_config()
            excluded_roles_ids = config.get('excluded_roles', [])
            ping_settings = config.get('ping_settings', {})
            
            # Check if user has moderator permissions FIRST
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для одобрения рапортов на увольнение. Только модераторы могут выполнять это действие.",
                    ephemeral=True
                )
                return
            
            print(f"User {interaction.user.display_name} found in config moderators - proceeding")
            
            # Extract target user and check if they left the server
            target_user, user_has_left_server = self._extract_target_user(interaction)
            
            # Check hierarchical moderation permissions (skip for users who left server)
            if not user_has_left_server and not can_moderate_user(interaction.user, target_user, config):
                # Determine the reason for denial
                if interaction.user.id == target_user.id:
                    reason = "Вы не можете одобрить свой собственный рапорт на увольнение."
                elif is_moderator_or_admin(target_user, config):
                    reason = "Вы не можете одобрить рапорт модератора того же или более высокого уровня."
                else:
                    reason = "У вас недостаточно прав для одобрения этого рапорта."
                
                await interaction.response.send_message(
                    f"❌ {reason}",
                    ephemeral=True
                )
                return
              # Get user data for audit notification - handle missing users gracefully
            current_time = discord.utils.utcnow()
            
            # Extract rank and department data for audit
            embed = interaction.message.embeds[0]
            user_rank_for_audit, user_unit_for_audit = self._extract_audit_data(embed, target_user, user_has_left_server, ping_settings)
            
            # Extract form data from embed fields
            form_data, is_automatic_report = self._extract_form_data(embed)
            
            # CHECK AUTHORIZATION FIRST - before any processing or defer
            try:
                # Check if moderator is authorized in system
                print(f"Checking authorization for moderator: {interaction.user.display_name}")
                auth_result = await sheets_manager.check_moderator_authorization(interaction.user)
                
                if not auth_result["found"]:
                    # Moderator not found - show modal immediately (before defer)
                    print(f"Moderator not found in system, showing authorization modal")
                    
                    from forms.moderator_auth_form import ModeratorAuthModal
                    
                    # Create modal with callback to continue processing
                    modal = ModeratorAuthModal(
                        self._continue_dismissal_with_manual_auth,
                        target_user, form_data,
                        user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server
                    )
                    
                    # Show modal immediately (this will consume the interaction response)
                    await interaction.response.send_modal(modal)
                    return  # Exit here, processing will continue in modal callback
                
                # Moderator found in system - continue normally
                print(f"Moderator authorized: {auth_result['info']}")
                signed_by_name = auth_result["info"]
                
            except Exception as e:
                print(f"❌ CRITICAL ERROR in authorization flow: {e}")
                import traceback
                traceback.print_exc()
                
                # SECURITY FIX: Do NOT continue processing on authorization errors
                await interaction.response.send_message(
                    "❌ Ошибка проверки авторизации модератора. Обратитесь к администратору.",
                    ephemeral=True
                )
                return  # DO NOT CONTINUE - return here to prevent unauthorized processing
            
            # After authorization check - handle automatic reports without static
            if is_automatic_report and not form_data.get('static'):
                print(f"Automatic dismissal detected, requesting static from moderator")
                
                from .modals import StaticRequestModal
                
                # Show modal to request static before continuing
                static_modal = StaticRequestModal(
                    self._continue_dismissal_with_static_after_auth,
                    interaction, target_user, form_data,
                    user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server, signed_by_name                )
                
                await interaction.response.send_modal(static_modal)
                return  # Processing will continue in modal callback
            
            # Now defer the interaction since we're continuing with normal processing
            await interaction.response.defer()
            
            # Immediately show "Processing..." state to give user feedback
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(label="⏳ Обрабатывается...", style=discord.ButtonStyle.gray, disabled=True)
            processing_view.add_item(processing_button)
            
            # Update the message to show processing state
            embed = interaction.message.embeds[0]
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=processing_view)            # Continue with processing using authorized moderator info
            await self._process_dismissal_approval(
                interaction, target_user, form_data,
                user_rank_for_audit, user_unit_for_audit,
                current_time, signed_by_name, config, override_moderator_info=None, user_has_left_server=user_has_left_server
            )
        except Exception as e:
            print(f"Error in dismissal approval: {e}")
            try:
                await interaction.followup.send(
                    f"Произошла ошибка при обработке одобрения: {e}", 
                    ephemeral=True
                )
            except:
                # If followup fails, try response (in case defer didn't work)
                try:
                    await interaction.response.send_message(
                        f"Произошла ошибка при обработке одобрения: {e}", 
                        ephemeral=True
                    )
                except:
                    pass
        
    @discord.ui.button(label="❌ Отказать", style=discord.ButtonStyle.red, custom_id="reject_dismissal")
    async def reject_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user has moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для отказа рапортов на увольнение. Только модераторы могут выполнять это действие.",
                    ephemeral=True
                )
                return
            
            # Defer the interaction since we're continuing with normal processing
            await interaction.response.defer()
            
            # Immediately show "Processing..." state to give user feedback
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(label="⏳ Обрабатывается...", style=discord.ButtonStyle.gray, disabled=True)
            processing_view.add_item(processing_button)
            
            # Update the message to show processing state
            embed = interaction.message.embeds[0]
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=processing_view)
              # Try to get user_id from the view, or extract from embed footer
            target_user, _ = self._extract_target_user(interaction)
              
            # Check hierarchical moderation permissions
            if target_user and not can_moderate_user(interaction.user, target_user, config):
                # Restore original buttons since permission check failed
                original_view = DismissalApprovalView(self.user_id)
                embed = interaction.message.embeds[0]  # Get current embed
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=original_view)
                  
                # Determine the reason for denial
                if interaction.user.id == target_user.id:
                    reason = "Вы не можете отклонить свой собственный рапорт на увольнение."
                elif is_moderator_or_admin(target_user, config):
                    reason = "Вы не можете отклонить рапорт модератора того же или более высокого уровня."
                else:
                    reason = "У вас недостаточно прав для отклонения этого рапорта."
                
                await interaction.followup.send(
                    f"❌ {reason}",
                    ephemeral=True
                )
                return
            
            # Update the embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            
            embed.add_field(
                name="Обработано", 
                value=f"Сотрудник: {interaction.user.mention}\nВремя: {discord.utils.format_dt(discord.utils.utcnow(), 'F')}", 
                inline=False
            )
            
            # Create new view with only "Rejected" button (disabled)
            rejected_view = ui.View(timeout=None)
            rejected_button = ui.Button(label="❌ Отказано", style=discord.ButtonStyle.red, disabled=True)
            rejected_view.add_item(rejected_button)
            
            await interaction.followup.edit_message(interaction.message.id, content="", embed=embed, view=rejected_view)
            
            # Send DM to the user if they're still on the server
            if target_user:
                try:
                    await target_user.send(
                        f"## Ваш рапорт на увольнение был **отклонён** сотрудником {interaction.user.mention}."
                    )
                except discord.Forbidden:
                    pass  # User has DMs disabled
                    
        except Exception as e:
            print(f"Error in dismissal rejection: {e}")
            try:
                await interaction.followup.send(
                    f"Произошла ошибка при обработке отказа: {e}", 
                    ephemeral=True
                )
            except:
                # If followup fails, try response (in case defer didn't work)
                try:
                    await interaction.response.send_message(
                        f"Произошла ошибка при обработке отказа: {e}", 
                        ephemeral=True
                    )
                except:
                    pass

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
                if "Отправлено:" in footer_text:
                    username = footer_text.replace("Отправлено:", "").strip()
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
                if "Отправлено:" in footer_text:
                    user_name_for_logging = footer_text.replace("Отправлено:", "").strip()
            
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
        if embed.description and "🚨 Автоматический рапорт на увольнение" in embed.description:
            is_automatic_report = True
        
        for field in embed.fields:
            if field.name == "Имя Фамилия":
                form_data['name'] = field.value
            elif field.name == "Статик":
                # Check if static is missing (automatic report)
                if "Требуется ввод" in field.value:
                    form_data['static'] = None  # Will be requested from moderator
                    is_automatic_report = True
                else:
                    form_data['static'] = field.value
            elif field.name == "Подразделение":
                form_data['department'] = field.value
            elif field.name == "Воинское звание":
                form_data['rank'] = field.value
            elif field.name == "Причина увольнения":
                form_data['reason'] = field.value
            
        return form_data, is_automatic_report
    
    def _extract_audit_data(self, embed, target_user, user_has_left_server, ping_settings):
        """Extract rank and department data for audit"""
        user_rank_for_audit = "Неизвестно"
        user_unit_for_audit = "Неизвестно"
        
        # Extract from embed fields (works for both present and absent users)
        for field in embed.fields:
            if field.name == "Воинское звание":
                user_rank_for_audit = field.value
            elif field.name == "Подразделение":
                user_unit_for_audit = field.value
        
        # If embed doesn't have the data and user is present, try to get from roles
        if (user_rank_for_audit == "Неизвестно" or user_unit_for_audit == "Неизвестно") and not user_has_left_server:
            try:
                if user_rank_for_audit == "Неизвестно":
                    role_rank = sheets_manager.get_rank_from_roles(target_user)
                    if role_rank != "Неизвестно":
                        user_rank_for_audit = role_rank
                
                if user_unit_for_audit == "Неизвестно":
                    role_unit = sheets_manager.get_department_from_roles(target_user, ping_settings)
                    if role_unit != "Неизвестно":
                        user_unit_for_audit = role_unit
            except Exception as e:
                print(f"Error getting data from roles: {e}")
        
        print(f"Audit data - User: {target_user.display_name}, Rank: {user_rank_for_audit}, Unit: {user_unit_for_audit}, Left server: {user_has_left_server}")
        
        return user_rank_for_audit, user_unit_for_audit

    async def _continue_dismissal_with_manual_auth(self, interaction, moderator_data, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server=False):
        """Continue dismissal process with manually entered moderator data."""
        try:
            # Use manually entered moderator info with full details
            signed_by_name = moderator_data['full_info']  # "Имя Фамилия | Статик"
            
            # Check if we still need to request static (for automatic reports)
            is_automatic_report = False
            if not form_data.get('static'):
                # Check if this is an automatic report by looking at the embed
                embed = interaction.message.embeds[0]
                if embed.description and "🚨 Автоматический рапорт на увольнение" in embed.description:
                    is_automatic_report = True
                
                # Also check if any field indicates static is needed
                for field in embed.fields:
                    if field.name == "Статик" and "Требуется ввод" in field.value:
                        is_automatic_report = True
                        break
            
            # If we need static, show the modal first
            if is_automatic_report and not form_data.get('static'):
                print(f"Manual auth completed, but still need static for automatic dismissal")
                
                from .modals import StaticRequestModal
                
                # Show modal to request static with already authorized moderator info
                static_modal = StaticRequestModal(
                    self._continue_dismissal_with_static_after_auth,
                    interaction, target_user, form_data,
                    user_rank_for_audit, user_unit_for_audit, current_time, user_has_left_server, signed_by_name
                )
                
                await interaction.response.send_modal(static_modal)
                return  # Processing will continue in modal callback
            
            # If we have all needed data, continue with processing
            # Show "Processing..." state to give user feedback
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(label="⏳ Обрабатывается...", style=discord.ButtonStyle.gray, disabled=True)
            processing_view.add_item(processing_button)
            
            # Update the message to show processing state
            embed = interaction.message.embeds[0]
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=processing_view)
              # Process dismissal with manual auth data
            config = load_config()  # Load config for this method
            await self._process_dismissal_approval(
                interaction, target_user, form_data,
                user_rank_for_audit, user_unit_for_audit,
                current_time, signed_by_name, config, override_moderator_info=signed_by_name, user_has_left_server=user_has_left_server
            )
        except Exception as e:
            print(f"Error in manual auth dismissal continuation: {e}")
            await interaction.followup.send("❌ Произошла ошибка при обработке данных авторизации.", ephemeral=True)

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
                    break
            
            # Show processing state
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(label="⏳ Обрабатывается...", style=discord.ButtonStyle.gray, disabled=True)
            processing_view.add_item(processing_button)
            
            # Update the message
            await original_interaction.followup.edit_message(original_interaction.message.id, embed=embed, view=processing_view)
            
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
                        name_part = target_user.display_name
                    
                    # Smart nickname formatting - check length
                    full_nickname = f"Уволен | {name_part}"
                    
                    # Discord nickname limit is 32 characters
                    if len(full_nickname) <= 32:
                        new_nickname = full_nickname
                    else:
                        # Format as "Уволен | И. Фамилия" if too long
                        name_parts = name_part.split()
                        if len(name_parts) >= 2:
                            first_name_initial = name_parts[0][0] if name_parts[0] else "И"
                            last_name = name_parts[-1]
                            new_nickname = f"Уволен | {first_name_initial}. {last_name}"
                        else:
                            # Fallback if name format is unusual
                            new_nickname = f"Уволен | {name_part[:23]}"  # Truncate to fit ("Уволен | " is 9 chars)
                    
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
            
            if not user_has_left_server:
                if roles_removed:
                    status_parts.append("✅ Роли сняты")
                if nickname_changed:
                    status_parts.append("✅ Никнейм изменён")
                if not roles_removed and not nickname_changed:
                    status_parts.append("⚠️ Роли и никнейм не изменены")
            
            embed.add_field(
                name="Обработано", 
                value="\n".join(status_parts),
                inline=False
            )
            
            # Create new view with only "Approved" button (disabled)
            approved_view = ui.View(timeout=None)
            approved_button = ui.Button(label="✅ Одобрено", style=discord.ButtonStyle.green, disabled=True)
            approved_view.add_item(approved_button)
            await interaction.followup.edit_message(interaction.message.id, content="", embed=embed, view=approved_view)
            
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
                        name_with_static = f"{form_data.get('name', 'Неизвестно')} | {form_data.get('static', '')}"
                        
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
                traceback.print_exc()            # Send DM to the user (only if they're still on the server and not a MockUser)
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
                    pass  # User has DMs disabled
            else:
                print(f"Skipping DM to {target_user.display_name} - user has left server or is MockUser")
            
        except Exception as e:
            print(f"Error in _process_dismissal_approval: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке одобрения заявки.",
                ephemeral=True
            )
