import discord
from discord import ui
import re

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
        placeholder="Например: Комиссар. Если без должности - укажите звание",
        min_length=2,
        max_length=50,
        required=True
    )
    
    def __init__(self, callback_func, *args, **kwargs):
        """
        Initialize the modal with a callback function.
        
        Args:
            callback_func: Function to call with the result data
        """
        super().__init__()
        self.callback_func = callback_func
        self.callback_args = args
        self.callback_kwargs = kwargs
    
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
        """Handle form submission with validation and registration."""
        try:
            # Validate email format
            email_value = self.email.value.strip()
            if "@" not in email_value or "." not in email_value:
                await interaction.response.send_message(
                    "❌ **Ошибка валидации email**\n"
                    "Пожалуйста, введите корректный email адрес.\n"
                    "**Пример:** `example@gmail.com`", 
                    ephemeral=True
                )
                return
            
            # Validate name format (должно быть 2 слова)
            name_parts = self.name.value.strip().split()
            if len(name_parts) != 2:
                await interaction.response.send_message(
                    "❌ **Ошибка валидации**\n"
                    "Имя и фамилия должны состоять из 2 слов, разделенных пробелом.\n"
                    "**Пример:** `Иван Петров`", 
                    ephemeral=True
                )
                return
            
            # Auto-format and validate static
            formatted_static = self.format_static(self.static.value)
            if not formatted_static:
                await interaction.response.send_message(
                    "❌ **Ошибка валидации статика**\n"
                    "Статик должен содержать ровно 5 или 6 цифр.\n"
                    "**Примеры допустимых форматов:**\n"
                    "• `123456` → `123-456`\n"
                    "• `123-456` → `123-456`\n"
                    "• `123 456` → `123-456`\n"
                    "• `12345` → `12-345`\n"
                    "• `12-345` → `12-345`",
                    ephemeral=True
                )
                return
            
            # Validate position
            position_value = self.position.value.strip()
            if len(position_value) < 2:
                await interaction.response.send_message(
                    "❌ **Ошибка валидации должности**\n"
                    "Пожалуйста, укажите вашу должность или звание.\n"
                    "**Примеры:** `Комиссар`, `Капитан`, `Майор`",
                    ephemeral=True
                )
                return
            
            # Send processing message
            await interaction.response.send_message(
                "⏳ **Регистрируем вас в системе...**\n"
                "Пожалуйста, подождите...",
                ephemeral=True
            )
            
            # Register moderator in Google Sheets
            from utils.google_sheets import sheets_manager
            
            registration_success = await sheets_manager.register_moderator(
                email=email_value,
                name=self.name.value.strip(),
                static=formatted_static,
                position=position_value
            )
            
            if registration_success:
                # Create moderator info for callback
                moderator_data = {
                    "email": email_value,
                    "name": self.name.value.strip(),
                    "static": formatted_static,
                    "position": position_value,
                    "full_info": f"{self.name.value.strip()} | {formatted_static}"
                }                # Send success confirmation
                await interaction.followup.send(
                    f"✅ **Регистрация успешна!**\n"
                    f"📧 Email: `{email_value}`\n"
                    f"👤 Имя: `{moderator_data['name']}`\n"
                    f"🔢 Статик: `{formatted_static}`\n"
                    f"💼 Должность: `{position_value}`\n\n"
                    f"🔄 Вы зарегистрированы в системе, продолжаем обработку заявки...",
                    ephemeral=True
                )
                
                # Call the callback function with the moderator data
                if self.callback_func:
                    await self.callback_func(interaction, moderator_data, *self.callback_args, **self.callback_kwargs)
            else:
                await interaction.followup.send(
                    "❌ **Ошибка регистрации**\n"
                    "Не удалось зарегистрировать вас в системе.\n"
                    "Пожалуйста, обратитесь к администратору.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Error in ModeratorAuthModal.on_submit: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ **Ошибка при обработке данных**\n"
                        "Попробуйте еще раз или обратитесь к администратору.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ **Ошибка при обработке данных**\n"
                        "Попробуйте еще раз или обратитесь к администратору.",
                        ephemeral=True
                    )
            except:
                print(f"Could not send error message to user: {e}")
