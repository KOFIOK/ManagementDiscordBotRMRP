import discord
from discord import ui
import re

class ModeratorAuthModal(ui.Modal, title="Авторизация модератора"):
    """Modal for manual moderator data entry when not found in 'Пользователи' sheet."""
    
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
        """Handle form submission with validation."""
        try:
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
            
            # Create moderator info
            moderator_data = {
                "name": self.name.value.strip(),
                "static": formatted_static,
                "full_info": f"{self.name.value.strip()} | {formatted_static}"
            }
            
            # Send success confirmation to user
            await interaction.response.send_message(
                f"✅ **Авторизация успешна**\n"
                f"Имя: `{moderator_data['name']}`\n"
                f"Статик: `{moderator_data['static']}`\n"
                f"Продолжаем обработку заявки...",
                ephemeral=True            )
            
            # Call the callback function with the moderator data
            if self.callback_func:
                await self.callback_func(interaction, moderator_data, *self.callback_args, **self.callback_kwargs)
                
        except Exception as e:
            print(f"Error in ModeratorAuthModal.on_submit: {e}")
            try:
                await interaction.response.send_message(
                    "❌ **Ошибка при обработке данных**\n"
                    "Попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
            except:
                # If interaction was already responded to
                await interaction.followup.send(
                    "❌ **Ошибка при обработке данных**\n"
                    "Попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
