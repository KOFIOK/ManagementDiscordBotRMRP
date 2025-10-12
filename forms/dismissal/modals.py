"""
Dismissal system modals
Contains modal forms for dismissal reports and static input
"""

import discord
from discord import ui
import re
from utils.config_manager import load_config, has_pending_dismissal_report
from utils.rank_utils import get_rank_from_roles_postgresql
from utils.user_cache import get_cached_user_info


class SimplifiedDismissalModal(ui.Modal):
    """Simplified modal for dismissal reports with auto-filled data"""
    
    def __init__(self, prefilled_name: str = "", prefilled_static: str = "", dismissal_reason: str = ""):
        super().__init__(title=f"Рапорт на увольнение - {dismissal_reason}")
        self.dismissal_reason = dismissal_reason
        
        # Create text inputs with prefilled data
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Введите полное имя",
            default=prefilled_name,
            min_length=1,
            max_length=100,
            required=True
        )
        
        self.static_input = ui.TextInput(
            label="Статик", 
            placeholder="123-456 или 12-345",
            default=prefilled_static,
            min_length=5,
            max_length=7,
            required=True
        )
        
        # Add inputs to modal
        self.add_item(self.name_input)
        self.add_item(self.static_input)
    
    @classmethod
    async def create_with_user_data(cls, user_discord_id: int, dismissal_reason: str):
        """Create modal with auto-filled user data from PersonnelManager"""
        prefilled_name = ""
        prefilled_static = ""
        
        try:
            # Get user data from PersonnelManager
            from utils.database_manager import PersonnelManager
            pm = PersonnelManager()
            user_info = await pm.get_personnel_summary(user_discord_id)
            
            if user_info:
                prefilled_name = user_info.get('full_name', '')
                prefilled_static = user_info.get('static', '')
            else:
                print(f"⚠️ No data found in PersonnelManager for user {user_discord_id}")
                
        except Exception as e:
            print(f"❌ Error getting user data for auto-fill: {e}")
        
        return cls(prefilled_name, prefilled_static, dismissal_reason)
    
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
        """Handle simplified dismissal report submission"""
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
            
            # Check for pending dismissal reports
            config = load_config()
            dismissal_channel_id = config.get('dismissal_channel')
            if await has_pending_dismissal_report(interaction.client, interaction.user.id, dismissal_channel_id):
                await interaction.response.send_message(
                    "❌ У вас уже есть pending рапорт на увольнение. Пожалуйста, дождитесь обработки предыдущего рапорта.",
                    ephemeral=True
                )
                return
            
            # Create dismissal report embed
            embed = discord.Embed(
                title="📋 Рапорт на увольнение",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Имя Фамилия", value=self.name_input.value, inline=True)
            embed.add_field(name="Статик", value=formatted_static, inline=True)
            
            # Try to get additional data from PersonnelManager
            try:
                from utils.database_manager import PersonnelManager
                pm = PersonnelManager()
                user_info = await pm.get_personnel_summary(interaction.user.id)
                
                if user_info:
                    embed.add_field(name="Воинское звание", value=user_info.get('rank', 'Неизвестно'), inline=True)
                    embed.add_field(name="Подразделение", value=user_info.get('department', 'Неизвестно'), inline=True)
                    # Должность добавляем только если она есть, не пустая и не "Не назначено"
                    position = user_info.get('position', '').strip()
                    if position and position != 'Не назначено':
                        embed.add_field(name="Должность", value=position, inline=True)
            except Exception as e:
                print(f"❌ Error getting additional user data: {e}")
            
            embed.add_field(name="Причина увольнения", value=self.dismissal_reason, inline=False)

            embed.set_footer(text=f"Отправлено: {interaction.user.display_name}")
            
            # Add dismissal footer with link to submit new applications (temporarily disabled)
            from .views import add_dismissal_footer_to_embed
            embed = add_dismissal_footer_to_embed(embed, interaction.guild.id)
            
            # Create approval view
            from .views import SimplifiedDismissalApprovalView
            approval_view = SimplifiedDismissalApprovalView(interaction.user.id)
            
            # Send to dismissal channel
            config = load_config()
            dismissal_channel_id = config.get('dismissal_channel')
            
            if dismissal_channel_id:
                dismissal_channel = interaction.guild.get_channel(dismissal_channel_id)
                if dismissal_channel:
                    # Initialize ping_content
                    ping_content = ""
                    
                    # Get ping roles using ping_manager
                    try:
                        from utils.ping_manager import ping_manager
                        ping_roles_list = ping_manager.get_ping_roles_for_user(interaction.user, 'dismissals')
                        if ping_roles_list:
                            ping_roles = [role.mention for role in ping_roles_list]
                            ping_content = f"-# {' '.join(ping_roles)}"
                    except Exception as e:
                        print(f"⚠️ Error getting ping roles: {e}")
                    
                    ping_content += f"\n-# **Новый рапорт на увольнение от {interaction.user.mention}**"
                    
                    await dismissal_channel.send(
                        content=ping_content,
                        embed=embed,
                        view=approval_view
                    )
                    
                    # Defer response to avoid "something went wrong"
                    await interaction.response.defer(ephemeral=True)
                
                else:
                    await interaction.response.send_message(
                        "❌ Канал для рапортов на увольнение не найден.",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ Канал для рапортов на увольнение не настроен.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Error in simplified dismissal submission: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отправке рапорта. Обратитесь к администратору.",
                ephemeral=True
            )


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
              # If we have original_message and view_instance, handle it directly (automatic dismissals)
            if self.original_message and self.view_instance:
                # Respond to modal interaction first
                await interaction.response.send_message(
                    "✅ Рапорт отклонен!",
                    ephemeral=True
                )
                
                # Use the proper finalization method with UI states
                await self.view_instance._finalize_automatic_rejection(interaction, reason, self.original_message)
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
                                            # Add required attributes for moderation checks
                                            self.roles = []  # Empty roles list
                                            self.guild_permissions = discord.Permissions.none()  # No permissions
                                    target_user = MockUser(user_id)
                    except Exception as e:
                        print(f"Error extracting target user for rejection: {e}")
                
                await interaction.response.defer(ephemeral=True)
                
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
            
            # Add dismissal footer with link to submit new applications (temporarily disabled)
            from .views import add_dismissal_footer_to_embed
            embed = add_dismissal_footer_to_embed(embed, interaction.guild.id)
            
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
