"""
Модальные окна для системы склада
Включает в себя формы запросов, редактирования и ввода данных
"""

import re
import discord
from datetime import datetime
from typing import Optional
from utils.warehouse_manager import WarehouseManager
from utils.user_database import UserDatabase
from .cart import (
    WarehouseRequestItem, WarehouseRequestCart, get_user_cart, 
    clear_user_cart_safe, get_user_cart_message, set_user_cart_message
)


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
            
            # Валидация количества с учетом доступного склада
            category_key = self._get_category_key(self.category)
            
            validation_result = await self.warehouse_manager.validate_warehouse_request(
                category_key, self.item_name, quantity
            )
            
            validation_message = ""
            if not validation_result.get('valid', True):
                if validation_result.get('adjusted', False):
                    # Корректируем количество до доступного
                    quantity = validation_result.get('available_quantity', quantity)
                    validation_message = f"⚠️ Количество **{self.item_name}** уменьшено до {quantity} (доступный остаток)"
                else:
                    # Полный отказ
                    error_embed = discord.Embed(
                        title="❌ Недостаточно снаряжения на складе",
                        description=validation_result.get('message', 'Недостаточно снаряжения'),
                        color=discord.Color.red()
                    )
                    await interaction.edit_original_response(embed=error_embed)
                    return
            
            # Создание объекта предмета
            item = WarehouseRequestItem(
                category=self.category,
                item_name=self.item_name,
                quantity=quantity,
                user_name=name,
                user_static=static,
                position=position,
                rank=rank
            )
            
            # Добавление в корзину
            cart = get_user_cart(interaction.user.id)
            cart.add_item(item)
            
            # Показать корзину
            await self._show_cart(interaction, cart, validation_message)
            
        except Exception as e:
            print(f"❌ Ошибка в WarehouseRequestModal.on_submit: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при обработке запроса.",
                color=discord.Color.red()
            )
            try:
                await interaction.edit_original_response(embed=error_embed)
            except:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

    async def _show_cart(self, interaction: discord.Interaction, cart: WarehouseRequestCart, validation_message: str = ""):
        """Показать содержимое корзины пользователю"""
        embed = discord.Embed(
            title="📦 Ваша заявка на склад",
            description=cart.get_summary(),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if validation_message and "уменьшено" in validation_message:
            embed.add_field(name="⚠️ Внимание", value=validation_message, inline=False)
        
        embed.add_field(
            name="📊 Статистика",
            value=f"Предметов в корзине: **{len(cart.items)}**\nОбщее количество: **{cart.get_total_items()}**",
            inline=False
        )
        
        embed.set_footer(text="Выберите действие ниже или продолжите выбор снаряжения из закреплённого сообщения")
        
        from .views import WarehouseCartView
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
        try:            
            await interaction.response.defer(ephemeral=True)
            
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
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            # Быстрое получение информации пользователя из предыдущих данных корзины
            cart = get_user_cart(interaction.user.id)
            
            # Используем данные из предыдущих запросов или базовые
            if cart.items:
                # Берем данные из последнего добавленного предмета
                last_item = cart.items[-1]
                user_name = last_item.user_name
                user_static = last_item.user_static
                position = last_item.position
                rank = last_item.rank
            else:
                # Базовые данные, если корзина пуста
                user_info = await self.warehouse_manager.get_user_info(interaction.user)
                user_name, user_static, position, rank = user_info
                
            # Валидация склада
            category_key = self._get_category_key(self.category)
            validation_result = await self.warehouse_manager.validate_warehouse_request(
                category_key, self.item_name, quantity
            )
            
            validation_message = ""
            if not validation_result.get('valid', True):
                if validation_result.get('adjusted', False):
                    quantity = validation_result.get('available_quantity', quantity)
                    validation_message = f"⚠️ Количество **{self.item_name}** уменьшено до {quantity} (доступный остаток)"
                else:
                    error_embed = discord.Embed(
                        title="❌ Недостаточно снаряжения на складе",
                        description=validation_result.get('message', 'Недостаточно снаряжения'),
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                    return
            
            # Создание и добавление предмета
            item = WarehouseRequestItem(
                category=self.category,
                item_name=self.item_name,
                quantity=quantity,
                user_name=user_name,
                user_static=user_static,
                position=position,
                rank=rank
            )
            
            cart.add_item(item)
            
            # Ультра-быстрое отображение корзины
            await self._show_cart_ultra_fast(interaction, cart, validation_message)
            
        except Exception as e:
            print(f"❌ Ошибка в WarehouseQuantityModal.on_submit: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при обработке запроса.",
                color=discord.Color.red()
            )
            try:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            except:
                pass

    async def _show_cart_ultra_fast(self, interaction: discord.Interaction, cart: WarehouseRequestCart, 
                                   validation_message: str = "", loading_message = None):
        """УЛЬТРА-БЫСТРОЕ отображение корзины для предотвращения таймаутов Discord"""
        try:
            embed = discord.Embed(
                title="📦 Ваша заявка на склад",
                description=cart.get_summary(),
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if validation_message:
                embed.add_field(name="⚠️ Внимание", value=validation_message, inline=False)
            
            embed.add_field(
                name="📊 Статистика",
                value=f"Предметов в корзине: **{len(cart.items)}**\nОбщее количество: **{cart.get_total_items()}**",
                inline=False
            )
            embed.set_footer(text="Выберите действие ниже или продолжите выбор снаряжения из закреплённого сообщения")
            
            from .views import WarehouseCartView
            view = WarehouseCartView(cart, self.warehouse_manager)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Ошибка в _show_cart_ultra_fast: {e}")
            # Fallback: минимальное сообщение
            await interaction.followup.send(
                f"✅ **{self.item_name}** добавлен в корзину!",
                ephemeral=True
            )

    def _get_category_key(self, category: str) -> str:
        """Получить ключ категории"""
        category_mapping = {
            "Оружие": "оружие",
            "Бронежилеты": "бронежилеты", 
            "Медикаменты": "медикаменты",
            "Другое": "другое"
        }
        return category_mapping.get(category, "другое")


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
                    raise ValueError("Номер позиции вне диапазона")
            except ValueError:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description=f"Некорректный номер позиции! Введите число от 1 до {len(self.cart.items)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return
            
            # Удаляем предмет (конвертируем в 0-based индекс)
            item_index = item_number - 1
            removed_item = self.cart.items[item_index]
            success = self.cart.remove_item_by_index(item_index)
            
            if success:
                success_embed = discord.Embed(
                    title="✅ Предмет удален",
                    description=f"Удален: **{removed_item.item_name}** × {removed_item.quantity}",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=success_embed, ephemeral=True)
                
                # Обновляем отображение корзины
                await self._update_cart_display(interaction)
            else:
                error_embed = discord.Embed(
                    title="❌ Ошибка удаления",
                    description="Не удалось удалить предмет из корзины",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                
        except Exception as e:
            print(f"❌ Ошибка при удалении предмета по номеру: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при удалении предмета",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    
    async def _update_cart_display(self, interaction: discord.Interaction):
        """Обновить отображение корзины после удаления"""
        try:
            # Получаем сообщение корзины для обновления
            cart_message = get_user_cart_message(interaction.user.id)
            
            if cart_message and self.cart.items:
                # Обновляем существующее сообщение корзины
                updated_embed = discord.Embed(
                    title="📦 Ваша заявка на склад",
                    description=self.cart.get_summary(),
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                
                updated_embed.add_field(
                    name="📊 Статистика",
                    value=f"Предметов в корзине: **{len(self.cart.items)}**\nОбщее количество: **{self.cart.get_total_items()}**",
                    inline=False
                )
                updated_embed.set_footer(text="Выберите действие ниже или продолжите выбор снаряжения из закреплённого сообщения")
                
                from .views import WarehouseCartView
                view = WarehouseCartView(self.cart, self.warehouse_manager)
                await cart_message.edit(embed=updated_embed, view=view)
                
        except Exception as e:
            print(f"❌ Ошибка при обновлении отображения корзины: {e}")


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
        """Создать модальное окно с предзаполненными данными"""
        modal = cls(cart, warehouse_manager, interaction_original, parent_view)
        modal.name_input.default = name
        modal.static_input.default = static
        return modal

    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы - быстрый отклик + фоновая обработка"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            name = self.name_input.value.strip()
            static = self._format_static(self.static_input.value.strip())
            
            if not static:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description="Некорректный статик! Используйте формат: 123456 или 123-456",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return
            
            # Мгновенный отклик пользователю
            loading_embed = discord.Embed(
                title="⏳ Отправка заявки...",
                description="Обрабатываем вашу заявку на склад, пожалуйста подождите...",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=loading_embed, ephemeral=True)
            
            # Фоновая обработка
            await self._process_warehouse_request_background(interaction, name, static)
            
        except Exception as e:
            print(f"❌ Ошибка в WarehouseFinalDetailsModal.on_submit: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при отправке заявки",
                color=discord.Color.red()
            )
            try:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            except:
                pass
    
    async def _process_warehouse_request_background(self, interaction: discord.Interaction, name: str, static: str):
        """Фоновая обработка отправки заявки на склад"""
        try:
            # Обновляем данные всех предметов в корзине
            for item in self.cart.items:
                item.user_name = name
                item.user_static = static
            
            # Отправляем заявку
            await self._send_simple_warehouse_request(interaction)
            
            # Очищаем корзину и обновляем интерфейс
            await self._update_cart_after_submission(interaction)
            
        except Exception as e:
            print(f"❌ Ошибка при фоновой обработке заявки: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка отправки",
                description="Произошла ошибка при отправке заявки на склад",
                color=discord.Color.red()
            )
            try:
                await interaction.edit_original_response(embed=error_embed)
            except:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

    async def _send_simple_warehouse_request(self, interaction: discord.Interaction):
        """Отправить простую заявку на склад"""
        from forms.warehouse.persistent_views import WarehousePersistentRequestView, WarehousePersistentMultiRequestView
        
        # Если один предмет - простая заявка, если несколько - множественная
        if len(self.cart.items) == 1:
            await self._send_single_request(interaction)
        else:
            await self._send_multi_request(interaction)

    async def _send_single_request(self, interaction: discord.Interaction):
        """Отправить одиночную заявку"""
        from forms.warehouse.persistent_views import WarehousePersistentRequestView
        
        item = self.cart.items[0]
        
        embed = discord.Embed(
            title="📦 Новая заявка на склад",
            description=f"**{item.item_name}** × {item.quantity}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="👤 Заявитель", value=f"{item.user_name} ({item.user_static})", inline=True)
        embed.add_field(name="🎖️ Звание", value=item.rank, inline=True)
        embed.add_field(name="💼 Должность", value=item.position, inline=True)
        embed.add_field(name="📂 Категория", value=item.category, inline=True)
        
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
        
        # Отправляем в канал склада
        warehouse_channel = await self.warehouse_manager.get_warehouse_channel(interaction.guild)
        if warehouse_channel:
            view = WarehousePersistentRequestView()
            await warehouse_channel.send(embed=embed, view=view)

    async def _send_multi_request(self, interaction: discord.Interaction):
        """Отправить множественную заявку"""
        from forms.warehouse.persistent_views import WarehousePersistentMultiRequestView
        
        first_item = self.cart.items[0]
        
        embed = discord.Embed(
            title="📦 Новая множественная заявка на склад",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Добавляем список предметов
        items_text = ""
        for i, item in enumerate(self.cart.items, 1):
            items_text += f"{i}. **{item.item_name}** × {item.quantity}\n"
        
        embed.add_field(
            name=f"📋 Запрашиваемые предметы ({len(self.cart.items)} поз.)",
            value=items_text,
            inline=False
        )
        
        embed.add_field(name="👤 Заявитель", value=f"{first_item.user_name} ({first_item.user_static})", inline=True)
        embed.add_field(name="🎖️ Звание", value=first_item.rank, inline=True)
        embed.add_field(name="💼 Должность", value=first_item.position, inline=True)
        
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
        
        # Отправляем в канал склада
        warehouse_channel = await self.warehouse_manager.get_warehouse_channel(interaction.guild)
        if warehouse_channel:
            view = WarehousePersistentMultiRequestView()
            await warehouse_channel.send(embed=embed, view=view)

    async def _update_cart_after_submission(self, interaction: discord.Interaction):
        """Обновить корзину после отправки заявки"""
        try:
            # Очищаем корзину
            clear_user_cart_safe(interaction.user.id, "submission_completed")
            
            # Обновляем интерфейс
            success_embed = discord.Embed(
                title="✅ Заявка отправлена!",
                description="Ваша заявка на склад успешно отправлена на рассмотрение модераторам.",
                color=discord.Color.green()
            )
            
            await interaction.edit_original_response(embed=success_embed)
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении корзины после отправки: {e}")

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


class WarehouseCustomItemModal(discord.ui.Modal):
    """Модальное окно для кастомного предмета 'Прочее' с полем описания"""
    
    def __init__(self, category: str, warehouse_manager: WarehouseManager):
        super().__init__(title="Запрос кастомного предмета")
        self.category = category
        self.warehouse_manager = warehouse_manager
        
        # Поле для названия предмета
        self.item_name_input = discord.ui.TextInput(
            label="Название предмета",
            placeholder="Введите название предмета...",
            min_length=2,
            max_length=100,
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
        
        self.add_item(self.item_name_input)
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы кастомного предмета"""
        try:
            await interaction.response.defer(ephemeral=True)
            
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
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            item_name = self.item_name_input.value.strip()
            
            # Получаем данные пользователя из корзины или базы
            cart = get_user_cart(interaction.user.id)
            
            if cart.items:
                # Используем данные из корзины
                last_item = cart.items[-1]
                user_name = last_item.user_name
                user_static = last_item.user_static
                position = last_item.position
                rank = last_item.rank
            else:
                # Получаем из базы
                user_info = await self.warehouse_manager.get_user_info(interaction.user)
                user_name, user_static, position, rank = user_info
            
            # Создание предмета
            item = WarehouseRequestItem(
                category=self.category,
                item_name=item_name,
                quantity=quantity,
                user_name=user_name,
                user_static=user_static,
                position=position,
                rank=rank
            )
            
            cart.add_item(item)
            
            # Показать корзину
            await self._show_cart_ultra_fast(interaction, cart)
            
        except Exception as e:
            print(f"❌ Ошибка в WarehouseCustomItemModal.on_submit: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при обработке запроса",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    async def _show_cart_ultra_fast(self, interaction: discord.Interaction, cart: WarehouseRequestCart, 
                                   validation_message: str = "", loading_message = None):
        """Быстрое отображение корзины"""
        try:
            embed = discord.Embed(
                title="📦 Ваша заявка на склад",
                description=cart.get_summary(),
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 Статистика",
                value=f"Предметов в корзине: **{len(cart.items)}**\nОбщее количество: **{cart.get_total_items()}**",
                inline=False
            )
            embed.set_footer(text="Выберите действие ниже или продолжите выбор снаряжения из закреплённого сообщения")
            
            from .views import WarehouseCartView
            view = WarehouseCartView(cart, self.warehouse_manager)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Ошибка в _show_cart_ultra_fast: {e}")
            await interaction.followup.send(f"✅ **{self.item_name_input.value}** добавлен в корзину!", ephemeral=True)

    def _get_category_key(self, category: str) -> str:
        """Получить ключ категории"""
        category_mapping = {
            "Оружие": "оружие",
            "Бронежилеты": "бронежилеты", 
            "Медикаменты": "медикаменты",
            "Другое": "другое"
        }
        return category_mapping.get(category, "другое")
