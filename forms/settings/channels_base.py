"""
Base classes and common components for channel configuration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal, ChannelParser, ConfigDisplayHelper


class ChannelSelectionModal(BaseSettingsModal):
    """Modal for selecting and configuring channels"""
    
    def __init__(self, config_type: str):
        self.config_type = config_type
        
        type_names = {
            "dismissal": "увольнений",
            "audit": "аудита", 
            "blacklist": "чёрного списка",
            "role_assignment": "получения ролей",
            "moderator_registration": "регистрации модераторов",
            "leave_requests": "отгулов",
            "medical_registration": "записи к врачу",
            "safe_documents": "сейф документов"
        }
        
        super().__init__(title=f"Настройка канала {type_names.get(config_type, config_type)}")
        
        self.channel_input = ui.TextInput(
            label="ID или упоминание канала",
            placeholder="Например: #канал-увольнений или 1234567890123456789",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_text = self.channel_input.value.strip()
            
            # Parse channel input
            channel = ChannelParser.parse_channel_input(channel_text, interaction.guild)
            
            if not channel:
                await self.send_error_message(
                    interaction,
                    "Канал не найден",
                    f"Канал '{channel_text}' не найден на сервере."
                )
                return
            
            if not isinstance(channel, discord.TextChannel):
                await self.send_error_message(
                    interaction,
                    "Неверный тип канала",
                    "Можно указывать только текстовые каналы."
                )
                return
            
            # Save configuration
            config = load_config()
            config[f'{self.config_type}_channel'] = channel.id
            save_config(config)
            
            # Define type names and handle button messages
            type_names = {
                "dismissal": "рапортов на увольнение",
                "audit": "кадрового аудита",
                "blacklist": "чёрного списка",
                "role_assignment": "получения ролей",
                "moderator_registration": "регистрации модераторов",
                "leave_requests": "отгулов",
                "medical_registration": "записи к врачу",
                "safe_documents": "сейф документов"
            }
            type_name = type_names.get(self.config_type, self.config_type)
              # Send appropriate button message to the channel
            button_message_added = False
            
            if self.config_type == "dismissal":
                from forms.dismissal_form import send_dismissal_button_message
                await send_dismissal_button_message(channel)
                button_message_added = True
            elif self.config_type == "role_assignment":
                from forms.role_assignment_form import send_role_assignment_button_message
                await send_role_assignment_button_message(channel)
                button_message_added = True
            elif self.config_type == "moderator_registration":
                from forms.moderator_registration import ensure_moderator_registration_message
                await ensure_moderator_registration_message(channel.guild, channel.id)
                button_message_added = True
            elif self.config_type == "leave_requests":
                from forms.leave_request_form import send_leave_request_button_message
                await send_leave_request_button_message(channel)
                button_message_added = True
            elif self.config_type == "medical_registration":
                from forms.medical_registration import send_medical_registration_message
                await send_medical_registration_message(channel)
                button_message_added = True
            elif self.config_type == "safe_documents":
                from forms.safe_documents import ensure_safe_documents_pin_message
                # Получаем бота из interaction
                bot = interaction.client
                success = await ensure_safe_documents_pin_message(bot, channel.id)
                if success:
                    button_message_added = True
                else:
                    # Если не удалось создать pin message, все равно продолжаем
                    print(f"Warning: Failed to create safe documents pin message in channel {channel.id}")
            
            success_message = f"Канал {type_name} успешно настроен на {channel.mention}!"
            if button_message_added:
                success_message += "\n\n✅ Кнопки управления добавлены в канал."
            
            await self.send_success_message(
                interaction,
                "Канал настроен",
                success_message
            )
            
        except ValueError as e:
            await self.send_error_message(
                interaction,
                "Ошибка валидации",
                f"Некорректные данные: {str(e)}"
            )
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке канала: {str(e)}"
            )
