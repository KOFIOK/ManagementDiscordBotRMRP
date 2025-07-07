import discord
from typing import Optional

from utils.user_cache import get_cached_user_info
from utils.warehouse_user_data import get_warehouse_user_data
from .manager import SafeDocumentsManager


class SafeDocumentsModal(discord.ui.Modal):
    def __init__(self, edit_mode: bool = False, existing_data: Optional[dict] = None):
        super().__init__(
            title="📋 Форма безопасных документов",
            timeout=300
        )
        
        self.edit_mode = edit_mode
        self.existing_data = existing_data or {}
        
        # Поля формы
        self.name_field = discord.ui.TextInput(
            label="Имя Фамилия",
            placeholder="Введите ваше имя и фамилию",
            required=True,
            max_length=100,
            default=self.existing_data.get('name', '')
        )
        
        self.static_field = discord.ui.TextInput(
            label="Статик",
            placeholder="Введите ваш статик",
            required=True,
            max_length=100,
            default=self.existing_data.get('static', '')
        )
        
        self.documents_field = discord.ui.TextInput(
            label="Копия всех документов",
            placeholder="Ссылки на: паспорт, мед книжка, справка нарколога, права, военный билет",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1000,
            default=self.existing_data.get('documents', '')
        )
        
        self.phone_field = discord.ui.TextInput(
            label="Игровой номер телефона",
            placeholder="Введите ваш игровой номер телефона",
            required=True,
            max_length=50,
            default=self.existing_data.get('phone', '')
        )
        
        # Добавляем поля в модальное окно
        self.add_item(self.name_field)
        self.add_item(self.static_field)
        self.add_item(self.documents_field)
        self.add_item(self.phone_field)

    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы"""
        try:
            # Генерируем email автоматически на основе username пользователя
            user_email = f"{interaction.user.name}@rmrp.ru"
            
            # Собираем данные формы
            form_data = {
                'name': self.name_field.value.strip(),
                'static': self.static_field.value.strip(),
                'documents': self.documents_field.value.strip(),
                'phone': self.phone_field.value.strip(),
                'email': user_email  # Автоматически сгенерированная почта
            }
            
            manager = SafeDocumentsManager()
            
            if self.edit_mode:
                # Редактирование существующей заявки
                await manager.handle_edit_submission(interaction, form_data, self.existing_data)
            else:
                # Новая заявка
                await manager.handle_new_submission(interaction, form_data)
                
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при обработке формы: {str(e)}",
                ephemeral=True
            )

    async def autofill_from_cache(self, user_id: int):
        """Автозаполнение полей из кэша пользователя"""
        try:
            # Получаем данные из user_cache
            cached_data = await get_cached_user_info(user_id)
            
            if cached_data:
                # Заполняем имя и фамилию
                if 'full_name' in cached_data and cached_data['full_name']:
                    self.name_field.default = cached_data['full_name']
                elif 'first_name' in cached_data and 'last_name' in cached_data:
                    # Если есть отдельно имя и фамилия, объединяем их
                    first_name = cached_data['first_name'].strip()
                    last_name = cached_data['last_name'].strip()
                    if first_name or last_name:
                        self.name_field.default = f"{first_name} {last_name}".strip()
                
                # Заполняем статик
                if 'static' in cached_data and cached_data['static']:
                    self.static_field.default = cached_data['static']
                elif 'position' in cached_data and cached_data['position']:
                    self.static_field.default = cached_data['position']
            
            # Если нет данных в user_cache, пробуем warehouse_user_data
            if not cached_data:
                warehouse_data = await get_warehouse_user_data(user_id)
                if warehouse_data:
                    if 'static' in warehouse_data:
                        static_data = warehouse_data['static']
                        
                        # Заполняем имя и фамилию из warehouse_user_data
                        if 'name' in static_data and static_data['name']:
                            self.name_field.default = static_data['name']
                        
                        if 'static' in static_data and static_data['static']:
                            self.static_field.default = static_data['static']
                        elif 'position' in static_data and static_data['position']:
                            self.static_field.default = static_data['position']
                            
        except Exception as e:
            # Если автозаполнение не удалось, просто продолжаем с пустыми полями
            print(f"Warning: Could not autofill safe documents form for user {user_id}: {e}")


class SafeDocumentsRejectionModal(discord.ui.Modal):
    def __init__(self, application_data: dict):
        super().__init__(
            title="❌ Причина отклонения",
            timeout=300
        )
        
        self.application_data = application_data
        
        self.reason_field = discord.ui.TextInput(
            label="Причина отклонения",
            placeholder="Укажите причину отклонения заявки...",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        
        self.add_item(self.reason_field)

    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отклонения заявки"""
        try:
            reason = self.reason_field.value.strip()
            
            manager = SafeDocumentsManager()
            await manager.handle_rejection(interaction, self.application_data, reason)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при отклонении заявки: {str(e)}",
                ephemeral=True
            )


class SafeDocumentsEditModal(discord.ui.Modal):
    def __init__(self, application_data: dict):
        super().__init__(
            title="✏️ Редактирование заявки",
            timeout=300
        )
        
        self.application_data = application_data
        
        # Предзаполняем поля текущими данными
        self.name_field = discord.ui.TextInput(
            label="Имя Фамилия",
            placeholder="Введите имя и фамилию",
            required=True,
            max_length=100,
            default=application_data.get('name', '')
        )
        
        self.static_field = discord.ui.TextInput(
            label="Статик",
            placeholder="Введите статик",
            required=True,
            max_length=100,
            default=application_data.get('static', '')
        )
        
        self.documents_field = discord.ui.TextInput(
            label="Копия всех документов",
            placeholder="Ссылки на: паспорт, мед книжка, справка нарколога, права, военный билет",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1000,
            default=application_data.get('documents', '')
        )
        
        self.phone_field = discord.ui.TextInput(
            label="Игровой номер телефона",
            placeholder="Введите игровой номер телефона",
            required=True,
            max_length=50,
            default=application_data.get('phone', '')
        )
        
        # Добавляем поля
        self.add_item(self.name_field)
        self.add_item(self.static_field)
        self.add_item(self.documents_field)
        self.add_item(self.phone_field)

    async def on_submit(self, interaction: discord.Interaction):
        """Обработка редактирования заявки"""
        try:
            # Генерируем email автоматически на основе username пользователя
            user_email = f"{interaction.user.name}@rmrp.ru"
            
            # Собираем новые данные
            updated_data = {
                'name': self.name_field.value.strip(),
                'static': self.static_field.value.strip(),
                'documents': self.documents_field.value.strip(),
                'phone': self.phone_field.value.strip(),
                'email': user_email,  # Автоматически сгенерированная почта
                # Сохраняем оригинальные данные
                'user_id': self.application_data['user_id'],
                'timestamp': self.application_data['timestamp'],
                'message_id': self.application_data.get('message_id')
            }
            
            manager = SafeDocumentsManager()
            await manager.handle_edit_update(interaction, updated_data, self.application_data)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка при редактировании заявки: {str(e)}",
                ephemeral=True
            )
