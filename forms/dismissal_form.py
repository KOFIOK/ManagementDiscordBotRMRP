import discord
from discord import ui
import re
from utils.config_manager import load_config
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
        label="Статик (6 цифр, 123-456)",
        placeholder="Формат: 123-456",
        min_length=6,
        max_length=7,
        required=True
    )
    
    reason = ui.TextInput(
        label="Причина увольнения",
        placeholder="Укажите причину увольнения...",
        style=discord.TextStyle.paragraph,
        min_length=3,
        max_length=1000,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate name format (должно быть 2 слова)
            name_parts = self.name.value.strip().split()
            if len(name_parts) != 2:
                await interaction.response.send_message(
                    "Ошибка: Имя и фамилия должны состоять из 2 слов, разделенных пробелом.", 
                    ephemeral=True
                )
                return
            
            # Validate static format (5 цифр: 12-345)
            if not re.match(r'^\d{2}-\d{3}$|^\d{3}-\d{3}$', self.static.value):
                await interaction.response.send_message(
                    "Ошибка: Статик должен быть в формате 123-456 (3 цифры, тире, 3 цифры).", 
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
            
            # Create an embed for the report
            embed = discord.Embed(
                description=f"## {interaction.user.mention} подал рапорт на увольнение!",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Имя Фамилия", value=self.name.value, inline=False)
            embed.add_field(name="Статик", value=self.static.value, inline=False)
            embed.add_field(name="Причина", value=self.reason.value, inline=False)
            
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
                
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=approved_view)
                return
            
            # Load configuration to get excluded roles and ping settings
            config = load_config()
            excluded_roles_ids = config.get('excluded_roles', [])
            ping_settings = config.get('ping_settings', {})
            
            # Extract form data from embed fields
            embed = interaction.message.embeds[0]
            form_data = {}
            
            for field in embed.fields:
                if field.name == "Имя Фамилия":
                    form_data['name'] = field.value
                elif field.name == "Статик":
                    form_data['static'] = field.value
                elif field.name == "Причина":
                    form_data['reason'] = field.value
            
            # Log to Google Sheets BEFORE removing roles (to capture rank and department correctly)
            try:
                current_time = discord.utils.utcnow()
                success = await sheets_manager.add_dismissal_record(
                    form_data=form_data,
                    dismissed_user=target_user,
                    approving_user=interaction.user,
                    dismissal_time=current_time,
                    ping_settings=ping_settings
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
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=approved_view)
            
            # Send notification to audit channel
            try:
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        # Create audit notification embed
                        audit_embed = discord.Embed(
                            title="🔄 Кадровый аудит - Увольнение одобрено",
                            color=discord.Color.green(),
                            timestamp=discord.utils.utcnow()
                        )
                        
                        # Get user rank from roles (before they were removed, we need to reconstruct)
                        user_rank = "Неизвестно"
                        if roles_to_remove:
                            # Find rank-like role (usually contains военные звания)
                            for role in roles_to_remove:
                                if any(rank_word in role.name.lower() for rank_word in 
                                      ["рядовой", "ефрейтор", "младший", "сержант", "старший", "старшина", 
                                       "прапорщик", "старший прапорщик", "лейтенант", "старший лейтенант", 
                                       "капитан", "майор", "подполковник", "полковник", "генерал"]):
                                    user_rank = role.name
                                    break
                        
                        # Get unit from roles (department/unit)
                        user_unit = "Неизвестно"
                        if roles_to_remove:
                            # Find unit-like role (usually the longest non-rank role)
                            for role in roles_to_remove:
                                if not any(rank_word in role.name.lower() for rank_word in 
                                          ["рядовой", "ефрейтор", "младший", "сержант", "старший", "старшина", 
                                           "прапорщик", "старший прапорщик", "лейтенант", "старший лейтенант", 
                                           "капитан", "майор", "подполковник", "полковник", "генерал"]):
                                    if len(role.name) > len(user_unit) or user_unit == "Неизвестно":
                                        user_unit = role.name
                        
                        # Set fields for audit notification
                        audit_embed.add_field(name="Подписал", value=interaction.user.mention, inline=True)
                        audit_embed.add_field(name="Полный тег", value=f"{target_user.mention} ({target_user})", inline=True)
                        audit_embed.add_field(name="Действие", value="Увольнение", inline=True)
                        audit_embed.add_field(name="Причина", value=form_data.get('reason', 'Не указана'), inline=False)
                        audit_embed.add_field(name="Дата действия", value=discord.utils.format_dt(discord.utils.utcnow(), 'F'), inline=True)
                        audit_embed.add_field(name="Подразделение", value=user_unit, inline=True)
                        audit_embed.add_field(name="Звание", value=user_rank, inline=True)
                        
                        # Set thumbnail to user's avatar
                        audit_embed.set_thumbnail(url=target_user.display_avatar.url)
                        
                        # Set footer
                        audit_embed.set_footer(text="Система кадрового аудита ВС РФ")
                        
                        await audit_channel.send(embed=audit_embed)
                        print(f"Sent audit notification for dismissal of {target_user.display_name}")
                    else:
                        print(f"Audit channel not found: {audit_channel_id}")
                else:
                    print("Audit channel ID not configured")
            except Exception as e:
                print(f"Error sending audit notification: {e}")
            
            # Send DM to the user
            try:
                await target_user.send(
                    f"Ваш рапорт на увольнение был **одобрен** сотрудником {interaction.user.mention}."
                )
            except discord.Forbidden:
                pass  # User has DMs disabled
                    
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
                        ephemeral=True                    )
                except:
                    pass
    
    @discord.ui.button(label="❌ Отказать", style=discord.ButtonStyle.red, custom_id="reject_dismissal")
    async def reject_dismissal(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
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
            
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=rejected_view)
            
            # Send DM to the user if they're still on the server
            if target_user:
                try:
                    await target_user.send(
                        f"Ваш рапорт на увольнение был **отклонён** сотрудником {interaction.user.mention}."
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
        value="1. Нажмите на кнопку\n2. Заполните открывшуюся форму\n3. Нажмите 'Отправить'", 
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
