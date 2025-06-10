import discord
from forms.moderator_auth_form import ModeratorAuthModal

class ModeratorAuthHandler:
    """Handler for moderator authorization and manual data input."""
    
    @staticmethod
    async def send_authorization_warning(interaction: discord.Interaction):
        """Send an ephemeral warning message about authorization requirement."""
        warning_embed = discord.Embed(
            title="⚠️ Требуется авторизация",
            description=(
                "Вы не найдены в системе авторизации бота.\n"
                "Для автоматического заполнения ваших данных в аудите "
                "необходимо авторизоваться у администратора."
            ),
            color=0xffa500  # Orange color
        )
        
        warning_embed.add_field(
            name="📋 Что делать?",
            value=(
                "• Обратитесь к администратору сервера\n"
                "• Попросите добавить вас в лист 'Пользователи'\n"
                "• После добавления данные будут заполняться автоматически"
            ),
            inline=False
        )
        
        warning_embed.add_field(
            name="💡 Сейчас",
            value="Данные для записи в аудит будут запрошены вручную",
            inline=False
        )
        
        warning_embed.set_footer(
            text="Это сообщение видно только вам",
            icon_url="https://i.imgur.com/07MRSyl.png"
        )
        
        try:
            await interaction.followup.send(embed=warning_embed, ephemeral=True)
        except:
            # If followup fails, try regular send
            try:
                await interaction.response.send_message(embed=warning_embed, ephemeral=True)
            except:
                print("Failed to send authorization warning message")
    
    @staticmethod
    async def request_moderator_data(interaction: discord.Interaction, callback_func, *args, **kwargs):
        """
        Show modal to request moderator data manually.
        
        Args:
            interaction: Discord interaction
            callback_func: Function to call with the result data
            *args, **kwargs: Additional arguments to pass to callback
        """
        try:
            modal = ModeratorAuthModal(callback_func, *args, **kwargs)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Error showing moderator auth modal: {e}")
            await interaction.response.send_message(
                "❌ Ошибка при открытии формы авторизации. Попробуйте еще раз.",
                ephemeral=True
            )
    
    @staticmethod
    def format_moderator_info(name: str, static: str) -> str:
        """Format moderator info to standard 'Имя Фамилия | Статик' format."""
        return f"{name.strip()} | {static.strip()}"
    
    @staticmethod
    async def handle_moderator_auth_flow(sheets_manager, approving_user, success_callback, *args, **kwargs):
        """
        Complete flow for handling moderator authorization.
        
        Args:
            sheets_manager: GoogleSheetsManager instance
            approving_user: Discord user object
            success_callback: Function to call when authorization is complete
            *args, **kwargs: Additional arguments for callback
            
        Returns:
            dict with authorization result or None if manual input needed
        """
        try:
            # Check if moderator is authorized
            auth_result = await sheets_manager.check_moderator_authorization(approving_user)
            
            if auth_result["found"]:
                # Moderator found in system, return their info
                return {
                    "status": "found",
                    "info": auth_result["info"],
                    "manual_input": False
                }
            else:
                # Moderator not found, will need manual input
                return {
                    "status": "not_found", 
                    "info": auth_result["clean_name"],
                    "manual_input": True,
                    "callback": success_callback,
                    "callback_args": args,
                    "callback_kwargs": kwargs
                }
                
        except Exception as e:
            print(f"Error in handle_moderator_auth_flow: {e}")
            return {
                "status": "error",
                "info": approving_user.display_name,
                "manual_input": True,
                "callback": success_callback,
                "callback_args": args,
                "callback_kwargs": kwargs
            }
