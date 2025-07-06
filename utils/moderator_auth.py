"""
Unified moderator authorization system

This module provides a centralized system for moderator authorization
that can be used by both dismissal reports and role assignment systems.
"""

import discord
from discord import ui
from utils.google_sheets import sheets_manager
from utils.config_manager import load_config


async def is_moderator(user_id: int) -> bool:
    """
    Check if user is a moderator based on config
    Returns True if user is in moderators list or has moderator role
    """
    try:
        config = load_config()
        moderators = config.get('moderators', {'users': [], 'roles': []})
        
        # Check if user ID is in moderators list
        if user_id in moderators.get('users', []):
            return True
        
        return False
        
    except Exception as e:
        print(f"Error checking moderator status for user {user_id}: {e}")
        return False


async def is_administrator(user_id: int) -> bool:
    """
    Check if user is an administrator based on config
    Returns True if user is in administrators list or has administrator role
    """
    try:
        config = load_config()
        administrators = config.get('administrators', {'users': [], 'roles': []})
        
        # Check if user ID is in administrators list
        if user_id in administrators.get('users', []):
            return True
        
        return False
        
    except Exception as e:
        print(f"Error checking administrator status for user {user_id}: {e}")
        return False


async def has_moderator_permissions(user: discord.Member, guild: discord.Guild) -> bool:
    """
    Check if user has moderator permissions
    Returns True if user is a moderator based on roles or config
    """
    try:
        config = load_config()
        moderators = config.get('moderators', {'users': [], 'roles': []})
        
        # Check if user ID is in moderators list
        if user.id in moderators.get('users', []):
            return True
        
        # Check if user has any of the moderator roles
        moderator_role_ids = moderators.get('roles', [])
        for role in user.roles:
            if role.id in moderator_role_ids:
                return True
        
        # Check if user has administrator permissions
        if user.guild_permissions.administrator:
            return True
        
        if has_admin_permissions(user, guild):
            return True
        
        return False
        
    except Exception as e:
        print(f"Error checking moderator permissions for user {user.id}: {e}")
        return False


async def has_admin_permissions(user: discord.Member, guild: discord.Guild) -> bool:
    """
    Check if user has admin permissions
    Returns True if user is an administrator based on roles or config
    """
    try:
        config = load_config()
        administrators = config.get('administrators', {'users': [], 'roles': []})
        
        # Check if user ID is in administrators list
        if user.id in administrators.get('users', []):
            return True
        
        # Check if user has any of the administrator roles
        admin_role_ids = administrators.get('roles', [])
        for role in user.roles:
            if role.id in admin_role_ids:
                return True
        
        # Check if user has administrator permissions
        if user.guild_permissions.administrator:
            return True
        
        return False
        
    except Exception as e:
        print(f"Error checking admin permissions for user {user.id}: {e}")
        return False


class ModeratorAuthModal(ui.Modal, title="Регистрация модератора в системе"):
    """Universal modal for moderator registration/authorization"""
    
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
        placeholder="~Комиссар. Без должности? - укажите звание",
        min_length=2,
        max_length=50,
        required=True
    )
    
    def __init__(self, callback_func, *callback_args, **callback_kwargs):
        """
        Initialize the modal with callback function and arguments
        
        Args:
            callback_func: Function to call after successful authorization
            *callback_args: Positional arguments to pass to callback
            **callback_kwargs: Keyword arguments to pass to callback
        """
        super().__init__()
        self.callback_func = callback_func
        self.callback_args = callback_args
        self.callback_kwargs = callback_kwargs
    
    def format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        import re
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            import re
            
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
                'discord_id': interaction.user.id,
                'discord_name': interaction.user.display_name,
                'full_info': f"{name_value} | {formatted_static}"  # Format for signing
            }
            
            # Send processing message
            await interaction.response.send_message(
                "✅ **Данные получены**\n"
                "Регистрируем модератора и продолжаем обработку...",
                ephemeral=True
            )
              # Register moderator in Google Sheets
            success = await sheets_manager.register_moderator(moderator_data, interaction.user)
            
            if success:
                signed_by_name = moderator_data['full_info']  # Use full_info for signing
                print(f"✅ Successfully registered moderator: {signed_by_name}")
                
                # Continue with the callback process
                if self.callback_func:
                    await self.callback_func(
                        interaction, 
                        moderator_data,  # Pass full moderator_data instead of just signed_by_name
                        *self.callback_args, 
                        **self.callback_kwargs
                    )
                    
            else:
                await interaction.followup.send(
                    "❌ Не удалось зарегистрировать модератора в системе. Попробуйте позже.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Error in ModeratorAuthModal: {e}")
            import traceback
            traceback.print_exc()
            
            await interaction.followup.send(
                "❌ Произошла ошибка при регистрации модератора.",
                ephemeral=True
            )
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"ModeratorAuthModal error: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Произошла ошибка при авторизации модератора. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Произошла ошибка при авторизации модератора. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
                    ephemeral=True
                )
        except discord.NotFound:
            print(f"⚠️ Could not send error message to {interaction.user.name} - interaction expired")
        except Exception as send_error:
            print(f"⚠️ Error sending error message to {interaction.user.name}: {send_error}")


class ModeratorAuthHandler:
    """Centralized handler for moderator authorization logic"""
    
    @staticmethod
    async def handle_moderator_authorization(interaction, callback_func, *callback_args, **callback_kwargs):
        """
        Handle moderator authorization flow and return signed_by_name if successful.
        
        Args:
            interaction: Discord interaction object
            callback_func: Function to call after successful authorization
            *callback_args: Positional arguments to pass to callback
            **callback_kwargs: Keyword arguments to pass to callback
            
        Returns:
            str or None: signed_by_name if authorization was successful, None if modal was shown
        """
        try:
            print(f"🔍 Checking moderator authorization for user: {interaction.user.name} (ID: {interaction.user.id})")
            
            # Check moderator authorization
            auth_result = await sheets_manager.check_moderator_authorization(interaction.user)
            print(f"🔍 Authorization result: {auth_result}")
            
            if not auth_result["found"]:
                print(f"❌ Moderator {interaction.user.name} not found in Google Sheets, showing auth modal")
                
                # Show manual auth modal
                auth_modal = ModeratorAuthModal(
                    callback_func,
                    *callback_args,
                    **callback_kwargs
                )
                
                try:
                    await interaction.response.send_modal(auth_modal)
                except discord.NotFound:
                    print(f"⚠️ Interaction expired for {interaction.user.name}, cannot send modal")
                    return None
                except Exception as modal_error:
                    print(f"⚠️ Error sending modal to {interaction.user.name}: {modal_error}")
                    return None
                    
                return None  # Processing will continue in modal callback
            else:
                print(f"✅ Moderator {interaction.user.name} found in Google Sheets: {auth_result['info']}")
                # Show processing state and continue
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer()
                except discord.NotFound:
                    print(f"⚠️ Interaction expired for {interaction.user.name}, continuing without defer")
                except Exception as defer_error:
                    print(f"⚠️ Error deferring interaction for {interaction.user.name}: {defer_error}")
                
                signed_by_name = auth_result["info"]
                return signed_by_name
                
        except Exception as e:
            print(f"❌ Error in moderator authorization: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при проверке авторизации модератора.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Произошла ошибка при проверке авторизации модератора.",
                        ephemeral=True
                    )
            except discord.NotFound:
                print(f"⚠️ Could not send error message to {interaction.user.name} - interaction expired")
            except Exception as send_error:
                print(f"⚠️ Error sending error message to {interaction.user.name}: {send_error}")
            return None
    
    @staticmethod
    async def show_processing_state(interaction, title="🔄 Обработка...", description="Запрос обрабатывается, пожалуйста подождите..."):
        """Show processing state during approval/dismissal"""
        try:
            # Create a temporary embed showing processing state
            processing_embed = discord.Embed(
                title=title,
                description=description,
                color=discord.Color.blue()
            )
            
            # Create a view without buttons to show processing state
            processing_view = ui.View()
            
            await interaction.edit_original_response(embed=processing_embed, view=processing_view)
            
        except Exception as e:
            print(f"Warning: Could not show processing state: {e}")
            # Don't raise exception, it's not critical
