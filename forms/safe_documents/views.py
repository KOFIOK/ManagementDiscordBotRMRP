import discord
from utils.message_manager import get_safe_documents_message
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class SafeDocumentsPinView(discord.ui.View):
    """Постоянный view для закрепленного сообщения с кнопкой подачи заявки"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="Подать заявку",
        style=discord.ButtonStyle.primary,
        custom_id="safe_documents:submit_application",
        emoji="📑"
    )
    async def submit_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка подачи заявки на безопасные документы"""
        try:
            from .modals import SafeDocumentsModal
            
            # Создаем модальное окно
            modal = SafeDocumentsModal()
            
            # Автозаполнение из кэша
            await modal.autofill_from_cache(interaction.user.id)
            
            # Показываем модальное окно
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            await interaction.response.send_message(
                get_safe_documents_message(interaction.guild.id, "approval.error_general", "❌ Произошла ошибка при открытии формы").format(str(e)),
                ephemeral=True
            )


class SafeDocumentsApplicationView(discord.ui.View):
    """View для модерации заявок на безопасные документы"""
    
    def __init__(self, application_data: dict = None, disabled: bool = False):
        super().__init__(timeout=None)
        # application_data может быть None для persistent views
        self.application_data = application_data or {}
        
        if disabled:
            # Отключаем все кнопки, если заявка уже обработана
            for item in self.children:
                item.disabled = True
    
    def _extract_application_data_from_embed(self, embed: discord.Embed) -> dict:
        """Извлечение данных заявки из embed сообщения для persistent views"""
        try:
            application_data = {}
            
            # Извлекаем данные из полей embed
            for field in embed.fields:
                if field.name == "👤 Имя Фамилия":
                    application_data['name'] = field.value if field.value != 'Не указано' else ''
                elif field.name == "📧 Почта":
                    application_data['email'] = field.value if field.value != 'Не указано' else ''
                elif field.name == "📞 Игровой телефон":
                    application_data['phone'] = field.value if field.value != 'Не указано' else ''
                elif field.name == "🎭 Статик":
                    application_data['static'] = field.value if field.value != 'Не указано' else ''
                elif field.name == "📎 Копия всех документов":
                    application_data['documents'] = field.value if field.value != 'Не указано' else ''
            
            # Извлекаем user_id из footer
            if embed.footer and embed.footer.text:
                footer_text = embed.footer.text
                if "ID: " in footer_text:
                    try:
                        user_id_str = footer_text.split("ID: ")[1].strip()
                        application_data['user_id'] = int(user_id_str)
                    except (IndexError, ValueError):
                        logger.warning("Warning: Could not extract user_id from footer: %s", footer_text)
            
            # Определяем статус из заголовка
            if embed.title:
                if "Одобрена" in embed.title:
                    application_data['status'] = 'approved'
                elif "Отклонена" in embed.title:
                    application_data['status'] = 'rejected'
                else:
                    application_data['status'] = 'pending'
            
            # Добавляем timestamp
            if embed.timestamp:
                application_data['timestamp'] = embed.timestamp.isoformat()
            
            return application_data
            
        except Exception as e:
            logger.error("Error extracting application data from embed: %s", e)
            return {}
    
    def _get_application_data(self, interaction: discord.Interaction) -> dict:
        """Получение актуальных данных заявки (из self.application_data или из embed)"""
        # Если у нас есть актуальные данные (не dummy), используем их
        if self.application_data and self.application_data.get('user_id', 0) != 0:
            return self.application_data
        
        # Иначе извлекаем данные из embed сообщения (для persistent views)
        if interaction.message and interaction.message.embeds:
            return self._extract_application_data_from_embed(interaction.message.embeds[0])
        
        return {}
    
    @discord.ui.button(
        label="Подтвердить",
        style=discord.ButtonStyle.success,
        custom_id="safe_documents:approve",
        emoji="✅"
    )
    async def approve_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка одобрения заявки"""
        try:
            # Получаем актуальные данные заявки
            application_data = self._get_application_data(interaction)
            if not application_data:
                await interaction.response.send_message(
                    get_safe_documents_message(interaction.guild.id, "approval.error_not_found", "❌ Не удалось получить данные заявки!"),
                    ephemeral=True
                )
                return
            
            from .manager import SafeDocumentsManager
            manager = SafeDocumentsManager()
            await manager.handle_approval(interaction, application_data)
            
        except Exception as e:
            await interaction.response.send_message(
                get_safe_documents_message(interaction.guild.id, "approval.error_approval_failed", "❌ Произошла ошибка при одобрении заявки").format(str(e)),
                ephemeral=True
            )
    
    @discord.ui.button(
        label="Отклонить",
        style=discord.ButtonStyle.danger,
        custom_id="safe_documents:reject",
        emoji="❌"
    )
    async def reject_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка отклонения заявки"""
        try:
            # Получаем актуальные данные заявки
            application_data = self._get_application_data(interaction)
            if not application_data:
                await interaction.response.send_message(
                    get_safe_documents_message(interaction.guild.id, "approval.error_not_found", " Не удалось получить данные заявки!"),
                    ephemeral=True
                )
                return
            
            from .modals import SafeDocumentsRejectionModal
            
            # Показываем модальное окно для ввода причины отклонения
            modal = SafeDocumentsRejectionModal(application_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            await interaction.response.send_message(
                get_safe_documents_message(interaction.guild.id, "approval.error_rejection_failed", "❌ Произошла ошибка при отклонении заявки").format(str(e)),
                ephemeral=True
            )
    
    @discord.ui.button(
        label="Редактировать",
        style=discord.ButtonStyle.secondary,
        custom_id="safe_documents:edit",
        emoji="✏️"
    )
    async def edit_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Кнопка редактирования заявки"""
        try:
            # Получаем актуальные данные заявки
            application_data = self._get_application_data(interaction)
            if not application_data:
                await interaction.response.send_message(
                    "❌ Не удалось получить данные заявки!",
                    ephemeral=True
                )
                return
            
            from .modals import SafeDocumentsEditModal
            from .manager import SafeDocumentsManager
            
            manager = SafeDocumentsManager()
            
            # Проверяем права на редактирование
            can_edit = (
                interaction.user.id == application_data.get('user_id') or  # Автор заявки
                await manager.check_moderator_permissions(interaction.user, application_data.get('department'))  # Модератор
            )
            
            if not can_edit:
                await interaction.response.send_message(
                    get_safe_documents_message(interaction.guild.id, "approval.error_no_edit_permissions", "❌ У вас нет прав для редактирования этой заявки!"),
                    ephemeral=True
                )
                return
            
            # Показываем модальное окно для редактирования
            modal = SafeDocumentsEditModal(application_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            await interaction.response.send_message(
                get_safe_documents_message(interaction.guild.id, "approval.error_edit_failed", "❌ Произошла ошибка при редактировании заявки: {0}").format(str(e)),
                ephemeral=True
            )


class SafeDocumentsApprovedView(discord.ui.View):
    """View для одобренных заявок - только кнопка редактирования для модераторов"""
    
    def __init__(self, application_data: dict = None):
        super().__init__(timeout=None)
        self.application_data = application_data or {}
    
    def _get_application_data(self, interaction: discord.Interaction) -> dict:
        """Получение актуальных данных заявки (аналогично основному view)"""
        if self.application_data and self.application_data.get('user_id', 0) != 0:
            return self.application_data
        
        if interaction.message and interaction.message.embeds:
            # Используем тот же метод извлечения данных
            return SafeDocumentsApplicationView()._extract_application_data_from_embed(interaction.message.embeds[0])
        
        return {}
    
    @discord.ui.button(
        label="Подтверждено",
        style=discord.ButtonStyle.success,
        custom_id="safe_documents:approved_status",
        emoji="✅",
        disabled=True
    )
    async def approved_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Заблокированная кнопка статуса"""
        pass
    
    @discord.ui.button(
        label="Редактировать",
        style=discord.ButtonStyle.secondary,
        custom_id="safe_documents:edit_approved",
        emoji="✏️"
    )
    async def edit_approved_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Редактирование одобренной заявки (только модераторы)"""
        try:
            application_data = self._get_application_data(interaction)
            if not application_data:
                await interaction.response.send_message(
                    get_safe_documents_message(interaction.guild.id, "approval.error_not_found", " Не удалось получить данные заявки!"),
                    ephemeral=True
                )
                return
            
            from .manager import SafeDocumentsManager
            manager = SafeDocumentsManager()
            
            # Только модераторы могут редактировать одобренные заявки
            if not await manager.check_moderator_permissions(interaction.user, application_data.get('department')):
                await interaction.response.send_message(
                    get_safe_documents_message(interaction.guild.id, "approval.error_only_moderators_can_edit_approved", "❌ Только модераторы могут редактировать одобренные заявки!"),
                    ephemeral=True
                )
                return
            
            from .modals import SafeDocumentsEditModal
            modal = SafeDocumentsEditModal(application_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            await interaction.response.send_message(
                get_safe_documents_message(interaction.guild.id, "approval.error_edit_failed", " Произошла ошибка при редактировании заявки: {0}").format(str(e)),
                ephemeral=True
            )


class SafeDocumentsRejectedView(discord.ui.View):
    """View для отклоненных заявок - только кнопка статуса"""
    
    def __init__(self, application_data: dict = None):
        super().__init__(timeout=None)
        self.application_data = application_data or {}
    
    @discord.ui.button(
        label="Отклонено",
        style=discord.ButtonStyle.danger,
        custom_id="safe_documents:rejected_status",
        emoji="❌",
        disabled=True
    )
    async def rejected_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Заблокированная кнопка статуса"""
        pass