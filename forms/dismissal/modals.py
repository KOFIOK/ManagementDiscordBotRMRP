"""
Dismissal system modals
Contains modal forms for dismissal reports and static input
"""

import discord
from discord import ui
import re
from utils.config_manager import load_config, has_pending_dismissal_report
from utils.google_sheets import sheets_manager
from utils.user_database import UserDatabase


class StaticRequestModal(ui.Modal, title="Укажите статик увольняемого"):
    """Modal for requesting static number when approving dismissal without static"""
    
    static_input = ui.TextInput(
        label="Статик (123-456)",
        placeholder="Введите статик покинувшего пользователя",
        min_length=5,
        max_length=7,
        required=True
    )
    
    def __init__(self, callback_func, *args, **kwargs):
        super().__init__()
        self.callback_func = callback_func
        self.callback_args = args
        self.callback_kwargs = kwargs
    
    def format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Format and validate static
            formatted_static = self.format_static(self.static_input.value)
            if not formatted_static:
                await interaction.response.send_message(
                    "❌ **Ошибка валидации статика**\n"
                    "Статик должен содержать ровно 5 или 6 цифр.\n"
                    "**Примеры:** `123456` → `123-456`, `12345` → `12-345`",
                    ephemeral=True
                )
                return
            
            # Send processing message
            await interaction.response.send_message(
                "✅ **Статик принят**\n"
                "Продолжаем обработку увольнения...",
                ephemeral=True
            )
            
            # Call the callback function with formatted static
            if self.callback_func:
                await self.callback_func(interaction, formatted_static, *self.callback_args, **self.callback_kwargs)
                
        except Exception as e:
            print(f"Error in StaticRequestModal: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке статика.",
                ephemeral=True
            )


class DismissalReportModal(ui.Modal, title="Рапорт на увольнение"):
    """Main dismissal report modal form"""
    
    def __init__(self, user_data=None):
        super().__init__()
        
        # Pre-fill name and static if user data is available
        name_value = ""
        static_value = ""
        name_placeholder = "Например: Олег Дубов"
        static_placeholder = "Например: 123-456"
        
        if user_data:
            name_value = user_data.get('full_name', '')
            static_value = user_data.get('static', '')
            if name_value:
                name_placeholder = f"Данные из реестра: {name_value}"
            if static_value:
                static_placeholder = f"Данные из реестра: {static_value}"
        
        self.name = ui.TextInput(
            label="Имя Фамилия",
            placeholder=name_placeholder,
            default=name_value,
            min_length=3,
            max_length=50,
            required=True
        )
        self.add_item(self.name)
        
        self.static = ui.TextInput(
            label="Статик (123-456)",
            placeholder=static_placeholder,
            default=static_value,
            min_length=6,
            max_length=7,
            required=True
        )
        self.add_item(self.static)
        
        self.reason = ui.TextInput(
            label="Причина увольнения",
            placeholder="ПСЖ или Перевод",
            style=discord.TextStyle.short,
            min_length=3,
            max_length=10,
            required=True
        )
        self.add_item(self.reason)
    
    @classmethod
    async def create_with_user_data(cls, user_id):
        """
        Create DismissalReportModal with auto-filled user data from database
        
        Args:
            user_id: Discord user ID
            
        Returns:
            DismissalReportModal: Modal instance with pre-filled data
        """
        try:
            # Try to get user data from personnel database
            user_data = await UserDatabase.get_user_info(user_id)
            return cls(user_data=user_data)
        except Exception as e:
            print(f"❌ Error loading user data for dismissal modal: {e}")
            # Return modal without pre-filled data if error occurs
            return cls(user_data=None)
    
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
                        "Это поможет избежать путаницы и ускорит обработку вашего запроса.",
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
            
            # Validate dismissal reason
            reason = self.reason.value.strip().upper()
            if reason not in ["ПСЖ", "ПЕРЕВОД"]:
                await interaction.response.send_message(
                    "❌ Укажите одну из причин увольнения: 'ПСЖ' (По Собственному Желанию) или 'Перевод'.",
                    ephemeral=True
                )
                return
            
            # Get the channel where reports should be sent
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
                title="🚨 Рапорт на увольнение",
                description=f"## {interaction.user.mention} подал рапорт на увольнение!",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add fields with inline formatting for compact display
            embed.add_field(name="Имя Фамилия", value=self.name.value, inline=True)
            embed.add_field(name="Статик", value=formatted_static, inline=True)
            embed.add_field(name="Подразделение", value=user_department, inline=True)
            embed.add_field(name="Воинское звание", value=user_rank, inline=True)
            embed.add_field(name="Причина увольнения", value=reason, inline=False)
            
            embed.set_footer(text=f"Отправлено: {interaction.user.name}")
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
              # Import here to avoid circular imports
            from .views import DismissalApprovalView
            
            # Create view with approval/rejection buttons
            approval_view = DismissalApprovalView(interaction.user.id)
            
            # Check for ping settings and add mentions
            ping_content = ""
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


class ModeratorAuthModal(ui.Modal, title="Регистрация модератора в системе"):
    """Modal for moderator registration when not found in 'Пользователи' sheet."""
    
    email = ui.TextInput(
        label="Email (для доступа к кадровому)",
        placeholder="example@gmail.com",
        min_length=5,
        max_length=100,
        required=True
    )
    
    name = ui.TextInput(
        label="Имя Фамилия",
        placeholder="Введите ваше имя и фамилию через пробел",
        min_length=3,
        max_length=50,
        required=True
    )
    
    static = ui.TextInput(
        label="Статик (123-456)",
        placeholder="Введите ваш статик в любом формате",
        min_length=5,
        max_length=7,
        required=True
    )
    
    position = ui.TextInput(
        label="Должность",
        placeholder="Комиссар. Если без должности - укажите звание",
        min_length=2,
        max_length=50,
        required=True
    )
    
    def __init__(self, callback_func, *args, **kwargs):
        """
        Initialize the modal with a callback function for dismissal system.
        
        Args:
            callback_func: Function to call with the result data
        """
        super().__init__()
        self.callback_func = callback_func
        self.callback_args = args
        self.callback_kwargs = kwargs
    
    def format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate inputs
            email_value = self.email.value.strip()
            name_value = self.name.value.strip()
            static_value = self.static.value.strip()
            position_value = self.position.value.strip()
            
            # Validate email format
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email_value):
                await interaction.response.send_message(
                    "❌ **Ошибка валидации email**\n"
                    "Пожалуйста, введите корректный email адрес.\n"
                    "**Пример:** `example@gmail.com`",
                    ephemeral=True
                )
                return
            
            # Validate name format (should have at least first name and last name)
            name_parts = name_value.split()
            if len(name_parts) < 2:
                await interaction.response.send_message(
                    "❌ **Ошибка валидации имени**\n"
                    "Пожалуйста, введите имя и фамилию через пробел.\n"
                    "**Пример:** `Иван Петров`",
                    ephemeral=True
                )
                return
            
            # Format and validate static
            formatted_static = self.format_static(static_value)
            if not formatted_static:
                await interaction.response.send_message(
                    "❌ **Ошибка валидации статика**\n"
                    "Статик должен содержать ровно 5 или 6 цифр.\n"
                    "**Примеры:** `123456` → `123-456`, `12345` → `12-345`",
                    ephemeral=True
                )
                return
              # Prepare moderator data
            moderator_data = {
                'email': email_value,
                'name': name_value,
                'static': formatted_static,
                'position': position_value,
                'full_info': f"{name_value} | {formatted_static}"  # Format for signing
            }
            
            print(f"ModeratorAuthModal: Calling callback with data: {moderator_data}")
            
            # First, respond to the modal interaction to avoid timeout
            await interaction.response.send_message(
                "✅ **Данные получены!**\nНачинаем обработку увольнения...",
                ephemeral=True
            )
            
            # Then call the callback function with the moderator data
            await self.callback_func(interaction, moderator_data, *self.callback_args, **self.callback_kwargs)
            
        except Exception as e:
            print(f"Error in ModeratorAuthModal.on_submit: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при обработке данных модератора. Пожалуйста, попробуйте еще раз.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Произошла ошибка при обработке данных модератора. Пожалуйста, попробуйте еще раз.",
                        ephemeral=True
                    )
            except Exception as follow_error:
                print(f"Failed to send error message: {follow_error}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"ModeratorAuthModal error: {error}")
        import traceback
        traceback.print_exc()
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Произошла ошибка при обработке формы регистрации модератора. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Произошла ошибка при обработке формы регистрации модератора. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
        except Exception as follow_error:
            print(f"Failed to send error message in on_error: {follow_error}")


class RejectionReasonModal(ui.Modal, title="Причина отказа"):
    """
    Modal for requesting rejection reason when rejecting dismissal reports
    
    This modal supports two usage patterns:
    1. Direct handling (for automatic dismissals): Pass original_message and view_instance
    2. Callback handling (for regular dismissals): Pass callback_func and original_message
    """
    
    reason_input = ui.TextInput(
        label="Введите причину отказа:",
        placeholder="Укажите причину отказа рапорта на увольнение",
        style=discord.TextStyle.paragraph,
        min_length=0,
        max_length=500,
        required=True
    )
    
    def __init__(self, callback_func, original_message=None, view_instance=None):
        super().__init__()
        self.callback_func = callback_func
        self.original_message = original_message
        self.view_instance = view_instance
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            reason = self.reason_input.value.strip()
            
            # If we have original_message and view_instance, handle it directly
            if self.original_message and self.view_instance:
                # Respond to modal interaction first
                await interaction.response.send_message(
                    "✅ Рапорт отклонен!",
                    ephemeral=True
                )
                
                # Update embed to show rejection
                embed = self.original_message.embeds[0]
                embed.color = discord.Color.red()
                
                # Add rejection status field
                embed.add_field(
                    name="❌ Обработано",
                    value=f"**Отклонено:** {interaction.user.mention}\n**Время:** {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n**Причина:** {reason}",
                    inline=False
                )
                
                # Remove buttons by setting view to None
                await self.original_message.edit(embed=embed, view=None)
                  # If we have a callback function, use it (backward compatibility for regular dismissals)
            elif self.callback_func:
                # For regular dismissals, we need to extract target_user from the original message
                target_user = None
                if self.original_message:
                    # Try to extract target user info from embed or view
                    try:
                        embed = self.original_message.embeds[0]
                        # Look for user mention in embed description
                        import re
                        user_mention_pattern = r'<@(\d+)>'
                        if embed.description:
                            match = re.search(user_mention_pattern, embed.description)
                            if match:
                                user_id = int(match.group(1))
                                # Try to get member object from guild
                                guild = interaction.guild
                                target_user = guild.get_member(user_id)
                                if not target_user:
                                    # Create mock user if user left
                                    class MockUser:
                                        def __init__(self, user_id):
                                            self.id = user_id
                                            self.display_name = "Покинувший пользователь"
                                            self._is_mock = True
                                    target_user = MockUser(user_id)
                    except Exception as e:
                        print(f"Error extracting target user for rejection: {e}")
                
                await self.callback_func(interaction, reason, target_user, self.original_message)
            else:
                # Fallback case
                await interaction.response.send_message(
                    "✅ Причина отказа получена!",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Error in RejectionReasonModal: {e}")
            # Check if we already responded to avoid errors
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Произошла ошибка при обработке причины отказа.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Произошла ошибка при обработке причины отказа.",
                    ephemeral=True
                )
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"RejectionReasonModal error: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Произошла ошибка при обработке причины отказа. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Произошла ошибка при обработке причины отказа. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
        except Exception as follow_error:
            print(f"Failed to send error message in RejectionReasonModal.on_error: {follow_error}")


class AutomaticDismissalEditModal(ui.Modal, title="Редактирование автоматического рапорта"):
    """Modal for editing automatic dismissal report data"""
    
    def __init__(self, current_data, original_message, view_instance):
        super().__init__()
        self.original_message = original_message
        self.view_instance = view_instance
        
        # Pre-fill with current data
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Олег Дубов",
            default=current_data.get('name', ''),
            min_length=3,
            max_length=50,
            required=True
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="Например: 123-456",
            default=current_data.get('static', ''),
            min_length=5,
            max_length=20,
            required=True
        )
        self.add_item(self.static_input)
        
        self.department_input = ui.TextInput(
            label="Подразделение",
            placeholder="Например: Военная Академия",
            default=current_data.get('department', ''),
            min_length=2,
            max_length=50,
            required=True
        )
        self.add_item(self.department_input)        
        self.rank_input = ui.TextInput(
            label="Воинское звание",
            placeholder="Например: Рядовой",
            default=current_data.get('rank', ''),
            min_length=2,
            max_length=30,
            required=True
        )
        self.add_item(self.rank_input)
    
    def format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return static_input.strip()  # Return as-is if can't format
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Format and validate inputs
            name = self.name_input.value.strip()
            static = self.format_static(self.static_input.value)
            department = self.department_input.value.strip()
            rank = self.rank_input.value.strip()
            
            # Validate name format (should be 2 words)
            name_parts = name.split()
            if len(name_parts) != 2:
                await interaction.response.send_message(
                    "❌ Имя и фамилия должны состоять из 2 слов, разделенных пробелом.",
                    ephemeral=True
                )
                return
            
            # Respond to modal interaction first
            await interaction.response.send_message(
                "✅ Данные успешно обновлены!",
                ephemeral=True
            )
            
            # Update the embed with new data
            embed = self.original_message.embeds[0]
            
            # Update fields in the embed
            for i, field in enumerate(embed.fields):
                if field.name == "Имя Фамилия":
                    embed.set_field_at(i, name="Имя Фамилия", value=name, inline=True)
                elif field.name == "Статик":
                    embed.set_field_at(i, name="Статик", value=static, inline=True)
                elif field.name == "Подразделение":
                    embed.set_field_at(i, name="Подразделение", value=department, inline=True)
                elif field.name == "Воинское звание":
                    embed.set_field_at(i, name="Воинское звание", value=rank, inline=True)
            
            # Add edit information to footer
            embed.set_footer(
                text=f"Отредактировано {interaction.user.display_name} • {discord.utils.format_dt(discord.utils.utcnow(), 'f')}"
            )
            
            # Update the message with new embed and keep the same view
            await self.original_message.edit(embed=embed, view=self.view_instance)
            
        except Exception as e:
            print(f"Error in AutomaticDismissalEditModal: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Произошла ошибка при обработке изменений.",
                    ephemeral=True
                )
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"AutomaticDismissalEditModal error: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Произошла ошибка при редактировании рапорта. Пожалуйста, попробуйте еще раз.",
                    ephemeral=True
                )
        except Exception as follow_error:
            print(f"Failed to send error message in AutomaticDismissalEditModal.on_error: {follow_error}")
