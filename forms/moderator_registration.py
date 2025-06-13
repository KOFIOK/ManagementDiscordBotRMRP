"""
Moderator registration system

This module provides a registration interface for moderators to access the system.
"""

import discord
from discord import ui
from utils.config_manager import load_config, is_moderator_or_admin
from utils.moderator_auth import ModeratorAuthModal
from utils.google_sheets import sheets_manager


class ModeratorRegistrationView(ui.View):
    """View with registration button for moderators"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔐 Регистрация модератора", style=discord.ButtonStyle.primary, custom_id="moderator_registration")
    async def register_moderator(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle moderator registration button click"""
        try:
            # Check if user has moderator permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ **Доступ запрещён**\n"
                    "Регистрация в системе доступна только назначенным модераторам.\n"
                    "Обратитесь к администратору для получения прав модератора.",
                    ephemeral=True
                )
                return
            
            # Check if moderator is already registered
            auth_result = await sheets_manager.check_moderator_authorization(interaction.user)
            if auth_result["found"]:
                await interaction.response.send_message(
                    f"✅ **Вы уже зарегистрированы в системе**\n"
                    f"Ваши данные: {auth_result['info']}\n\n"
                    "Вы можете использовать все функции модерации.",
                    ephemeral=True
                )
                return
            
            # Show registration modal
            registration_modal = ModeratorAuthModal(
                self._handle_registration_complete,
                interaction
            )            
            await interaction.response.send_modal(registration_modal)
            
        except Exception as e:
            print(f"Error in moderator registration: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке регистрации. Попробуйте позже.",
                ephemeral=True
            )
    
    async def _handle_registration_complete(self, interaction, moderator_data, original_interaction):
        """Handle successful moderator registration"""
        try:
            # Send success message to the user
            await interaction.followup.send(
                f"✅ **Регистрация завершена успешно!**\n"
                f"Ваши данные: {moderator_data['full_info']}\n\n"
                "Теперь вы можете обрабатывать заявки на увольнение и получение ролей.",
                ephemeral=True
            )
                    
        except Exception as e:
            print(f"Error in registration completion: {e}")


def create_moderator_registration_embed():
    """Create embed for moderator registration message"""
    embed = discord.Embed(
        title="🔐 Регистрация модераторов в системе",
        description=(
            "Для работы с системой кадрового учёта модераторы должны зарегистрироваться.\n\n"
            "**Что нужно для регистрации:**\n"
            "• Email для доступа к Google Sheets\n"
            "• Имя и Фамилия вашего персонажа\n"
            "• Статик (123-456)\n"
            "• Должность (например: `Нач. по КР`).\n"
            "   *Нет должности? Напишите своё звание.*\n\n"
            "После регистрации вы получите доступ к кадровым таблицам и сможете "
            "обрабатывать заявки на увольнение и получение ролей.\n\n"
            "**⚠️ Регистрация доступна со звания Капитана.**"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="Нажмите кнопку ниже для регистрации")
    return embed


async def ensure_moderator_registration_message(guild, channel_id):
    """Проверить и создать сообщение регистрации модераторов если нужно"""
    if not channel_id:
        print("⚠️ Moderator registration channel not configured")
        return None
    
    channel = guild.get_channel(channel_id)
    if not channel:
        print(f"⚠️ Moderator registration channel not found: {channel_id}")
        return None
    
    try:
        # Поиск закреплённого сообщения
        pinned_messages = await channel.pins()
        for message in pinned_messages:
            if (message.author.id == guild.me.id and 
                message.embeds and 
                "Регистрация модераторов" in message.embeds[0].title):
                print(f"✅ Moderator registration message already exists in {channel.name}")
                return message
        
        # Создать новое сообщение
        embed = create_moderator_registration_embed()
        view = ModeratorRegistrationView()
        
        message = await channel.send(embed=embed, view=view)
        await message.pin(reason="Система регистрации модераторов")
        
        print(f"✅ Created moderator registration message in {channel.name}")
        return message
        
    except discord.Forbidden:
        print(f"❌ No permission to manage messages in {channel.name}")
        return None
    except Exception as e:
        print(f"❌ Error setting up moderator registration message: {e}")
        return None
