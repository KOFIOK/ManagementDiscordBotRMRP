"""
Формы и UI элементы для системы склада - ИСПРАВЛЕННАЯ ВЕРСИЯ
Включает в себя выбор категорий, модальные окна для ввода данных и кнопки модерации
"""

import re
import asyncio
import discord
import traceback
from datetime import datetime
from typing import Optional, Dict, List
from utils.warehouse_manager import WarehouseManager
from utils.user_database import UserDatabase


# =================== PERSISTENT VIEWS для кнопок модерации ===================

class WarehousePersistentRequestView(discord.ui.View):
    """Persistent View для модерации одиночных запросов склада"""
    
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="✅ Выдать склад", style=discord.ButtonStyle.green, custom_id="warehouse_approve", row=0)
    async def approve_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Одобрить запрос склада"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этого действия!", ephemeral=True
                )
                return            # Обновление embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            
            # Добавляем информацию об одобрении
            embed.add_field(
                name="✅ Одобрено", 
                value=f"*Склад выдал: {interaction.user.mention}*", 
                inline=False
            )
            
            # Заменяем view на кнопку статуса "Одобрено" и очищаем пинги
            status_view = WarehouseStatusView(status="approved")
            
            await interaction.response.edit_message(content="", embed=embed, view=status_view)
              # 📋 АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ЗАПИСИ АУДИТА
            try:
                from forms.warehouse.audit import create_automatic_audit_from_approval
                
                # Извлекаем информацию из embed'а заявки
                recipient_id = None
                items_list = []
                
                # Ищем ID получателя в footer
                if embed.footer and embed.footer.text and "ID пользователя:" in embed.footer.text:
                    try:
                        recipient_id = int(embed.footer.text.split("ID пользователя:")[-1].strip())
                    except (ValueError, IndexError):
                        pass
                
                # Извлекаем предметы из description
                if embed.description:
                    # Ищем строки с предметами (обычно содержат × или x)
                    for line in embed.description.split('\n'):
                        if '×' in line or 'x' in line:
                            items_list.append(line.strip())
                
                # Если не нашли предметы в description, ищем в полях
                if not items_list:
                    for field in embed.fields:
                        if any(keyword in field.name.lower() for keyword in ['предмет', 'запрос', 'заявка']):
                            if field.value:
                                for line in field.value.split('\n'):
                                    if '×' in line or 'x' in line:
                                        items_list.append(line.strip())
                
                items_text = '\n'.join(items_list) if items_list else "Предметы не указаны"
                request_url = interaction.message.jump_url
                
                # Создаем запись аудита, если получатель найден
                if recipient_id:
                    recipient = interaction.guild.get_member(recipient_id)
                    if recipient:
                        await create_automatic_audit_from_approval(
                            interaction.guild,
                            interaction.user,  # модератор
                            recipient,         # получатель
                            items_text,        # предметы
                            request_url        # ссылка на заявку
                        )
                        print(f"📋 AUTO AUDIT: Создана запись аудита для выдачи {recipient.display_name}")
                    else:
                        print(f"⚠️ AUTO AUDIT: Получатель с ID {recipient_id} не найден на сервере")
                else:
                    print(f"⚠️ AUTO AUDIT: Не удалось извлечь ID получателя из заявки")
                    
            except Exception as audit_error:
                print(f"❌ AUTO AUDIT: Ошибка при создании автоматического аудита: {audit_error}")
                # Не прерываем основной процесс одобрения из-за ошибки аудита
            
        except Exception as e:
            print(f"Ошибка при одобрении запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )
    
    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, custom_id="warehouse_reject", row=0)
    async def reject_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отклонить запрос склада"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этого действия!", ephemeral=True
                )
                return

            # Показываем модальное окно для ввода причины отказа
            rejection_modal = RejectionReasonModal(interaction.message)
            await interaction.response.send_modal(rejection_modal)
            
        except Exception as e:
            print(f"Ошибка при отклонении запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.",
                ephemeral=True
            )

    @discord.ui.button(label="🗑️ Удалить запрос", style=discord.ButtonStyle.secondary, custom_id="warehouse_delete", row=1)
    async def delete_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Удалить запрос (доступно автору или администраторам)"""
        try:
            # Проверяем права на удаление
            can_delete = await self._check_delete_permissions(interaction)
            if not can_delete:
                return
            
            # Показываем ephemeral сообщение с кнопкой подтверждения
            embed = discord.Embed(
                title="⚠️ Подтверждение удаления",
                description="Вы действительно хотите удалить этот запрос склада?\n\n**Это действие необратимо!**",
                color=discord.Color.orange()
            )
            confirm_view = DeletionConfirmView(interaction.message)
            await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
            
        except Exception as e:
            print(f"Ошибка при попытке удаления запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )

    @discord.ui.button(label="📝 Редактировать", style=discord.ButtonStyle.secondary, custom_id="warehouse_edit", row=1)
    async def edit_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Редактировать заявку (доступно только модераторам)"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для редактирования заявок!", ephemeral=True
                )
                return
            
            # Проверяем, что заявка ещё не обработана (нет статуса одобрения/отказа)
            embed = interaction.message.embeds[0]
            embed_text = str(embed.to_dict())
            
            if "✅ Одобрено" in embed_text or "❌ Отклонено" in embed_text:
                await interaction.response.send_message(
                    "❌ Нельзя редактировать уже обработанную заявку!", ephemeral=True
                )
                return
            
            # Показываем select menu с предметами для редактирования
            view = WarehouseEditSelectView(interaction.message)
            await interaction.response.send_message(
                "📝 Выберите предмет для редактирования:",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Ошибка при попытке редактирования заявки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.",
                ephemeral=True
            )
    
    async def _check_delete_permissions(self, interaction: discord.Interaction) -> bool:
        """Проверить права на удаление запроса"""
        try:
            # 1. Проверяем, является ли пользователь системным или Discord администратором
            from utils.moderator_auth import has_admin_permissions
            if await has_admin_permissions(interaction.user, interaction.guild):
                return True
            
            # 2. Проверяем, является ли пользователь автором запроса
            if interaction.message.embeds:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text:
                    # Извлекаем ID автора из footer
                    footer_text = embed.footer.text
                    if "ID пользователя:" in footer_text:
                        try:
                            author_id = int(footer_text.split("ID пользователя:")[-1].strip())
                            if author_id == interaction.user.id:
                                return True
                        except (ValueError, IndexError):
                            pass
            
            # Если ни одно условие не выполнено - отказываем в доступе
            await interaction.response.send_message(
                "❌ У вас нет прав для удаления этого запроса!\n"
                "Удалить запрос может только его автор или администратор.",
                ephemeral=True
            )
            return False
            
        except Exception as e:
            print(f"Ошибка при проверке прав на удаление: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при проверке прав доступа.", ephemeral=True
            )
            return False


class WarehousePersistentMultiRequestView(discord.ui.View):
    """Persistent View для модерации множественных запросов склада"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ Выдать склад", style=discord.ButtonStyle.green, custom_id="warehouse_multi_approve", row=0)
    async def approve_all_requests(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Одобрить все запросы в заявке"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этого действия!", ephemeral=True
                )
                return

            # Обновление embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
              # Добавляем информацию об одобрении
            embed.add_field(
                name="✅ Одобрено", 
                value=f"*Одобрил: {interaction.user.mention}*", 
                inline=False
            )
            
            # Заменяем view на кнопку статуса "Одобрено" и очищаем пинги
            status_view = WarehouseStatusView(status="approved")
            
            await interaction.response.edit_message(content="", embed=embed, view=status_view)
              # 📋 АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ЗАПИСИ АУДИТА для множественного запроса
            try:
                from forms.warehouse.audit import create_automatic_audit_from_approval
                
                # Извлекаем информацию из embed'а заявки
                recipient_id = None
                items_list = []
                
                # Ищем ID получателя в footer
                if embed.footer and embed.footer.text and "ID пользователя:" in embed.footer.text:
                    try:
                        recipient_id = int(embed.footer.text.split("ID пользователя:")[-1].strip())
                    except (ValueError, IndexError):
                        pass
                
                # Извлекаем предметы из description (для множественных запросов)
                if embed.description:
                    for line in embed.description.split('\n'):
                        if '×' in line or 'x' in line:
                            items_list.append(line.strip())
                
                # Также проверяем поля embed'а
                if not items_list:
                    for field in embed.fields:
                        if any(keyword in field.name.lower() for keyword in ['предмет', 'запрос', 'заявка']):
                            if field.value:
                                for line in field.value.split('\n'):
                                    if '×' in line or 'x' in line:
                                        items_list.append(line.strip())
                
                items_text = '\n'.join(items_list) if items_list else "Множественный запрос - предметы не указаны"
                request_url = interaction.message.jump_url
                
                # Создаем запись аудита, если получатель найден
                if recipient_id:
                    recipient = interaction.guild.get_member(recipient_id)
                    if recipient:
                        await create_automatic_audit_from_approval(
                            interaction.guild,
                            interaction.user,  # модератор
                            recipient,         # получатель
                            items_text,        # предметы
                            request_url        # ссылка на заявку
                        )
                        print(f"📋 AUTO AUDIT: Создана запись аудита для множественной выдачи {recipient.display_name}")
                    else:
                        print(f"⚠️ AUTO AUDIT: Получатель с ID {recipient_id} не найден на сервере")
                else:
                    print(f"⚠️ AUTO AUDIT: Не удалось извлечь ID получателя из множественной заявки")
                    
            except Exception as audit_error:
                print(f"❌ AUTO AUDIT: Ошибка при создании автоматического аудита: {audit_error}")
                # Не прерываем основной процесс одобрения из-за ошибки аудита
            
        except Exception as e:
            print(f"Ошибка при одобрении множественного запроса: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса!", ephemeral=True
            )
    
    @discord.ui.button(label="❌ Отклонить заявку", style=discord.ButtonStyle.red, custom_id="warehouse_multi_reject", row=0)
    async def reject_all_requests(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отклонить всю заявку"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этого действия!", ephemeral=True
                )
                return

            # Показываем модальное окно для ввода причины отказа
            rejection_modal = RejectionReasonModal(interaction.message)
            await interaction.response.send_modal(rejection_modal)
            
        except Exception as e:
            print(f"Ошибка при отклонении множественной заявки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )    @discord.ui.button(label="🗑️ Удалить запрос", style=discord.ButtonStyle.secondary, custom_id="warehouse_multi_delete", row=1)
    async def delete_all_requests(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Удалить всю заявку (доступно автору или администраторам)"""
        try:
            # Проверяем права на удаление
            can_delete = await self._check_delete_permissions(interaction)
            if not can_delete:
                return
            
            # Показываем ephemeral сообщение с кнопкой подтверждения
            embed = discord.Embed(
                title="⚠️ Подтверждение удаления",
                description="Вы действительно хотите удалить этот запрос склада?\n\n**Это действие необратимо!**",
                color=discord.Color.orange()
            )
            
            confirm_view = DeletionConfirmView(interaction.message)
            await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
        except Exception as e:
            print(f"Ошибка при попытке удаления множественной заявки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )

    @discord.ui.button(label="📝 Редактировать", style=discord.ButtonStyle.secondary, custom_id="warehouse_multi_edit", row=1)
    async def edit_multi_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Редактировать множественную заявку (доступно только модераторам)"""
        try:
            # Проверка прав модератора
            from utils.moderator_auth import has_moderator_permissions
            if not await has_moderator_permissions(interaction.user, interaction.guild):
                await interaction.response.send_message(
                    "❌ У вас нет прав для редактирования заявок!", ephemeral=True
                )
                return
            
            # Проверяем, что заявка ещё не обработана (нет статуса одобрения/отказа)
            embed = interaction.message.embeds[0]
            embed_text = str(embed.to_dict())
            
            if "✅ Одобрено" in embed_text or "❌ Отклонено" in embed_text:
                await interaction.response.send_message(
                    "❌ Нельзя редактировать уже обработанную заявку!", ephemeral=True
                )
                return
            
            # Показываем select menu с предметами для редактирования
            view = WarehouseEditSelectView(interaction.message)
            await interaction.response.send_message(
                "📝 Выберите предмет для редактирования:",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Ошибка при попытке редактирования множественной заявки: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке запроса.", ephemeral=True
            )
    
    async def _check_delete_permissions(self, interaction: discord.Interaction) -> bool:
        """Проверить права на удаление запроса"""
        try:
            # 1. Проверяем, является ли пользователь системным или Discord администратором
            from utils.moderator_auth import has_admin_permissions
            if await has_admin_permissions(interaction.user, interaction.guild):
                return True
            
            # 2. Проверяем, является ли пользователь автором запроса
            if interaction.message.embeds:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text:
                    # Извлекаем ID автора из footer
                    footer_text = embed.footer.text
                    if "ID пользователя:" in footer_text:
                        try:
                            author_id = int(footer_text.split("ID пользователя:")[-1].strip())
                            if author_id == interaction.user.id:
                                return True
                        except (ValueError, IndexError):
                            pass
            
            # Если ни одно условие не выполнено - отказываем в доступе
            await interaction.response.send_message(
                "❌ У вас нет прав для удаления этого запроса!\n"
                "Удалить запрос может только его автор или администратор.",
                ephemeral=True
            )
            return False
            
        except Exception as e:
            print(f"Ошибка при проверке прав на удаление: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при проверке прав доступа.", ephemeral=True
            )
            return False


# =================== ДАННЫЕ КОРЗИНЫ ===================

class WarehouseRequestItem:
    """Класс для представления одного предмета в корзине"""
    
    def __init__(self, category: str, item_name: str, quantity: int, user_name: str, 
                 user_static: str, position: str, rank: str):
        self.category = category
        self.item_name = item_name
        self.quantity = quantity
        self.user_name = user_name
        self.user_static = user_static
        self.position = position
        self.rank = rank
        self.timestamp = datetime.now()
    
    def __str__(self):
        return f"**{self.item_name}** × {self.quantity}"


class WarehouseRequestCart:
    """Класс для управления корзиной запросов склада"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.items: List[WarehouseRequestItem] = []
        self.created_at = datetime.now()
    
    def add_item(self, item: WarehouseRequestItem):
        """Добавить предмет в корзину"""
        # Проверяем, есть ли уже такой предмет
        for existing_item in self.items:
            if (existing_item.category == item.category and 
                existing_item.item_name == item.item_name):
                # Если есть, увеличиваем количество
                existing_item.quantity += item.quantity
                return
          # Если нет, добавляем новый предмет
        self.items.append(item)
    
    def remove_item_by_index(self, index: int):
        """Удалить предмет по индексу (0-based)"""
        if 0 <= index < len(self.items):
            self.items.pop(index)
            return True
        return False
    
    def clear(self):
        """Очистить корзину"""
        self.items.clear()
    
    def is_empty(self) -> bool:
        """Проверить, пуста ли корзина"""
        return len(self.items) == 0
    
    def get_total_items(self) -> int:
        """Получить общее количество предметов"""
        return sum(item.quantity for item in self.items)    
    def get_summary(self) -> str:
        """Получить краткое описание корзины"""
        if self.is_empty():
            return "Корзина пуста"
        
        summary = []
        for i, item in enumerate(self.items, 1):
            summary.append(f"{i}. {str(item)}")
        
        return "\n".join(summary)
    
    def get_summary_without_numbers(self) -> str:
        """Получить краткое описание корзины без номеров (для финальной заявки)"""
        if self.is_empty():
            return "Корзина пуста"
        
        summary = []
        for item in self.items:
            summary.append(str(item))
        
        return "\n".join(summary)
    
    def get_item_quantity(self, category: str, item_name: str) -> int:
        """Получить текущее количество конкретного предмета в корзине"""
        for item in self.items:
            if item.category == category and item.item_name == item_name:
                return item.quantity
        return 0


# Глобальный словарь для хранения корзин пользователей
user_carts: Dict[int, WarehouseRequestCart] = {}

# Глобальный словарь для хранения сообщений корзин пользователей (для редактирования)
user_cart_messages: Dict[int, discord.Message] = {}


def get_user_cart(user_id: int) -> WarehouseRequestCart:
    """Получить корзину пользователя"""
    if user_id not in user_carts:
        user_carts[user_id] = WarehouseRequestCart(user_id)
    return user_carts[user_id]


def clear_user_cart(user_id: int):
    """Очистить корзину пользователя безопасно"""
    try:
        cart_cleared = False
        message_cleared = False
        
        if user_id in user_carts:
            del user_carts[user_id]
            cart_cleared = True
            
        if user_id in user_cart_messages:
            del user_cart_messages[user_id]
            message_cleared = True
            
        if cart_cleared or message_cleared:
            print(f"🧹 CART CLEANUP: Очищены данные для пользователя {user_id} (корзина: {'✅' if cart_cleared else '❌'}, сообщение: {'✅' if message_cleared else '❌'})")
        
    except Exception as e:
        print(f"❌ CART CLEANUP ERROR: Ошибка очистки корзины для {user_id}: {e}")


def clear_user_cart_safe(user_id: int, reason: str = "unknown"):
    """Безопасная очистка корзины с указанием причины"""
    try:
        print(f"🧹 CART SAFE CLEAR: Начата очистка для пользователя {user_id}, причина: {reason}")
        clear_user_cart(user_id)
    except Exception as e:
        print(f"❌ CART SAFE CLEAR ERROR: Критическая ошибка очистки корзины для {user_id}: {e}")


def get_user_cart_message(user_id: int) -> Optional[discord.Message]:
    """Получить сообщение корзины пользователя"""
    return user_cart_messages.get(user_id)


def set_user_cart_message(user_id: int, message: discord.Message):
    """Установить сообщение корзины пользователя"""
    user_cart_messages[user_id] = message


# =================== МОДАЛЬНЫЕ ОКНА ===================

class WarehouseRequestModal(discord.ui.Modal):
    """Модальное окно для запроса склада"""
    
    def __init__(self, category: str, item_name: str, warehouse_manager: WarehouseManager, user_data=None):
        super().__init__(title=f"Запрос: {item_name}")
        self.category = category
        self.item_name = item_name
        self.warehouse_manager = warehouse_manager
        
        # Pre-fill name and static if user data is available
        name_value = ""
        static_value = ""
        name_placeholder = "Введите ваше имя и фамилию"
        static_placeholder = "Например: 123-456"
        
        if user_data:
            name_value = user_data.get('full_name', '')
            static_value = user_data.get('static', '')
            if name_value:
                name_placeholder = f"Данные из реестра: {name_value}"
            if static_value:
                static_placeholder = f"Данные из реестра: {static_value}"
        
        # Поля формы
        self.name_input = discord.ui.TextInput(
            label="Имя Фамилия",
            placeholder=name_placeholder,
            default=name_value,
            min_length=3,
            max_length=50,
            required=True
        )
        
        self.static_input = discord.ui.TextInput(
            label="Статик",
            placeholder=static_placeholder,
            default=static_value,
            min_length=5,
            max_length=10,
            required=True
        )
        
        self.quantity_input = discord.ui.TextInput(
            label="Количество",
            placeholder="Введите количество предметов",
            min_length=1,
            max_length=10,
            required=True
        )
        
        self.add_item(self.name_input)
        self.add_item(self.static_input)
        self.add_item(self.quantity_input)

    @classmethod
    async def create_with_user_data(cls, category: str, item_name: str, warehouse_manager: WarehouseManager, user_id: int):
        """
        Create WarehouseRequestModal with auto-filled user data from database
        """
        try:
            # Try to get user data from personnel database
            user_data = await UserDatabase.get_user_info(user_id)
            return cls(category, item_name, warehouse_manager, user_data=user_data)
        except Exception as e:
            print(f"❌ Error loading user data for warehouse modal: {e}")
            # Fallback to empty modal
            return cls(category, item_name, warehouse_manager)

    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы - добавление в корзину"""
        try:
            # Мгновенный ответ для предотвращения таймаута
            await interaction.response.defer(ephemeral=True)
            
            # Показать быстрое сообщение о подготовке формы запроса
            quick_embed = discord.Embed(
                title="⏳ Подготовка формы запроса...",
                description="Обрабатываем ваш запрос, пожалуйста подождите...",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=quick_embed, ephemeral=True)
            
            # Валидация количества
            try:
                quantity = int(self.quantity_input.value.strip())
                if quantity <= 0:
                    raise ValueError("Количество должно быть больше 0")
            except ValueError:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description="Некорректное количество! Введите положительное число.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=error_embed)
                return

            # Форматирование статика
            static = self._format_static(self.static_input.value.strip())
            if not static:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description="Некорректный статик! Используйте формат: 123456 или 123-456",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=error_embed)
                return

            name = self.name_input.value.strip()
            
            # Получение информации о пользователе
            user_info = await self.warehouse_manager.get_user_info(interaction.user)
            _, _, position, rank = user_info
            
            # Если имя или статик не введены, используем данные из системы
            if not name:
                name = user_info[0]
            if not static:
                static = user_info[1]

            # Валидация запроса с учетом лимитов
            category_key = self._get_category_key(self.category)
            is_valid, corrected_quantity, message = self.warehouse_manager.validate_item_request(
                category_key, self.item_name, quantity, position, rank
            )
            
            if not is_valid:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description=message,
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=error_embed)
                return

            # Создание предмета для корзины
            item = WarehouseRequestItem(
                category=self.category,
                item_name=self.item_name,
                quantity=corrected_quantity,
                user_name=name,
                user_static=static,
                position=position,
                rank=rank
            )
            
            # Добавление в корзину
            cart = get_user_cart(interaction.user.id)
            cart.add_item(item)
              # Показ корзины пользователю
            await self._show_cart(interaction, cart, message)
            
        except Exception as e:
            print(f"Ошибка при обработке запроса склада: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при обработке запроса. Попробуйте позже.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=error_embed)

    async def _show_cart(self, interaction: discord.Interaction, cart: WarehouseRequestCart, validation_message: str = ""):
        """Показать содержимое корзины пользователю"""
        embed = discord.Embed(
            title="📦 Ваша заявка на склад",
            description=cart.get_summary(),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if validation_message and "уменьшено" in validation_message:
            embed.add_field(
                name="⚠️ Внимание",
                value=validation_message,
                inline=False
            )
        
        embed.add_field(
            name="📊 Статистика",
            value=f"Предметов в корзине: **{len(cart.items)}**\nОбщее количество: **{cart.get_total_items()}**",
            inline=False
        )
        
        embed.set_footer(text="Выберите действие ниже или продолжите выбор снаряжения из закреплённого сообщения")
        
        view = WarehouseCartView(cart, self.warehouse_manager)
        await interaction.edit_original_response(embed=embed, view=view)

    def _format_static(self, static: str) -> str:
        """Форматирование статика в стандартный вид"""
          # Удаляем все, кроме цифр
        digits = re.sub(r'\D', '', static)
        
        # Проверяем длину
        if len(digits) == 6:
            return f"{digits[:3]}-{digits[3:]}"
        elif len(digits) == 5:
            return f"{digits[:2]}-{digits[2:]}"
        
        return ""

    def _get_category_key(self, category: str) -> str:
        """Получить ключ категории"""
        category_mapping = {
            "Оружие": "оружие",
            "Бронежилеты": "бронежилеты", 
            "Медикаменты": "медикаменты",
            "Другое": "другое"
        }
        return category_mapping.get(category, "другое")


class WarehouseQuantityModal(discord.ui.Modal):
    """Упрощенное модальное окно только для ввода количества - СУПЕР БЫСТРАЯ ВЕРСИЯ"""
    
    def __init__(self, category: str, item_name: str, warehouse_manager: WarehouseManager):
        super().__init__(title=f"Запрос: {item_name}")
        self.category = category
        self.item_name = item_name
        self.warehouse_manager = warehouse_manager
        
        # Только поле для количества
        self.quantity_input = discord.ui.TextInput(
            label="Количество",
            placeholder="Введите количество предметов",
            min_length=1,
            max_length=10,
            required=True
        )
        
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы - СУПЕР БЫСТРАЯ версия для предотвращения таймаутов"""
        try:            # ⚡ МГНОВЕННЫЙ DEFER - самое первое действие!
            await interaction.response.defer(ephemeral=True)
              # 🧹 Очистка старого сообщения корзины перед созданием нового loading_message
            existing_message = get_user_cart_message(interaction.user.id)
            if existing_message:
                try:
                    await existing_message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
                # Очищаем только ссылку на сообщение, но НЕ корзину
                if interaction.user.id in user_cart_messages:
                    del user_cart_messages[interaction.user.id]
            
            # 🔄 Показать быстрое сообщение о подготовке черновика
            quick_embed = discord.Embed(
                title="⏳ Подготовка формы запроса...",
                description="Добавляем предмет в корзину...",
                color=discord.Color.orange()
            )
            loading_message = await interaction.followup.send(embed=quick_embed, ephemeral=True)
            
            # ⚡ БЫСТРАЯ валидация количества (микросекунды)
            try:
                quantity = int(self.quantity_input.value.strip())
                if quantity <= 0:
                    raise ValueError("Количество должно быть больше 0")
                if quantity > 999:  # Разумный лимит для предотвращения злоупотреблений
                    raise ValueError("Слишком большое количество")
            except ValueError as e:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description=f"Некорректное количество! {str(e)}",
                    color=discord.Color.red()
                )
                await loading_message.edit(embed=error_embed)
                return

            # 🚀 СУПЕР БЫСТРОЕ получение данных из кэша с fallback
            print(f"⚡ ULTRA FAST: Обработка запроса {self.item_name} для {interaction.user.display_name}")
              # Используем максимально быстрый путь
            position = "Не указано"
            rank = "Не указано"
            
            try:
                # Попытка получить из кэша (наиболее быстро)
                from utils.user_cache import get_cached_user_info
                user_data = await get_cached_user_info(interaction.user.id, force_refresh=False)
                
                if user_data:
                    position = user_data.get('position', 'Не указано')
                    rank = user_data.get('rank', 'Не указано')
                    print(f"✅ LIGHTNING CACHE: {position}, {rank}")
                else:
                    # Быстрый fallback через роли Discord (без обращения к БД)
                    for role in interaction.user.roles:
                        role_name = role.name.lower()
                        if "офицер" in role_name or "командир" in role_name:
                            position = "Офицер"
                            break
                        elif "сержант" in role_name:
                            rank = "Сержант"
                        elif "рядовой" in role_name:
                            rank = "Рядовой"
                    print(f"📋 ROLE FAST: {position}, {rank}")
                        
            except Exception as e:
                print(f"⚠️ Fallback для данных: {e}")
                # Используем безопасные значения по умолчанию

            # 🛡️ ПОЛУЧАЕМ КОРЗИНУ И ПРОВЕРЯЕМ СУЩЕСТВУЮЩЕЕ КОЛИЧЕСТВО
            cart = get_user_cart(interaction.user.id)
            current_time = datetime.now()
            
            # Получаем текущее количество этого предмета в корзине
            existing_quantity = cart.get_item_quantity(self.category, self.item_name)
            total_quantity = existing_quantity + quantity  # Суммарное количество после добавления
            
            print(f"📊 ITEM CHECK: {self.item_name} - в корзине: {existing_quantity}, добавляем: {quantity}, итого: {total_quantity}")            # ⚡ ВАЛИДАЦИЯ С УЧЕТОМ КОРЗИНЫ - проверяем лимиты на суммарное количество
            category_key = self._get_category_key(self.category)
            is_valid, corrected_total_quantity, validation_message = self.warehouse_manager.validate_item_request(
                category_key, self.item_name, total_quantity, position, rank
            )
            
            if not is_valid:
                # Если валидация не прошла по критическим причинам (недоступное оружие и т.д.)
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description=validation_message,
                    color=discord.Color.red()
                )
                await loading_message.edit(embed=error_embed)
                return
            
            # Вычисляем, сколько реально нужно добавить
            final_quantity_to_add = corrected_total_quantity - existing_quantity
            warning_message = ""
            
            # Если лимит был превышен, показываем предупреждение
            if "уменьшено" in validation_message:
                warning_message = validation_message
            
            # Проверяем дубликаты по времени (быстрое добавление)
            for existing_item in cart.items:
                if (existing_item.category == self.category and 
                    existing_item.item_name == self.item_name and
                    (current_time - existing_item.timestamp).total_seconds() < 15):  # Увеличили до 15 сек
                    
                    # Обновляем существующий предмет до corrected_total_quantity
                    existing_item.quantity = corrected_total_quantity
                    print(f"🔄 VALIDATED DUPLICATE: обновлено до {corrected_total_quantity} для {self.item_name}")
                    await self._show_cart_ultra_fast(interaction, cart, warning_message, loading_message)
                    return
            
            # Проверяем, есть ли уже такой предмет в корзине (без учета времени)
            for existing_item in cart.items:
                if (existing_item.category == self.category and 
                    existing_item.item_name == self.item_name):
                    # Обновляем существующий предмет до corrected_total_quantity
                    existing_item.quantity = corrected_total_quantity
                    existing_item.timestamp = current_time  # Обновляем время
                    print(f"🔄 ITEM UPDATED: {self.item_name} обновлено до {corrected_total_quantity} (было {existing_quantity})")
                    await self._show_cart_ultra_fast(interaction, cart, warning_message, loading_message)
                    return
            
            # Если предмет не найден, создаем новый с corrected_total_quantity
            item = WarehouseRequestItem(
                category=self.category,
                item_name=self.item_name,
                quantity=corrected_total_quantity,
                user_name="",  # Будет заполнено позже
                user_static="",  # Будет заполнено позже
                position=position,
                rank=rank
            )
            
            # Добавление в корзину (предмета точно нет, так как мы проверили выше)
            cart.items.append(item)  # Используем напрямую append вместо add_item
            print(f"✅ NEW ITEM CREATED: {self.item_name} x{corrected_total_quantity}")
            
            # 🚀 СУПЕР быстрое отображение
            await self._show_cart_ultra_fast(interaction, cart, warning_message, loading_message)
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR в WarehouseQuantityModal: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                # Пытаемся обновить сообщение загрузки, если оно есть
                if 'loading_message' in locals():
                    error_embed = discord.Embed(
                        title="❌ Ошибка",
                        description="Временная ошибка. Попробуйте ещё раз.",
                        color=discord.Color.red()
                    )
                    await loading_message.edit(embed=error_embed)
                else:
                    await interaction.followup.send(
                        "❌ Временная ошибка. Попробуйте ещё раз.",
                        ephemeral=True
                    )
            except:
                print("❌ Критическая ошибка: не удалось отправить уведомление об ошибке")

    async def _show_cart_ultra_fast(self, interaction: discord.Interaction, cart: WarehouseRequestCart, 
                                   validation_message: str = "", loading_message = None):
        """УЛЬТРА-БЫСТРОЕ отображение корзины для предотвращения таймаутов Discord"""
        try:
            # Формируем описание с предупреждением, если есть
            description = f"В корзине: **{len(cart.items)}** поз. | Всего: **{cart.get_total_items()}** ед."
            if validation_message:
                description += f"\n\n{validation_message}"
            
            embed = discord.Embed(
                title="📦 Корзина обновлена",
                description=description,
                color=discord.Color.green()
            )              # Полный список ВСЕХ предметов с нумерацией для черновика
            items_list = []
            for i, item in enumerate(cart.items, 1):
                items_list.append(f"{i}. **{item.item_name}** × {item.quantity}")
            items_text = "\n".join(items_list)
            
            embed.add_field(name="Все предметы в корзине", value=items_text or "Нет предметов", inline=False)
            
            # Быстрая view с минимальным функционалом
            view = WarehouseCartView(cart, self.warehouse_manager)
            
            # Приоритет 1: обновляем сообщение загрузки, если оно есть
            if loading_message:
                try:
                    await loading_message.edit(embed=embed, view=view)
                    
                    # Удаляем старое сообщение корзины, если оно есть и отличается от loading_message
                    existing_message = get_user_cart_message(interaction.user.id)
                    if existing_message and existing_message.id != loading_message.id:
                        try:
                            await existing_message.delete()
                        except (discord.NotFound, discord.HTTPException):
                            pass
                    
                    # Устанавливаем loading_message как новое сообщение корзины
                    set_user_cart_message(interaction.user.id, loading_message)
                    return
                except (discord.NotFound, discord.HTTPException):
                    pass
            
            # Приоритет 2: обновляем существующее сообщение корзины
            existing_message = get_user_cart_message(interaction.user.id)
            
            if existing_message:
                try:
                    await existing_message.edit(embed=embed, view=view)
                    return
                except (discord.NotFound, discord.HTTPException):
                    pass
            
            # Приоритет 3: создаем новое сообщение корзины
            try:
                message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                set_user_cart_message(interaction.user.id, message)
            except Exception:
                await interaction.followup.send(f"✅ Добавлено: **{cart.items[-1].item_name}** × {cart.items[-1].quantity}", ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка в _show_cart_ultra_fast: {e}")
            try:
                await interaction.followup.send("✅ Предмет добавлен в корзину!", ephemeral=True)
            except:
                pass

    def _get_category_key(self, category: str) -> str:
        """Получить ключ категории"""
        category_mapping = {
            "Оружие": "оружие",
            "Бронежилеты": "бронежилеты", 
            "Медикаменты": "медикаменты",
            "Другое": "другое"
        }
        return category_mapping.get(category, "другое")


# =================== VIEWS ===================

class WarehouseCategorySelect(discord.ui.Select):
    """Выбор категории склада - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self):
        # Статические опции, не зависящие от warehouse_manager
        options = [
            discord.SelectOption(
                label="Оружие",
                emoji="🔫",
                description="Выберите для запроса оружия",
                value="weapon"
            ),
            discord.SelectOption(
                label="Бронежилеты",
                emoji="🦺",
                description="Выберите для запроса бронежилетов",
                value="armor"
            ),
            discord.SelectOption(
                label="Медикаменты",
                emoji="💊",
                description="Выберите для запроса медикаментов",
                value="medical"
            ),
            discord.SelectOption(
                label="Другое",
                emoji="📦",
                description="Выберите для запроса другого имущества",
                value="other"
            )
        ]
        
        super().__init__(
            placeholder="📦 Выберите категорию складского имущества...",
            options=options,
            custom_id="warehouse_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        """Обработка выбора категории"""
        try:
            # Создаем warehouse_manager для проверок
            from utils.google_sheets import GoogleSheetsManager
            sheets_manager = GoogleSheetsManager()
            warehouse_manager = WarehouseManager(sheets_manager)
              # Проверка кулдауна для всех пользователей (включая админов)
            submission_channel_id = warehouse_manager.get_warehouse_submission_channel()
            if submission_channel_id:
                channel = interaction.guild.get_channel(submission_channel_id)
                if channel:
                    can_request, next_time = await warehouse_manager.check_user_cooldown(
                        interaction.user.id, channel
                    )
                    
                    if not can_request and next_time:
                        # next_time уже в московском времени из warehouse_manager
                        from datetime import timezone, timedelta
                        moscow_tz = timezone(timedelta(hours=3))  # UTC+3 для Москвы
                        current_time_moscow = datetime.now(moscow_tz).replace(tzinfo=None)
                        time_left = next_time - current_time_moscow
                        hours = int(time_left.total_seconds() // 3600)
                        minutes = int((time_left.total_seconds() % 3600) // 60)
                        
                        await interaction.response.send_message(
                            f"⏰ Кулдаун! Вы можете подать следующий запрос через {hours}ч {minutes}мин",
                            ephemeral=True
                        )
                        return            # Преобразование value в полное название категории
            category_mapping = {
                "weapon": "Оружие",
                "armor": "Бронежилеты",
                "medical": "Медикаменты",
                "other": "Другое"
            }
            
            selected_value = self.values[0]
            selected_category = category_mapping.get(selected_value)
            
            if not selected_category:
                await interaction.response.send_message(
                    "❌ Неизвестная категория! Попробуйте ещё раз.",
                    ephemeral=True
                )
                return
            
            # Получение информации о категории из warehouse_manager
            category_info = warehouse_manager.item_categories.get(selected_category)
            
            if not category_info:
                await interaction.response.send_message(
                    f"❌ Категория '{selected_category}' не найдена в системе!",
                    ephemeral=True
                )
                return
            
            # Создание выбора предметов
            view = WarehouseItemSelectView(selected_category, category_info, warehouse_manager)
            
            embed = discord.Embed(
                title=f"{category_info['emoji']} {selected_category}",
                description="Выберите конкретный предмет для запроса:",
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Ошибка при выборе категории склада: {e}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"❌ Произошла ошибка: {str(e)}", ephemeral=True
                )
            except:
                print("❌ Не удалось отправить сообщение об ошибке пользователю")


class WarehouseItemSelectView(discord.ui.View):
    """View для выбора конкретного предмета - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self, category: str, category_info: Dict, warehouse_manager: WarehouseManager):
        super().__init__(timeout=None)  # 5 минут таймаут для выбора предмета
        self.category = category
        self.category_info = category_info
        self.warehouse_manager = warehouse_manager
          # Добавление кнопок для каждого предмета
        items = category_info["items"]
        for i, item in enumerate(items):
            if i < 20:  # Максимум 20 кнопок (4 ряда по 5)
                # ИСПРАВЛЕНИЕ: делаем custom_id уникальным для каждой категории!
                unique_id = f"warehouse_{self.category.lower()}_{i}_{hash(item) % 10000}"
                button = discord.ui.Button(
                    label=item[:80] if len(item) > 80 else item,  # Ограничение длины
                    style=discord.ButtonStyle.secondary,
                    custom_id=unique_id,  # Уникальный ID!
                    row=i // 5  # Распределение по рядам
                )
                button.callback = self._create_item_callback(item)
                self.add_item(button)

    def _create_item_callback(self, item_name: str):
        """Создать callback для кнопки предмета"""
        # ВАЖНО: захватываем значения по значению, а не по ссылке!
        category = self.category
        warehouse_manager = self.warehouse_manager
        
        async def callback(interaction: discord.Interaction):
            # ОТЛАДКА: выводим что именно открываем
            print(f"🔍 CALLBACK: Пользователь {interaction.user.display_name} нажал '{item_name}' в категории '{category}'")
            
            # Специальная обработка для кастомного предмета "Прочее"
            if item_name == "Прочее":
                modal = WarehouseCustomItemModal(category, warehouse_manager)
            else:
                # Создание упрощенного модального окна только для количества
                modal = WarehouseQuantityModal(category, item_name, warehouse_manager)
            await interaction.response.send_modal(modal)
            
        return callback


class WarehousePinMessageView(discord.ui.View):
    """View для закрепленного сообщения склада - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self):
        super().__init__(timeout=None)
        
        # Добавление селекта категорий
        self.add_item(WarehouseCategorySelect())


class WarehouseCartView(discord.ui.View):
    """View для управления корзиной запросов"""
    
    def __init__(self, cart: WarehouseRequestCart, warehouse_manager: WarehouseManager, is_submitted: bool = False):
        super().__init__(timeout=None)
        self.cart = cart
        self.warehouse_manager = warehouse_manager
        self.is_submitted = is_submitted

    @discord.ui.button(label="Подтвердить отправку", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Подтвердить и отправить весь запрос"""
        if self.is_submitted:
            await interaction.response.send_message(
                "❌ Заявка уже была отправлена!",
                ephemeral=True
            )
            return
        
        try:
            if self.cart.is_empty():
                await interaction.response.send_message(
                    "❌ Корзина пуста! Добавьте предметы перед отправкой.",
                    ephemeral=True
                )
                return
              # Проверка кулдауна перед отправкой
            submission_channel_id = self.warehouse_manager.get_warehouse_submission_channel()
            if submission_channel_id:
                channel = interaction.guild.get_channel(submission_channel_id)
                if channel:
                    can_request, next_time = await self.warehouse_manager.check_user_cooldown(
                        interaction.user.id, channel
                    )
                    if not can_request and next_time:
                        from datetime import timezone, timedelta
                        moscow_tz = timezone(timedelta(hours=3))
                        current_time_moscow = datetime.now(moscow_tz).replace(tzinfo=None)
                        time_left = next_time - current_time_moscow
                        hours = int(time_left.total_seconds() // 3600)
                        minutes = int((time_left.total_seconds() % 3600) // 60)
                        await interaction.response.send_message(
                            f"⏰ Кулдаун! Вы можете подать следующий запрос через {hours}ч {minutes}мин",
                            ephemeral=True
                        )
                        return
            
            # НЕ устанавливаем флаг отправки здесь - только после реальной отправки в канал!
            
            # Показываем модальное окно
            try:
                from utils.warehouse_user_data import prepare_modal_data
                modal_data = await prepare_modal_data(interaction.user.id)
                modal = WarehouseFinalDetailsModal.create_with_prefilled_data(
                    self.cart, self.warehouse_manager, interaction,
                    name=modal_data['name_value'],
                    static=modal_data['static_value'],
                    parent_view=self
                )
                print(f"🚀 FAST MODAL: Создано модальное окно с данными из {modal_data['source']} для {interaction.user.display_name}")
                await interaction.response.send_modal(modal)
            except Exception as e:
                print(f"❌ Ошибка предзагрузки данных пользователя: {e}")
                try:
                    modal = WarehouseFinalDetailsModal(self.cart, self.warehouse_manager, interaction, parent_view=self)
                    await interaction.response.send_modal(modal)
                except Exception as modal_error:
                    print(f"❌ Критическая ошибка с модальным окном: {modal_error}")
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            "❌ Произошла ошибка при открытии формы заявки. Попробуйте позже.",
                            ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            "❌ Произошла ошибка при открытии формы заявки. Попробуйте позже.",
                            ephemeral=True
                        )
                    return
        except Exception as e:
            print(f"❌ Критическая ошибка в confirm_request: {e}")

    @discord.ui.button(label="Очистить корзину", style=discord.ButtonStyle.secondary, emoji="🗑️")
    async def clear_cart(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Очистить корзину с подтверждением"""
        if self.is_submitted:
            await interaction.response.send_message(
                "❌ Нельзя изменять корзину после отправки заявки!",
                ephemeral=True
            )
            return
            
        confirm_embed = discord.Embed(
            title="⚠️ Подтверждение очистки",
            description="Вы действительно хотите удалить **все предметы** из корзины?\n\n**Это действие необратимо!**",
            color=discord.Color.orange()
        )
        
        confirm_view = ConfirmClearCartView(self.cart, self.warehouse_manager)
        await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)

    @discord.ui.button(label="Удалить по номеру", style=discord.ButtonStyle.secondary, emoji="❌")
    async def remove_by_number(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Удалить предмет по номеру позиции"""
        if self.is_submitted:
            await interaction.response.send_message(
                "❌ Нельзя изменять корзину после отправки заявки!",
                ephemeral=True
            )
            return
            
        if self.cart.is_empty():
            await interaction.response.send_message(
                "❌ Корзина уже пуста!",
                ephemeral=True
            )
            return
        
        modal = RemoveItemByNumberModal(self.cart, self.warehouse_manager)
        await interaction.response.send_modal(modal)
        await interaction.response.send_modal(modal)
    
    async def _safe_update_cart_display(self, interaction: discord.Interaction):
        """Безопасное обновление отображения корзины"""
        try:
            if self.cart.is_empty():
                # Корзина пуста - показываем сообщение о возврате к главному меню
                empty_embed = discord.Embed(
                    title="📦 Корзина пуста",
                    description="Все предметы удалены из корзины.\n\nДля новых запросов используйте закрепленное сообщение склада.",
                    color=discord.Color.blue()
                )
                empty_embed.set_footer(text="Сообщение автоматически исчезнет через 10 секунд")
                
                # Удаляем сообщение корзины из отслеживания
                if interaction.user.id in user_cart_messages:
                    del user_cart_messages[interaction.user.id]
                
                await interaction.response.edit_message(embed=empty_embed, view=None)
                
                # Автоматически удаляем сообщение через 10 секунд
                import asyncio
                await asyncio.sleep(10)
                try:
                    await interaction.delete_original_response()
                except:
                    pass  # Игнорируем ошибки удаления
                    
            else:
                # Обновляем отображение корзины с актуальными данными
                embed = discord.Embed(
                    title="📦 Ваша заявка на склад",
                    description=self.cart.get_summary(),
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📊 Статистика",
                    value=f"Предметов в корзине: **{len(self.cart.items)}**\nОбщее количество: **{self.cart.get_total_items()}**",
                    inline=False
                )
                
                embed.set_footer(text="Последний предмет удалён из корзины")
                
                # Создаем новый view с актуальным состоянием
                new_view = WarehouseCartView(self.cart, self.warehouse_manager, self.is_submitted)
                await interaction.response.edit_message(embed=embed, view=new_view)
                
        except Exception as e:
            print(f"❌ Ошибка обновления корзины: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обновлении корзины.",
                ephemeral=True            )


# =================== МОДАЛЬНОЕ ОКНО ДЛЯ УДАЛЕНИЯ ПО НОМЕРУ ===================

class RemoveItemByNumberModal(discord.ui.Modal):
    """Модальное окно для удаления предмета по номеру позиции"""
    def __init__(self, cart: WarehouseRequestCart, warehouse_manager: WarehouseManager):
        super().__init__(title=f"Удалить предмет (1-{len(cart.items)})")
        self.cart = cart
        self.warehouse_manager = warehouse_manager
        
        # Только поле для ввода номера - список предметов пользователь уже видит в корзине
        self.number_input = discord.ui.TextInput(
            label="Номер позиции для удаления",
            placeholder=f"Введите номер от 1 до {len(cart.items)}",
            min_length=1,
            max_length=3,
            required=True
        )
        
        self.add_item(self.number_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка удаления предмета по номеру"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Валидация номера
            try:
                item_number = int(self.number_input.value.strip())
                if item_number < 1 or item_number > len(self.cart.items):
                    raise ValueError(f"Номер должен быть от 1 до {len(self.cart.items)}")
            except ValueError as e:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description=f"Некорректный номер! {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return
            
            # Сохраняем информацию об удаляемом предмете
            removed_item = self.cart.items[item_number - 1]  # -1 потому что нумерация с 0
            
            # Удаляем предмет по индексу
            self.cart.remove_item_by_index(item_number - 1)
            
            # Формируем сообщение об успешном удалении
            success_embed = discord.Embed(
                title="✅ Предмет удален",
                description=f"Удален предмет #{item_number}: **{removed_item.item_name}** × {removed_item.quantity}",
                color=discord.Color.green()
            )
            
            # Если корзина стала пустой
            if self.cart.is_empty():
                success_embed.add_field(
                    name="📦 Корзина пуста",
                    value="Все предметы удалены. Для новых запросов используйте закрепленное сообщение склада.",
                    inline=False
                )
                
                # Очищаем корзину из отслеживания
                clear_user_cart_safe(interaction.user.id, "корзина опустошена через удаление")
                
                await interaction.followup.send(embed=success_embed, ephemeral=True)
                
                # Обновляем исходное сообщение
                original_message = get_user_cart_message(interaction.user.id)
                if original_message:
                    try:
                        empty_embed = discord.Embed(
                            title="📦 Корзина пуста",
                            description="Все предметы удалены из корзины.\n\nДля новых запросов используйте закрепленное сообщение склада.",
                            color=discord.Color.blue()
                        )
                        empty_embed.set_footer(text="Сообщение автоматически исчезнет через 10 секунд")
                        await original_message.edit(embed=empty_embed, view=None)
                        
                        # Удаляем сообщение через 10 секунд
                        import asyncio
                        await asyncio.sleep(10)
                        try:
                            await original_message.delete()
                        except:
                            pass
                    except (discord.NotFound, discord.HTTPException):
                        pass
            else:
                # Корзина не пуста - обновляем отображение
                await interaction.followup.send(embed=success_embed, ephemeral=True)
                
                # Обновляем корзину
                await self._update_cart_display(interaction)
                
        except Exception as e:
            print(f"❌ Ошибка при удалении предмета по номеру: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при удалении предмета. Попробуйте позже.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    async def _update_cart_display(self, interaction: discord.Interaction):
        """Обновить отображение корзины после удаления"""
        try:
            original_message = get_user_cart_message(interaction.user.id)
            if original_message:
                # Создаем обновленный embed
                embed = discord.Embed(
                    title="📦 Ваша заявка на склад",
                    description=self.cart.get_summary(),
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📊 Статистика",
                    value=f"Предметов в корзине: **{len(self.cart.items)}**\nОбщее количество: **{self.cart.get_total_items()}**",
                    inline=False
                )
                
                embed.set_footer(text="Предмет удален из корзины")
                
                # Создаем новый view с актуальным состоянием
                new_view = WarehouseCartView(self.cart, self.warehouse_manager)
                await original_message.edit(embed=embed, view=new_view)
        except Exception as e:
            print(f"❌ Ошибка обновления корзины: {e}")


# =================== ПОДТВЕРЖДЕНИЕ ОЧИСТКИ КОРЗИНЫ ===================

class ConfirmClearCartView(discord.ui.View):
    """View для подтверждения очистки корзины"""
    
    def __init__(self, cart: WarehouseRequestCart, warehouse_manager: WarehouseManager):
        super().__init__(timeout=30)  # 30 секунд на подтверждение
        self.cart = cart
        self.warehouse_manager = warehouse_manager
    
    @discord.ui.button(label="✅ Да, очистить", style=discord.ButtonStyle.danger)
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Подтвердить очистку корзины"""
        try:
            self.cart.clear()
              # Удаляем сообщение корзины из отслеживания
            if interaction.user.id in user_cart_messages:
                cart_message = user_cart_messages[interaction.user.id]
                clear_user_cart_safe(interaction.user.id, "manual_clear")
                
                # Обновляем основное сообщение корзины
                embed = discord.Embed(
                    title="🗑️ Корзина очищена",
                    description="Все предметы удалены из корзины.\n\nДля новых запросов используйте закрепленное сообщение склада.",
                    color=discord.Color.orange()
                )
                embed.set_footer(text="Сообщение автоматически исчезнет через 10 секунд")
                
                await cart_message.edit(embed=embed, view=None)
                
                # Автоматически удаляем сообщение через 10 секунд
                import asyncio
                asyncio.create_task(self._auto_delete_message(cart_message))
            
            await interaction.response.edit_message(
                content="✅ Корзина успешно очищена!",
                embed=None,
                view=None
            )
            
        except Exception as e:
            print(f"❌ Ошибка очистки корзины: {e}")
            await interaction.response.edit_message(
                content="❌ Произошла ошибка при очистке корзины.",
                embed=None,
                view=None
            )
    
    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отменить очистку корзины"""
        await interaction.response.edit_message(
            content="Очистка корзины отменена.",
            embed=None,
            view=None
        )
    
    async def _auto_delete_message(self, message):
        """Автоматически удалить сообщение через 10 секунд"""
        import asyncio
        await asyncio.sleep(10)
        try:
            await message.delete()
        except:
            pass  # Игнорируем ошибки удаления


# =================== РЕДАКТИРОВАНИЕ ЗАЯВОК МОДЕРАТОРАМИ ===================

class WarehouseEditSelectView(discord.ui.View):
    """View с Select Menu для выбора предмета для редактирования"""
    
    def __init__(self, original_message: discord.Message):
        super().__init__(timeout=300)  # 5 минут на выбор
        self.original_message = original_message
        
        # Создаем select menu с предметами из заявки
        self.add_item(WarehouseEditSelect(original_message))

class WarehouseEditSelect(discord.ui.Select):
    """Select для выбора предмета для редактирования"""
    
    def __init__(self, original_message: discord.Message):
        self.original_message = original_message
        
        # Парсим предметы из embed заявки
        items = self._parse_items_from_embed()
        
        # Создаем опции для select menu
        options = []
        for i, (item_text, item_name, quantity) in enumerate(items):
            if i < 25:  # Discord лимит на select options
                options.append(discord.SelectOption(
                    label=f"{i+1}. {item_name}",
                    description=f"Количество: {quantity}",
                    value=str(i),
                    emoji="📦"
                ))
        
        if not options:
            options.append(discord.SelectOption(
                label="Предметы не найдены",
                description="Ошибка парсинга заявки",
                value="error"
            ))
        
        super().__init__(
            placeholder="Выберите предмет для редактирования...",
            options=options,
            custom_id="warehouse_edit_select"
        )
        
        self.parsed_items = items
    
    def _parse_items_from_embed(self) -> List[tuple]:
        """Парсит предметы из embed заявки"""
        items = []
        
        try:
            embed = self.original_message.embeds[0]
            
            # Ищем поле с предметами
            for field in embed.fields:
                if "запрашиваемые предметы" in field.name.lower() or "предмет" in field.name.lower():
                    field_value = field.value
                    
                    # Парсим строки вида "1. **AK-74M** × 2"
                    lines = field_value.split('\n')
                    for line in lines:
                        line = line.strip()
                        if '×' in line or 'x' in line:
                            # Извлекаем номер, название и количество
                            import re
                            
                            # Паттерн для строки "1. **название** × количество"
                            match = re.match(r'(\d+)\.\s*\*\*(.*?)\*\*\s*[×x]\s*(\d+)', line)
                            if match:
                                number, item_name, quantity = match.groups()
                                items.append((line, item_name.strip(), int(quantity)))
                            else:
                                # Fallback парсинг для других форматов
                                if '**' in line and ('×' in line or 'x' in line):
                                    parts = line.split('**')
                                    if len(parts) >= 3:
                                        item_name = parts[1].strip()
                                        quantity_part = line.split('×')[-1] if '×' in line else line.split('x')[-1]
                                        try:
                                            quantity = int(quantity_part.strip())
                                            items.append((line, item_name, quantity))
                                        except ValueError:
                                            pass
                    break
        except Exception as e:
            print(f"❌ Ошибка парсинга предметов из embed: {e}")
        
        return items
    
    async def callback(self, interaction: discord.Interaction):
        """Обработка выбора предмета"""
        try:
            if self.values[0] == "error":
                await interaction.response.send_message(
                    "❌ Ошибка парсинга заявки. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Получаем выбранный предмет
            item_index = int(self.values[0])
            if item_index >= len(self.parsed_items):
                await interaction.response.send_message(
                    "❌ Ошибка: предмет не найден.",
                    ephemeral=True
                )
                return
            
            item_text, item_name, current_quantity = self.parsed_items[item_index]
            
            # Показываем кнопки действий
            view = WarehouseEditActionView(
                self.original_message, 
                item_index, 
                item_text, 
                item_name, 
                current_quantity
            )
            
            embed = discord.Embed(
                title="🔧 Действия с предметом",
                description=f"**Выбранный предмет:** {item_name}\n**Текущее количество:** {current_quantity}",
                color=discord.Color.orange()
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"❌ Ошибка при выборе предмета для редактирования: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке выбора.",
                ephemeral=True
            )


class WarehouseEditActionView(discord.ui.View):
    """View с кнопками действий над выбранным предметом"""
    
    def __init__(self, original_message: discord.Message, item_index: int, 
                 item_text: str, item_name: str, current_quantity: int):
        super().__init__(timeout=300)  # 5 минут на действие
        self.original_message = original_message
        self.item_index = item_index
        self.item_text = item_text
        self.item_name = item_name
        self.current_quantity = current_quantity
    
    @discord.ui.button(label="🗑️ Удалить предмет", style=discord.ButtonStyle.danger)
    async def delete_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Удалить предмет из заявки (зачеркнуть)"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Обновляем оригинальное сообщение заявки
            await self._update_original_message_remove_item(interaction)
            
            await interaction.followup.send(
                f"✅ Предмет **{self.item_name}** удален из заявки.",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"❌ Ошибка при удалении предмета: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при удалении предмета.",
                ephemeral=True
            )
    
    @discord.ui.button(label="📝 Изменить количество", style=discord.ButtonStyle.primary)
    async def edit_quantity(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Изменить количество предмета"""
        try:
            modal = WarehouseEditQuantityModal(
                self.original_message,
                self.item_index,
                self.item_text,
                self.item_name,
                self.current_quantity
            )
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"❌ Ошибка при открытии модального окна: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при открытии формы.",
                ephemeral=True
            )
    
    async def _update_original_message_remove_item(self, interaction: discord.Interaction):
        """Обновить оригинальное сообщение - удалить предмет"""
        try:
            embed = self.original_message.embeds[0]
            original_view = None
            
            # Сохраняем оригинальный view
            if self.original_message.components:
                # Определяем тип view по количеству кнопок или custom_id
                embed_text = str(embed.to_dict())
                is_multi_request = False
                for field in embed.fields:
                    if "запрашиваемые предметы" in field.name.lower() and "поз.)" in field.name:
                        is_multi_request = True
                        break
                
                # Восстанавливаем соответствующий view
                if is_multi_request:
                    original_view = WarehousePersistentMultiRequestView()
                else:
                    original_view = WarehousePersistentRequestView()
            
            # Ищем поле с предметами
            for i, field in enumerate(embed.fields):
                if "запрашиваемые предметы" in field.name.lower():
                    lines = field.value.split('\n')
                    
                    # Найдем и зачеркнем нужную строку
                    for j, line in enumerate(lines):
                        if line.strip() == self.item_text:
                            # Зачеркиваем предмет
                            lines[j] = f"❌ ~~{self.item_text}~~"
                            break
                    
                    # Обновляем поле
                    new_value = '\n'.join(lines)
                    embed.set_field_at(i, name=field.name, value=new_value, inline=field.inline)
                    break
            
            # Обновляем сообщение с восстановленным view
            await self.original_message.edit(embed=embed, view=original_view)
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении сообщения: {e}")
            raise


class WarehouseEditQuantityModal(discord.ui.Modal):
    """Модальное окно для изменения количества предмета"""
    
    def __init__(self, original_message: discord.Message, item_index: int,
                 item_text: str, item_name: str, current_quantity: int):
        super().__init__(title=f"Изменить: {item_name[:40]}")
        self.original_message = original_message
        self.item_index = item_index
        self.item_text = item_text
        self.item_name = item_name
        self.current_quantity = current_quantity
        
        # Поле для нового количества
        self.quantity_input = discord.ui.TextInput(
            label="Новое количество",
            placeholder=f"Текущее: {current_quantity}",
            default=str(current_quantity),
            min_length=1,
            max_length=10,
            required=True
        )
        
        self.add_item(self.quantity_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка изменения количества"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Валидация нового количества
            try:
                new_quantity = int(self.quantity_input.value.strip())
                if new_quantity <= 0:
                    await interaction.followup.send(
                        "❌ Количество должно быть больше 0!",
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.followup.send(
                    "❌ Некорректное количество! Введите число.",
                    ephemeral=True
                )
                return
            
            # Обновляем оригинальное сообщение
            await self._update_original_message_quantity(interaction, new_quantity)
            
            await interaction.followup.send(
                f"✅ Количество **{self.item_name}** изменено с {self.current_quantity} на {new_quantity}.",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"❌ Ошибка при изменении количества: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при изменении количества.",
                ephemeral=True
            )
    
    async def _update_original_message_quantity(self, interaction: discord.Interaction, new_quantity: int):
        """Обновить количество предмета в оригинальном сообщении"""
        try:
            embed = self.original_message.embeds[0]
            
            # Ищем поле с предметами
            for i, field in enumerate(embed.fields):
                if "запрашиваемые предметы" in field.name.lower():
                    lines = field.value.split('\n')
                    
                    # Найдем и обновим нужную строку
                    for j, line in enumerate(lines):
                        if line.strip() == self.item_text:
                            # Создаем новую строку с отметкой об изменении
                            import re
                            # Заменяем количество и добавляем пометку
                            match = re.match(r'(\d+\.\s*\*\*.*?\*\*)\s*[×x]\s*(\d+)', self.item_text)
                            if match:
                                item_part = match.group(1)
                                lines[j] = f"{item_part} × {new_quantity} *(из {self.current_quantity})*"
                            else:
                                # Fallback
                                lines[j] = self.item_text.replace(f"× {self.current_quantity}", f"× {new_quantity} *(из {self.current_quantity})*")
                            break
                    
                    # Обновляем поле
                    new_value = '\n'.join(lines)
                    embed.set_field_at(i, name=field.name, value=new_value, inline=field.inline)
                    break
              # Обновляем сообщение с правильно восстановленным view
            original_view = None
            
            # Определяем тип view по количеству кнопок или содержимому embed
            if self.original_message.components:
                # Определяем тип view по количеству кнопок или custom_id
                embed_text = str(embed.to_dict())
                is_multi_request = False
                for field in embed.fields:
                    if "запрашиваемые предметы" in field.name.lower() and "поз.)" in field.name:
                        is_multi_request = True
                        break
                
                # Восстанавливаем соответствующий view
                if is_multi_request:
                    original_view = WarehousePersistentMultiRequestView()
                else:
                    original_view = WarehousePersistentRequestView()
            
            await self.original_message.edit(embed=embed, view=original_view)
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении количества в сообщении: {e}")
            raise


# =================== КНОПКИ СОСТОЯНИЯ ЗАПРОСА ===================

class WarehouseStatusView(discord.ui.View):
    """View для отображения статуса запроса (кнопки Одобрено/Отказано)"""
    
    def __init__(self, status: str):
        super().__init__(timeout=None)
        self.status = status
        
        if status == "approved":
            button = discord.ui.Button(
                label="✅ Одобрено",
                style=discord.ButtonStyle.green,
                disabled=True,
                custom_id="warehouse_status_approved"
            )
        elif status == "rejected":
            button = discord.ui.Button(
                label="❌ Отклонено", 
                style=discord.ButtonStyle.red,
                disabled=True,
                custom_id="warehouse_status_rejected"
            )
        else:
            button = discord.ui.Button(
                label="⏳ В обработке",
                style=discord.ButtonStyle.gray,
                disabled=True,
                custom_id="warehouse_status_pending"
            )
        
        self.add_item(button)


# =================== VIEW ДЛЯ ПОДТВЕРЖДЕНИЯ УДАЛЕНИЯ ===================

class DeletionConfirmView(discord.ui.View):
    """View с кнопкой подтверждения удаления запроса"""
    
    def __init__(self, original_message: discord.Message):
        super().__init__(timeout=30)  # 30 секунд на подтверждение
        self.original_message = original_message
    
    @discord.ui.button(label="🗑️ Подтвердить удаление", style=discord.ButtonStyle.danger)
    async def confirm_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Подтвердить удаление запроса"""
        try:
            # Определяем, кто удаляет запрос
            if self.original_message.embeds:
                embed = self.original_message.embeds[0]
                footer_text = embed.footer.text if embed.footer else ""
                
                # Проверяем, является ли пользователь автором
                is_author = False
                if "ID пользователя:" in footer_text:
                    try:
                        author_id = int(footer_text.split("ID пользователя:")[-1].strip())
                        is_author = (author_id == interaction.user.id)
                    except (ValueError, IndexError):
                        pass
                
                # Формируем сообщение об удалении
                if is_author:
                    deletion_info = f"*Удалено автором: {interaction.user.mention}*"
                else:
                    deletion_info = f"*Удалено администратором: {interaction.user.mention}*"
            
            # Отправляем подтверждение удаления
            await interaction.response.send_message(
                f"🗑️ **Запрос склада удален**\n\n{deletion_info}",
                ephemeral=True
            )
            
            # Удаляем оригинальное сообщение
            try:
                await self.original_message.delete()
                print(f"✅ DELETE: Запрос склада удален пользователем {interaction.user.display_name}")
            except discord.NotFound:
                # Сообщение уже удалено
                pass
            except discord.Forbidden:
                await interaction.followup.send(
                    "⚠️ Нет прав для удаления сообщения. Обратитесь к администратору сервера.",
                    ephemeral=True
                )
            
        except Exception as e:
            print(f"Ошибка при удалении запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при удалении запроса.", ephemeral=True
            )
    
    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel_deletion(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отменить удаление"""
        await interaction.response.edit_message(
            content="❌ Удаление отменено.",
            embed=None,
            view=None
        )
    
    async def on_timeout(self):
        """Обработка истечения времени ожидания"""
        # Отключаем все кнопки при таймауте
        for item in self.children:
            item.disabled = True


# =================== МОДАЛЬНОЕ ОКНО ДЛЯ ПРИЧИНЫ ОТКАЗА ===================

class RejectionReasonModal(discord.ui.Modal):
    """Модальное окно для ввода причины отказа"""
    
    def __init__(self, original_message: discord.Message):
        super().__init__(title="Причина отказа")
        self.original_message = original_message
        
        self.reason_input = discord.ui.TextInput(
            label="Причина отказа",
            placeholder="Введите причину отказа в выдаче склада...",
            style=discord.TextStyle.paragraph,
            min_length=5,
            max_length=500,
            required=True
        )
        
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки причины отказа"""
        try:
            reason = self.reason_input.value.strip()
            
            # Обновление embed
            embed = self.original_message.embeds[0]
            embed.color = discord.Color.red()
            
            # Добавляем информацию об отклонении
            embed.add_field(
                name="❌ Отклонено", 
                value=f"*Отклонил: {interaction.user.mention}*\n**Причина:** {reason}", 
                inline=False
            )            # Заменяем view на кнопку статуса "Отклонено" и очищаем пинги
            status_view = WarehouseStatusView(status="rejected")
            
            await interaction.response.edit_message(content="", embed=embed, view=status_view)
            
        except Exception as e:
            print(f"Ошибка при отклонении запроса склада: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при обработке отказа.", ephemeral=True
            )


# =================== ФИНАЛЬНОЕ МОДАЛЬНОЕ ОКНО ===================

class WarehouseFinalDetailsModal(discord.ui.Modal):
    """Модальное окно для финального ввода имени и статика при отправке заявки"""
    def __init__(self, cart: WarehouseRequestCart, warehouse_manager: WarehouseManager, interaction_original: discord.Interaction, parent_view=None):
        super().__init__(title="Подтверждение заявки")
        self.cart = cart
        self.warehouse_manager = warehouse_manager
        self.interaction_original = interaction_original
        self.parent_view = parent_view  # Ссылка на родительскую view для сброса флагов
        
        # Поля формы с значениями по умолчанию
        self.name_input = discord.ui.TextInput(
            label="Имя Фамилия",
            placeholder="Введите ваше имя и фамилию",
            default="",
            min_length=3,
            max_length=50,
            required=True
        )
        
        self.static_input = discord.ui.TextInput(
            label="Статик",
            placeholder="Например: 123-456",
            default="",
            min_length=5,
            max_length=10,
            required=True
        )
        
        self.add_item(self.name_input)
        self.add_item(self.static_input)
    @classmethod
    def create_with_prefilled_data(cls, cart: WarehouseRequestCart, warehouse_manager: WarehouseManager, 
                                 interaction_original: discord.Interaction, name: str = "", static: str = "", parent_view=None):
        """
        Создать модальное окно с предзаполненными данными (быстрый метод)
        """
        instance = cls.__new__(cls)
        instance.cart = cart
        instance.warehouse_manager = warehouse_manager
        instance.interaction_original = interaction_original
        instance.parent_view = parent_view  # Ссылка на родительскую view
        
        # Инициализируем Modal
        discord.ui.Modal.__init__(instance, title="Подтверждение заявки")
        
        # Используем переданные данные
        name_value = name if name else ""
        static_value = static if static else ""
        
        # Устанавливаем placeholders
        name_placeholder = f"Данные из системы: {name}" if name_value else "Введите ваше имя и фамилию"
        static_placeholder = f"Данные из системы: {static}" if static_value else "Например: 123-456"
        
        # Поля формы
        instance.name_input = discord.ui.TextInput(
            label="Имя Фамилия",
            placeholder=name_placeholder,
            default=name_value,
            min_length=3,
            max_length=50,
            required=True
        )
        
        instance.static_input = discord.ui.TextInput(
            label="Статик",
            placeholder=static_placeholder,
            default=static_value,
            min_length=5,
            max_length=10,
            required=True
        )
        instance.add_item(instance.name_input)
        instance.add_item(instance.static_input)
        
        return instance

    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы - быстрый отклик + фоновая обработка"""
        try:
            # БЫСТРАЯ ВАЛИДАЦИЯ (без запросов к API)
            static = self._format_static(self.static_input.value.strip())
            if not static:
                await interaction.response.send_message(
                    "❌ Некорректный статик! Используйте формат: 123456 или 123-456",
                    ephemeral=True
                )
                return
            
            name = self.name_input.value.strip()
            if not name:
                await interaction.response.send_message(
                    "❌ Имя не может быть пустым!",
                    ephemeral=True
                )
                return
            
            # БЫСТРЫЙ ОТКЛИК ПОЛЬЗОВАТЕЛЮ (в пределах 3 секунд)
            await interaction.response.defer(ephemeral=True)
            
            # ФОНОВАЯ ОБРАБОТКА (тяжелые операции)
            try:
                await self._process_warehouse_request_background(interaction, name, static)
            except Exception as e:
                print(f"❌ Ошибка фоновой обработки заявки: {e}")
                await interaction.edit_original_response(
                    content="❌ Произошла ошибка при создании заявки. Попробуйте позже."
                )
            
        except Exception as e:
            print(f"❌ Ошибка при обработке модального окна: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Произошла ошибка при отправке заявки. Попробуйте позже.",
                    ephemeral=True
                )
            except:
                print("❌ Не удалось отправить сообщение об ошибке")
    
    async def _process_warehouse_request_background(self, interaction: discord.Interaction, name: str, static: str):
        """Фоновая обработка заявки склада"""
        try:
            # Берём данные пользователя из первого предмета (все предметы от одного пользователя)
            first_item = self.cart.items[0]
            
            # Обновляем все предметы в корзине
            for item in self.cart.items:
                item.user_name = name
                item.user_static = static
              # Отправляем заявку (самая тяжелая операция)
            await self._send_simple_warehouse_request(interaction)
            
            # ✅ ЗАЯВКА УСПЕШНО ОТПРАВЛЕНА В КАНАЛ - теперь устанавливаем флаг!
            if self.parent_view:
                self.parent_view.is_submitted = True
                print(f"🔒 SUBMITTED FLAG SET: Заявка отправлена, корзина заблокирована для пользователя {self.interaction_original.user.id}")
            
            # ✅ ОБНОВЛЯЕМ КОРЗИНУ: заявка отправлена, отключаем все кнопки
            await self._update_cart_after_submission(interaction)
            
            print(f"✅ PROCESS COMPLETE: Заявка успешно обработана для пользователя {self.interaction_original.user.id}")
            
        except Exception as e:
            print(f"❌ Ошибка фоновой обработки: {e}")
            import traceback
            traceback.print_exc()
            
            # Обновляем сообщение пользователю об ошибке
            await interaction.edit_original_response(
                content="❌ Произошла ошибка при создании заявки. Попробуйте позже."
            )

    async def _send_simple_warehouse_request(self, interaction: discord.Interaction):
        """Упрощенная отправка заявки склада"""
        try:
            # Получение канала отправки заявок (новая логика)
            submission_channel_id = self.warehouse_manager.get_warehouse_submission_channel()
            if not submission_channel_id:
                await interaction.edit_original_response(
                    content="❌ Канал отправки заявок склада не настроен! Обратитесь к администратору."
                )
                return

            channel = self.interaction_original.guild.get_channel(submission_channel_id)
            if not channel:
                await interaction.edit_original_response(
                    content="❌ Канал отправки заявок склада не найден! Обратитесь к администратору."
                )
                return

            # Берём данные пользователя из первого предмета
            first_item = self.cart.items[0]
            
            # 🏢 ПОЛУЧАЕМ ПОДРАЗДЕЛЕНИЕ из оптимизированного модуля
            try:
                from utils.warehouse_user_data import warehouse_user_manager
                department = await warehouse_user_manager.get_user_department(self.interaction_original.user.id)
                print(f"🏢 DEPT: Получено подразделение '{department}' для пользователя {self.interaction_original.user.id}")
            except Exception as e:
                print(f"⚠️ DEPT FALLBACK: Ошибка получения подразделения: {e}")
                department = "Не определено"            # Создание embed для заявки
            embed = discord.Embed(
                title="📦 Запрос склада",
                description=f"## {self.interaction_original.user.mention}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Информация о пользователе - ПРАВИЛЬНЫЙ ПОРЯДОК с подразделением
            embed.add_field(
                name="👤 Имя Фамилия | Статик", 
                value=f"{first_item.user_name} | {first_item.user_static}", 
                inline=False
            )
            
            # Подразделение, должность, звание в правильном порядке
            embed.add_field(name="🏢 Подразделение", value=department, inline=True)
            embed.add_field(name="📍 Должность", value=first_item.position or "Не указано", inline=True)
            embed.add_field(name="🎖️ Звание", value=first_item.rank or "Не указано", inline=True)
            
            # Добавляем пустое поле для разделения
            embed.add_field(name="\u200b", value="\u200b", inline=False)            # Список запрашиваемых предметов С номерами для финальной заявки
            items_text = ""
            for i, item in enumerate(self.cart.items, 1):
                items_text += f"{i}. **{item.item_name}** × {item.quantity}\n"
            
            embed.add_field(
                name=f"📋 Запрашиваемые предметы ({len(self.cart.items)} поз.)",
                value=items_text,
                inline=False
            )
            
            embed.set_footer(text=f"ID пользователя: {self.interaction_original.user.id}")
              # Создание view с кнопками модерации
            view = WarehousePersistentMultiRequestView()            # 📢 ПОЛУЧАЕМ ПИНГ-РОЛИ ДЛЯ УВЕДОМЛЕНИЙ
            try:
                ping_roles = self.warehouse_manager.get_ping_roles_for_warehouse_request(
                    self.interaction_original.user, department
                )
                # Форматируем пинги как мелкий текст
                ping_text = "\n".join([f"-# {role.mention}" for role in ping_roles]) if ping_roles else None
                print(f"📢 PING: Найдено {len(ping_roles)} ролей для пинга: {[role.name for role in ping_roles]}")
            except Exception as e:
                print(f"⚠️ PING ERROR: Ошибка получения пинг-ролей: {e}")
                ping_text = None # Отправка сообщения с пингами
            message = await channel.send(content=ping_text, embed=embed, view=view)
            
            print(f"✅ SIMPLE SEND: Заявка склада отправлена для пользователя {self.interaction_original.user.id}")
            
        except Exception as e:
            print(f"❌ SIMPLE SEND ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _update_cart_after_submission(self, interaction: discord.Interaction):
        """Обновить сообщения корзины после успешной отправки заявки"""
        try:
            # Получаем сообщение корзины пользователя для обновления
            cart_message = get_user_cart_message(self.interaction_original.user.id)
            
            if cart_message:
                # Создаем embed с информацией об отправленной заявке
                submitted_embed = discord.Embed(
                    title="✅ Заявка отправлена",
                    description="Заявка успешно отправлена!",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                  # Показываем краткий список отправленных предметов
                items_text = ""
                for i, item in enumerate(self.cart.items, 1):
                    items_text += f"{i}. **{item.item_name}** × {item.quantity}\n"
                
                submitted_embed.add_field(
                    name="📋 Отправленные предметы:",
                    value=items_text,
                    inline=False
                )
                
                submitted_embed.set_footer(text="Для новой заявки воспользуйтесь закреплённым сообщением")
                  # Создаем view без кнопок для статического отображения
                submitted_view = WarehouseSubmittedView()
                  # Обновляем сообщение корзины
                await cart_message.edit(embed=submitted_embed, view=submitted_view)
                print(f"✅ CART UPDATE: Обновлено сообщение корзины для пользователя {self.interaction_original.user.id}")
                  # Очищаем корзину ПОСЛЕ обновления сообщения
                clear_user_cart_safe(self.interaction_original.user.id, "successful_submission")
                print(f"🧹 CART CLEAR: Корзина очищена для пользователя {self.interaction_original.user.id}")
                
        except Exception as e:
            print(f"⚠️ CART UPDATE ERROR: Ошибка обновления корзины: {e}")            # Если не удалось обновить сообщение, всё равно очищаем корзину
            clear_user_cart_safe(self.interaction_original.user.id, "error_fallback")
            # Не критично, не прерываем процесс    async def on_timeout(self):
        """Обработчик истечения времени ожидания"""
        pass

    def _format_static(self, static: str) -> str:
        """Форматирование статика в стандартный вид"""
        
        # Удаляем все, кроме цифр
        digits = re.sub(r'\D', '', static)
        
        # Проверяем длину
        if len(digits) == 6:
            return f"{digits[:3]}-{digits[3:]}"
        elif len(digits) == 5:
            return f"{digits[:2]}-{digits[2:]}"
        
        return ""


class WarehouseSubmittedView(discord.ui.View):
    """View для уже отправленной заявки - только статическое сообщение без кнопок"""
    
    def __init__(self):
        super().__init__(timeout=None)  # Постоянный view без кнопок


# =================== МОДАЛЬНОЕ ОКНО ДЛЯ КАСТОМНОГО ПРЕДМЕТА ===================

class WarehouseCustomItemModal(discord.ui.Modal):
    """Модальное окно для кастомного предмета 'Прочее' с полем описания"""
    
    def __init__(self, category: str, warehouse_manager: WarehouseManager):
        super().__init__(title="Запрос: Прочее")
        self.category = category
        self.warehouse_manager = warehouse_manager
        
        # Поле для описания предмета (обязательное)
        self.description_input = discord.ui.TextInput(
            label="Описание предмета",
            placeholder="Укажите, что именно вы запрашиваете",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=500,
            required=True
        )
        
        # Поле для количества
        self.quantity_input = discord.ui.TextInput(
            label="Количество",
            placeholder="Введите количество предметов",
            min_length=1,
            max_length=10,
            required=True
        )
        
        self.add_item(self.description_input)
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы для кастомного предмета"""
        try:
            # ⚡ МГНОВЕННЫЙ DEFER - самое первое действие!
            await interaction.response.defer(ephemeral=True)
            
            # 🧹 Очистка старого сообщения корзины перед созданием нового loading_message
            existing_message = get_user_cart_message(interaction.user.id)
            if existing_message:
                try:
                    await existing_message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
                # Очищаем только ссылку на сообщение, но НЕ корзину
                if interaction.user.id in user_cart_messages:
                    del user_cart_messages[interaction.user.id]
            
            # 🔄 Показать быстрое сообщение о подготовке черновика
            quick_embed = discord.Embed(
                title="⏳ Подготовка формы запроса...",
                description="Добавляем кастомный предмет в корзину...",
                color=discord.Color.orange()
            )
            loading_message = await interaction.followup.send(embed=quick_embed, ephemeral=True)
            
            # ⚡ БЫСТРАЯ валидация количества (микросекунды)
            try:
                quantity = int(self.quantity_input.value.strip())
                if quantity <= 0:
                    raise ValueError("Количество должно быть больше 0")
                if quantity > 999:  # Разумный лимит для предотвращения злоупотреблений
                    raise ValueError("Слишком большое количество")
            except ValueError as e:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description=f"Некорректное количество! {str(e)}",
                    color=discord.Color.red()
                )
                await loading_message.edit(embed=error_embed)
                return

            # Валидация описания
            description = self.description_input.value.strip()
            if not description:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description="Описание предмета не может быть пустым!",
                    color=discord.Color.red()
                )
                await loading_message.edit(embed=error_embed)
                return

            # 🚀 СУПЕР БЫСТРОЕ получение данных из кэша с fallback
            print(f"⚡ ULTRA FAST: Обработка кастомного запроса для {interaction.user.display_name}")
            
            # Используем максимально быстрый путь
            position = "Не указано"
            rank = "Не указано"
            
            try:
                # Попытка получить из кэша (наиболее быстро)
                from utils.user_cache import get_cached_user_info
                user_data = await get_cached_user_info(interaction.user.id, force_refresh=False)
                
                if user_data:
                    position = user_data.get('position', 'Не указано')
                    rank = user_data.get('rank', 'Не указано')
                    print(f"✅ LIGHTNING CACHE: {position}, {rank}")
                else:
                    # Быстрый fallback через роли Discord (без обращения к БД)
                    for role in interaction.user.roles:
                        role_name = role.name.lower()
                        if "офицер" in role_name or "командир" in role_name:
                            position = "Офицер"
                            break
                        elif "сержант" in role_name:
                            rank = "Сержант"
                        elif "рядовой" in role_name:
                            rank = "Рядовой"
                    print(f"📋 ROLE FAST: {position}, {rank}")
                        
            except Exception as e:
                print(f"⚠️ Fallback для данных: {e}")
                # Используем безопасные значения по умолчанию

            # 🛡️ ПОЛУЧАЕМ КОРЗИНУ И ПРОВЕРЯЕМ СУЩЕСТВУЮЩЕЕ КОЛИЧЕСТВО
            cart = get_user_cart(interaction.user.id)
            current_time = datetime.now()
            
            # Для кастомного предмета item_name включает описание
            custom_item_name = f"Прочее ({description})"
            
            # Получаем текущее количество этого предмета в корзине
            existing_quantity = cart.get_item_quantity(self.category, custom_item_name)
            total_quantity = existing_quantity + quantity  # Суммарное количество после добавления
            
            print(f"📊 CUSTOM ITEM CHECK: {custom_item_name} - в корзине: {existing_quantity}, добавляем: {quantity}, итого: {total_quantity}")
            
            # ⚡ ВАЛИДАЦИЯ С УЧЕТОМ КОРЗИНЫ - для кастомных предметов лимиты не применяются
            category_key = self._get_category_key(self.category)
            
            # Для кастомных предметов всегда разрешаем запрос
            is_valid = True
            final_quantity = total_quantity
            validation_message = "✅ Кастомный запрос принят"
            
            # 🛒 ДОБАВЛЯЕМ В КОРЗИНУ
            cart_item = WarehouseRequestItem(
                category=self.category,
                item_name=custom_item_name,
                quantity=final_quantity - existing_quantity,  # Добавляем только разницу
                user_name="",  # Будет заполнено при отправке
                user_static="",  # Будет заполнено при отправке
                position=position,
                rank=rank
            )
            
            # Обновляем существующий предмет или добавляем новый
            if existing_quantity > 0:
                # Обновляем существующий предмет
                for item in cart.items:
                    if item.category == self.category and item.item_name == custom_item_name:
                        item.quantity = final_quantity
                        break
            else:
                # Добавляем новый предмет
                cart.add_item(cart_item)
            
            print(f"🛒 CART UPDATED: Кастомный предмет добавлен/обновлен в корзине")
              # ⚡ БЫСТРОЕ ОБНОВЛЕНИЕ КОРЗИНЫ
            await self._show_cart_ultra_fast(interaction, cart, validation_message, loading_message)
            
        except Exception as e:
            print(f"❌ Ошибка в WarehouseCustomItemModal: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                await interaction.edit_original_response(
                    content="❌ Произошла ошибка при добавлении предмета. Попробуйте позже."
                )
            except:
                pass

    async def _show_cart_ultra_fast(self, interaction: discord.Interaction, cart: WarehouseRequestCart, 
                                   validation_message: str = "", loading_message = None):
        """УЛЬТРА-БЫСТРОЕ отображение корзины для предотвращения таймаутов Discord"""
        try:
            # Формируем описание с предупреждением, если есть
            description = "Предметы готовы к отправке:"
            if validation_message:
                description += f"\n\n{validation_message}"
            
            # Создание embed для корзины
            embed = discord.Embed(
                title="🛒 Корзина складских запросов",
                description=description,
                color=discord.Color.green()
            )
            
            # Добавление всех предметов из корзины
            for i, item in enumerate(cart.items, 1):
                embed.add_field(
                    name=f"{i}. {item.item_name}",
                    value=f"**Количество:** {item.quantity}\n**Категория:** {item.category}",
                    inline=False
                )
            
            embed.add_field(
                name="📊 Статистика",
                value=f"Предметов в корзине: **{len(cart.items)}**\nОбщее количество: **{cart.get_total_items()}**",
                inline=False
            )
            
            embed.set_footer(text="Выберите действие ниже или продолжите выбор снаряжения из закреплённого сообщения")
            
            view = WarehouseCartView(cart, self.warehouse_manager)
            
            # Приоритет 1: обновляем сообщение загрузки, если оно есть
            if loading_message:
                try:
                    await loading_message.edit(embed=embed, view=view)
                    
                    # Удаляем старое сообщение корзины, если оно есть и отличается от loading_message
                    existing_message = get_user_cart_message(interaction.user.id)
                    if existing_message and existing_message.id != loading_message.id:
                        try:
                            await existing_message.delete()
                        except (discord.NotFound, discord.HTTPException):
                            pass
                    
                    # Устанавливаем loading_message как новое сообщение корзины
                    set_user_cart_message(interaction.user.id, loading_message)
                    return
                except (discord.NotFound, discord.HTTPException):
                    pass
            
            # Приоритет 2: обновляем существующее сообщение корзины
            existing_message = get_user_cart_message(interaction.user.id)
            
            if existing_message:
                try:
                    await existing_message.edit(embed=embed, view=view)
                    return
                except (discord.NotFound, discord.HTTPException):
                    pass
            
            # Приоритет 3: создаем новое сообщение корзины
            try:
                message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                set_user_cart_message(interaction.user.id, message)
            except Exception:
                await interaction.followup.send(f"✅ Добавлено: **{cart.items[-1].item_name}** × {cart.items[-1].quantity}", ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка в _show_cart_ultra_fast: {e}")
            try:
                await interaction.followup.send("✅ Предмет добавлен в корзину!", ephemeral=True)
            except:
                pass

    def _get_category_key(self, category: str) -> str:
        """Получить ключ категории"""
        category_mapping = {
            "Оружие": "оружие",
            "Бронежилеты": "бронежилеты", 
            "Медикаменты": "медикаменты",
            "Другое": "другое"
        }
        return category_mapping.get(category, "другое")
