import discord
from discord import ui
import re
from datetime import datetime
from utils.config_manager import load_config, is_moderator_or_admin, can_moderate_user, has_pending_dismissal_report
from utils.google_sheets import sheets_manager

# Define the dismissal report form
class DismissalReportModal(ui.Modal, title="Рапорт на увольнение"):
    name = ui.TextInput(
        label="Имя Фамилия",
        placeholder="Введите имя и фамилию через пробел",
        min_length=3,
        max_length=50,
        required=True
    )
    
    static = ui.TextInput(
        label="Статик (123-456)",
        placeholder="Формат: 123-456",
        min_length=6,
        max_length=7,
        required=True
    )
    
    reason = ui.TextInput(
        label="Причина увольнения",
        placeholder="Не пишите 'по собственному желанию', укажите более конкретную причину увольнения.",
        style=discord.TextStyle.paragraph,
        min_length=3,
        max_length=1000,
        required=True    )
    
    def format_static(self, static_input: str) -> str:
        """
        Auto-format static number to standard format (XXX-XXX or XX-XXX).
        Accepts various input formats: 123456, 123 456, 123-456, etc.
        Returns formatted static or empty string if invalid.
        """
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        # Check if we have exactly 5 or 6 digits
        if len(digits_only) == 5:
            # Format as XX-XXX (2-3)
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            # Format as XXX-XXX (3-3)
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            # Invalid length
            return ""
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check if user already has a pending dismissal report
            config = load_config()
            dismissal_channel_id = config.get('dismissal_channel')
            
            if dismissal_channel_id:
                has_pending = await has_pending_dismissal_report(interaction.client, interaction.user.id, dismissal_channel_id)
                if has_pending:
                    await interaction.response.send_message(
                        "❌ **У вас уже есть рапорт на увольнение, который находится на рассмотрении.**\n\n"
                        "Пожалуйста, дождитесь решения по текущему рапорту, прежде чем подавать новый.\n"
                        "Это поможет избежать путаницы и ускорить обработку вашего запроса.",
                        ephemeral=True
                    )
                    return
            
            # Validate name format (должно быть 2 слова)
            name_parts = self.name.value.strip().split()
            if len(name_parts) != 2:
                await interaction.response.send_message(
                    "Ошибка: Имя и фамилия должны состоять из 2 слов, разделенных пробелом.", 
                    ephemeral=True
                )
                return
              # Auto-format and validate static
            formatted_static = self.format_static(self.static.value)
            if not formatted_static:
                await interaction.response.send_message(
                    "Ошибка: Статик должен содержать 5 или 6 цифр.\n"
                    "Примеры допустимых форматов:\n"
                    "• 123-456 или 123456\n"
                    "• 12-345 или 12345\n"
                    "• 123 456 (с пробелом)", 
                    ephemeral=True
                )
                return
            
            # Get the channel where reports should be sent
            config = load_config()
            channel_id = config.get('dismissal_channel')
            
            if not channel_id:
                await interaction.response.send_message(
                    "Ошибка: канал для рапортов не настроен. Обратитесь к администратору.", 
                    ephemeral=True
                )
                return
            
            channel = interaction.client.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Ошибка: не удалось найти канал для рапортов. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
              # Auto-determine department and rank from user's roles
            ping_settings = config.get('ping_settings', {})
            user_department = sheets_manager.get_department_from_roles(interaction.user, ping_settings)
            user_rank = sheets_manager.get_rank_from_roles(interaction.user)
            
            # Create an embed for the report
            embed = discord.Embed(
                description=f"## {interaction.user.mention} подал рапорт на увольнение!",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
              # Add fields with inline formatting for compact display
            embed.add_field(name="Имя Фамилия", value=self.name.value, inline=True)
            embed.add_field(name="Статик", value=formatted_static, inline=True)
            embed.add_field(name="Подразделение", value=user_department, inline=True)
            embed.add_field(name="Воинское звание", value=user_rank, inline=True)
            embed.add_field(name="Причина увольнения", value=self.reason.value, inline=False)
            
            embed.set_footer(text=f"Отправлено: {interaction.user.name}")
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            
            # Create view with approval/rejection buttons
            approval_view = DismissalApprovalView(interaction.user.id)
            
            # Check for ping settings and add mentions
            ping_content = ""
            ping_settings = config.get('ping_settings', {})
            if ping_settings:
                # Find user's highest department role (by position in hierarchy)
                user_department = None
                highest_position = -1
                
                for department_role_id in ping_settings.keys():
                    department_role = interaction.guild.get_role(int(department_role_id))
                    if department_role and department_role in interaction.user.roles:
                        # Check if this role is higher in hierarchy than current highest
                        if department_role.position > highest_position:
                            highest_position = department_role.position
                            user_department = department_role
                
                if user_department:
                    ping_role_ids = ping_settings.get(str(user_department.id), [])
                    ping_roles = []
                    for role_id in ping_role_ids:
                        role = interaction.guild.get_role(role_id)
                        if role:
                            ping_roles.append(role.mention)
                    
                    if ping_roles:
                        ping_content = f"-# {' '.join(ping_roles)}\n\n"
            
            # Send the report to the dismissal channel with pings
            await channel.send(content=ping_content, embed=embed, view=approval_view)
            
            await interaction.response.send_message(
                "Ваш рапорт на увольнение был успешно отправлен и будет рассмотрен.", 
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in form submission: {e}")
            await interaction.response.send_message(
                f"Произошла ошибка при отправке рапорта: {e}", 
                ephemeral=True
            )
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Modal error: {error}")
        await interaction.response.send_message(
            "Произошла ошибка при обработке формы. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
            ephemeral=True
        )

# Approval/Rejection view for dismissal reports
class DismissalApprovalView(ui.View):
    def __init__(self, user_id=None):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, custom_id="approve_dismissal")
    async def approve_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:            
            # Check if user has moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для одобрения рапортов на увольнение. Только модераторы могут выполнять это действие.",
                    ephemeral=True
                )
                return
            
            # Try to get user_id from the view, or extract from embed footer
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
            
            if not target_user:
                # Update the embed first
                embed = interaction.message.embeds[0]
                embed.color = discord.Color.orange()
                embed.add_field(
                    name="Обработано", 
                    value=f"Сотрудник: {interaction.user.mention}\nВремя: {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n⚠️ Пользователь не найден - роли не сняты", 
                    inline=False
                )
                # Create new view with only "Approved" button (disabled)
                approved_view = ui.View(timeout=None)
                approved_button = ui.Button(label="✅ Одобрено", style=discord.ButtonStyle.green, disabled=True)
                approved_view.add_item(approved_button)
                
                await interaction.followup.edit_message(interaction.message.id, content="", embed=embed, view=approved_view)
                return
              # Check hierarchical moderation permissions
            if not can_moderate_user(interaction.user, target_user, config):
                # Restore original buttons since permission check failed
                original_view = DismissalApprovalView(self.user_id)
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=original_view)
                  # Determine the reason for denial
                if interaction.user.id == target_user.id:
                    reason = "Вы не можете одобрить свой собственный рапорт на увольнение."
                elif is_moderator_or_admin(target_user, config):
                    reason = "Вы не можете одобрить рапорт модератора того же или более высокого уровня."
                else:
                    reason = "У вас недостаточно прав для одобрения этого рапорта."
                
                await interaction.followup.send(
                    f"❌ {reason}",
                    ephemeral=True
                )
                return
            
            # Extract form data from embed fields first
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
            
            # Load configuration to get excluded roles and ping settings
            config = load_config()
            excluded_roles_ids = config.get('excluded_roles', [])
            ping_settings = config.get('ping_settings', {})
            
            # Get user data BEFORE removing roles (for audit notification)
            user_rank_for_audit = sheets_manager.get_rank_from_roles(target_user)
            user_unit_for_audit = sheets_manager.get_department_from_roles(target_user, ping_settings)
            current_time = discord.utils.utcnow()            # CHECK AUTHORIZATION FIRST - before any processing or defer
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
                        user_rank_for_audit, user_unit_for_audit, current_time
                    )
                    
                    # Show modal immediately (this will consume the interaction response)
                    await interaction.response.send_modal(modal)
                    return  # Exit here, processing will continue in modal callback
                
                # Moderator found in system - continue normally
                print(f"Moderator authorized: {auth_result['info']}")
                signed_by_name = auth_result["info"]
                
            except Exception as e:
                print(f"Error in authorization flow: {e}")
                print(f"Falling back to display name")
                # Fall back to display name
                signed_by_name = interaction.user.display_name
            
            # Now defer the interaction since we're continuing with normal processing
            await interaction.response.defer()
            
            # Continue with processing using authorized moderator info
            await self._process_dismissal_approval(
                interaction, target_user, form_data,
                user_rank_for_audit, user_unit_for_audit,
                current_time, signed_by_name, override_moderator_info=None
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
        try:            # Check if user has moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для отказа рапортов на увольнение. Только модераторы могут выполнять это действие.",
                    ephemeral=True
                )
                return
            
            # First, quickly respond to avoid timeout
            await interaction.response.defer()
            
            # Immediately show "Processing..." state to give user feedback
            processing_view = ui.View(timeout=None)
            processing_button = ui.Button(label="⏳ Обрабатывается...", style=discord.ButtonStyle.gray, disabled=True)
            processing_view.add_item(processing_button)
            
            # Update the message to show processing state
            embed = interaction.message.embeds[0]
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=processing_view)
            
            # Try to get user_id from the view, or extract from embed footer
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
            except:                # If followup fails, try response (in case defer didn't work)
                try:
                    await interaction.response.send_message(
                        f"Произошла ошибка при обработке отказа: {e}", 
                        ephemeral=True
                    )
                except:
                    pass

    async def _continue_dismissal_with_manual_auth(self, interaction, moderator_data, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time):
        """Continue dismissal process with manually entered moderator data."""
        try:
            # Use manually entered moderator info with full details
            signed_by_name = moderator_data['full_info']  # "Имя Фамилия | Статик"
            
            # Process dismissal with manual auth data
            await self._process_dismissal_approval(
                interaction, target_user, form_data,
                user_rank_for_audit, user_unit_for_audit,
                current_time, signed_by_name, override_moderator_info=signed_by_name
            )
            
        except Exception as e:
            print(f"Error in manual auth dismissal continuation: {e}")
            await interaction.followup.send("❌ Произошла ошибка при обработке данных авторизации.", ephemeral=True)

    async def _process_dismissal_approval(self, interaction, target_user, form_data, user_rank_for_audit, user_unit_for_audit, current_time, signed_by_name, override_moderator_info=None):
        """Complete dismissal approval process with moderator information."""
        try:
            config = load_config()
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
            roles_to_remove = []
            for role in target_user.roles:
                if role.name != "@everyone" and role.id not in excluded_roles_ids:
                    roles_to_remove.append(role)
            
            if roles_to_remove:
                await target_user.remove_roles(*roles_to_remove, reason="Рапорт на увольнение одобрен")
            
            # Change nickname to "Уволен | Имя Фамилия"
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
                
                new_nickname = f"Уволен | {name_part}"
                await target_user.edit(nick=new_nickname, reason="Рапорт на увольнение одобрен")
            except discord.Forbidden:
                # Bot doesn't have permission to change nickname
                print(f"Cannot change nickname for {target_user.name} - insufficient permissions")
            except Exception as e:
                print(f"Error changing nickname for {target_user.name}: {e}")
            
            # Update the embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.add_field(
                name="Обработано", 
                value=f"Сотрудник: {interaction.user.mention}\nВремя: {discord.utils.format_dt(discord.utils.utcnow(), 'F')}", 
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
                        
                        # Combine name and static for "Имя Фамилия | Статик" field
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
                if static:
                    hiring_record = await sheets_manager.get_latest_hiring_record_by_static(static)
                    if hiring_record:
                        hire_date_str = str(hiring_record.get('Дата Действия', '')).strip()
                        if hire_date_str:
                            try:
                                # Parse hire date
                                hire_date = None
                                
                                # If date contains time, extract date part
                                if ' ' in hire_date_str:
                                    date_part = hire_date_str.split(' ')[0]
                                else:
                                    date_part = hire_date_str
                                  # Try different date formats
                                try:
                                    hire_date = datetime.strptime(date_part, '%d.%m.%Y')
                                except ValueError:
                                    try:
                                        hire_date = datetime.strptime(date_part, '%d-%m-%Y')
                                    except ValueError:
                                        # Try full datetime format
                                        try:
                                            hire_date = datetime.strptime(hire_date_str, '%d.%m.%Y %H:%M:%S')
                                        except ValueError:
                                            hire_date = datetime.strptime(hire_date_str, '%d-%m-%Y %H:%M:%S')
                                
                                # Calculate days difference
                                dismissal_date = current_time.replace(tzinfo=None)
                                days_difference = (dismissal_date - hire_date).days
                                
                                if days_difference < 5:
                                    print(f"Early dismissal detected: {days_difference} days of service for {form_data.get('name', 'Unknown')}")
                                    # Send to blacklist channel with audit message URL and approving user
                                    await sheets_manager.send_to_blacklist(
                                        guild=interaction.guild,
                                        form_data=form_data,
                                        days_difference=days_difference,
                                        audit_message_url=audit_message_url,
                                        approving_user=interaction.user,
                                        override_moderator_info=override_moderator_info
                                    )
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
                                        if penalty_logged:
                                            print(f"Successfully logged early dismissal penalty for {form_data.get('name', 'Unknown')}")
                                        else:
                                            print(f"Failed to log early dismissal penalty for {form_data.get('name', 'Unknown')}")
                                    except Exception as penalty_error:
                                        print(f"Error logging penalty to blacklist sheet: {penalty_error}")
                                else:
                                    print(f"Normal dismissal: {days_difference} days of service")
                            
                            except ValueError as date_error:
                                print(f"Error parsing hire date '{hire_date_str}': {date_error}")
                    else:
                        print(f"No hiring record found for static {static}")
            except Exception as e:
                print(f"Error checking for early dismissal: {e}")
            
            # Send DM to the user
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
            
        except Exception as e:
            print(f"Error in _process_dismissal_approval: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке одобрения заявки.",
                ephemeral=True
            )

# Button for dismissal report
class DismissalReportButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Отправить рапорт на увольнение", style=discord.ButtonStyle.red, custom_id="dismissal_report")
    async def dismissal_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DismissalReportModal())

# Message with button for the dismissal channel
async def send_dismissal_button_message(channel):
    embed = discord.Embed(
        title="Рапорты на увольнение",
        description="Нажмите на кнопку ниже, чтобы отправить рапорт на увольнение.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Инструкция", 
        value="1. Нажмите на кнопку и заполните открывшуюся форму\n2. Нажмите 'Отправить'\n3. Ваш рапорт будет рассматриваться в течении __24 часов__.", 
        inline=False
    )
    
    view = DismissalReportButton()
    await channel.send(embed=embed, view=view)

# Function to restore approval views for existing dismissal reports
async def restore_dismissal_approval_views(bot, channel):
    """Restore approval views for existing dismissal report messages."""
    try:
        async for message in channel.history(limit=50):
            # Check if message is from bot and has dismissal report embed
            if (message.author == bot.user and 
                message.embeds and
                message.embeds[0].description and
                "подал рапорт на увольнение!" in message.embeds[0].description):
                
                embed = message.embeds[0]
                
                # Check if report is still pending (not approved/rejected)
                # We check if there's no "Обработано" field, which means it's still pending
                status_pending = True
                for field in embed.fields:
                    if field.name == "Обработано":
                        status_pending = False
                        break
                
                if status_pending:
                    # Extract user ID from footer if possible
                    # This is a fallback since we can't perfectly restore user_id
                    # but the view will still work for approval/rejection
                    view = DismissalApprovalView(user_id=None)
                      # Edit message to restore the view
                    try:
                        await message.edit(view=view)
                        print(f"Restored approval view for dismissal report message {message.id}")
                    except discord.NotFound:
                        continue
                    except Exception as e:
                        print(f"Error restoring view for message {message.id}: {e}")
                        
    except Exception as e:
        print(f"Error restoring dismissal approval views: {e}")
