"""
Модальные окна для системы склада
Включает в себя формы запросов, редактирования и ввода данных
"""

import re
import discord
from datetime import datetime
from utils.warehouse_manager import WarehouseManager
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
        
        # Сохраняем ПОЛНЫЕ данные пользователя для использования в on_submit
        self.user_data = user_data or {}
        
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
        
        🎯 ИСТОЧНИК ДАННЫХ: PostgreSQL через utils.user_cache.get_cached_user_info()
        Данные получаются из таблиц: personnel → employees → ranks/subdivisions/positions
        Кэширование для производительности, но данные всегда актуальные из БД
        """
        try:
            # 🔗 Четкий источник данных: PostgreSQL через систему кеширования
            from utils.user_cache import get_cached_user_info
            user_data = await get_cached_user_info(user_id)
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
            
            # Проверяем, первое ли это добавление в корзину
            cart = get_user_cart(interaction.user.id)
            is_first_item = cart.is_empty()
            
            # Создаем новое сообщение (НЕ редактируем original_response с кнопками!)
            if is_first_item:
                # Для первого предмета - создаем сообщение "Создание корзины..."
                loading_embed = discord.Embed(
                    title="📦 Создание корзины...",
                    description="Обрабатываем ваш запрос...",
                    color=discord.Color.orange()
                )
                loading_message = await interaction.followup.send(embed=loading_embed, ephemeral=True)
            else:
                # Для последующих предметов - сразу показываем обработку
                loading_message = None
            
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

            # Форматирование статика
            static = self._format_static(self.static_input.value.strip())
            if not static:
                error_embed = discord.Embed(
                    title="❌ Ошибка валидации",
                    description="Некорректный статик! Используйте формат: 123456 или 123-456",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            name = self.name_input.value.strip()
            
            # Используем сохраненные данные пользователя вместо повторного запроса
            if self.user_data:
                position = self.user_data.get('position', 'Не назначено')
                rank = self.user_data.get('rank', 'Не назначено') 
                department = self.user_data.get('department', 'Не определено')
                print(f"🔄 WAREHOUSE MODAL: Используем сохраненные данные - должность='{position}', звание='{rank}', подразделение='{department}'")
            else:
                # Если данных нет, попробуем получить из кэша/БД
                print(f"⚠️ WAREHOUSE MODAL: Нет сохраненных данных, запрашиваем из кэша/БД")
                from utils.user_cache import get_cached_user_info
                fresh_data = await get_cached_user_info(interaction.user.id)
                if fresh_data:
                    position = fresh_data.get('position', 'Не назначено')
                    rank = fresh_data.get('rank', 'Не назначено')
                    department = fresh_data.get('department', 'Не определено')
                    print(f"✅ WAREHOUSE MODAL: Получены свежие данные - должность='{position}', звание='{rank}', подразделение='{department}'")
                else:
                    position = 'Не назначено'
                    rank = 'Не назначено'
                    department = 'Не определено'
                    print(f"❌ WAREHOUSE MODAL: Не удалось получить данные пользователя, используем значения по умолчанию")
            
            # Получаем текущее состояние корзины для проверки лимитов
            cart = get_user_cart(interaction.user.id)
            
            # Валидация количества с учетом ограничений пользователя
            category_key = self._get_category_key(self.category)
            
            is_valid, corrected_quantity, validation_msg = self.warehouse_manager.validate_item_request(
                category_key, self.item_name, quantity, position, rank, cart.items
            )
            
            validation_message = ""
            item_to_add = None  # Флаг для определения, добавлять ли предмет
            
            if corrected_quantity != quantity:
                # Количество было скорректировано
                quantity = corrected_quantity
                validation_message = validation_msg
                # Создаем предмет для добавления
                item_to_add = WarehouseRequestItem(
                    category=self.category,
                    item_name=self.item_name,
                    quantity=quantity,
                    user_name=name,
                    user_static=static,
                    position=position,
                    rank=rank
                )
            elif not is_valid:
                # Полный отказ - показываем информацию в корзине
                validation_message = validation_msg
                # Предмет НЕ добавляется в корзину
            else:
                # Валидация прошла успешно
                item_to_add = WarehouseRequestItem(
                    category=self.category,
                    item_name=self.item_name,
                    quantity=quantity,
                    user_name=name,
                    user_static=static,
                    position=position,
                    rank=rank
                )
            
            # Добавляем предмет в корзину только если он создан
            if item_to_add:
                cart.add_item(item_to_add)
            
            # Показать корзину
            await self._show_cart(interaction, cart, validation_message, is_first_item=is_first_item, loading_message=loading_message)
            
        except Exception as e:
            print(f"❌ Ошибка в WarehouseRequestModal.on_submit: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при обработке запроса.",
                color=discord.Color.red()
            )
            try:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            except:
                pass

    async def _show_cart(self, interaction: discord.Interaction, cart: WarehouseRequestCart, 
                        validation_message: str = "", is_first_item: bool = False, loading_message=None):
        """Показать содержимое корзины пользователю"""
        embed = discord.Embed(
            title="📦 Ваша заявка на склад",
            description=cart.get_summary(),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        if validation_message:
            # Определяем цвет и иконку в зависимости от типа сообщения
            if "Превышен лимит" in validation_message:
                field_name = "🚫 Лимит исчерпан"
            elif "уменьшено" in validation_message:
                field_name = "⚠️ Внимание"
            else:
                field_name = "ℹ️ Информация"
            embed.add_field(name=field_name, value=validation_message, inline=False)
        
        # Добавляем специальное поле для первого предмета
        if is_first_item:
            embed.add_field(
                name="🎉 Корзина создана!",
                value="Ваш первый предмет добавлен в корзину. Теперь вы можете добавить ещё предметы или отправить заявку.",
                inline=False
            )
        
        embed.add_field(
            name="📊 Статистика",
            value=f"Предметов в корзине: **{len(cart.items)}**\nОбщее количество: **{cart.get_total_items()}**",
            inline=False
        )
        
        embed.set_footer(text="Выберите действие ниже или продолжите выбор снаряжения из закреплённого сообщения")
        
        from .views import WarehouseCartView
        view = WarehouseCartView(cart, self.warehouse_manager)
        
        # Приоритет 1: Если есть loading_message - заменяем его
        if loading_message:
            try:
                await loading_message.edit(embed=embed, view=view)
                set_user_cart_message(interaction.user.id, loading_message)
                return
            except (discord.NotFound, discord.HTTPException):
                pass
        
        # Приоритет 2: Обновляем существующее сообщение корзины
        existing_cart_message = get_user_cart_message(interaction.user.id)
        if existing_cart_message:
            try:
                await existing_cart_message.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.HTTPException):
                pass
        
        # Приоритет 3: Создаем новое сообщение корзины
        cart_message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        set_user_cart_message(interaction.user.id, cart_message)

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
    
    def __init__(self, category: str, item_name: str, warehouse_manager: WarehouseManager, user_data=None):
        super().__init__(title=f"Запрос: {item_name}")
        self.category = category
        self.item_name = item_name
        self.warehouse_manager = warehouse_manager
        
        # Сохраняем данные пользователя для использования в on_submit
        self.user_data = user_data or {}
        
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
            
            # Проверяем, первое ли это добавление в корзину
            cart = get_user_cart(interaction.user.id)
            is_first_item = cart.is_empty()
            
            # Создаем новое сообщение (НЕ редактируем original_response с кнопками!)
            if is_first_item:
                # Для первого предмета - создаем сообщение "Создание корзины..."
                loading_embed = discord.Embed(
                    title="📦 Создание корзины...",
                    description="Обрабатываем ваш запрос...",
                    color=discord.Color.orange()
                )
                loading_message = await interaction.followup.send(embed=loading_embed, ephemeral=True)
            else:
                # Для последующих предметов - сообщение будет создано позже
                loading_message = None
            
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
            # cart уже получена выше для проверки первого добавления
            
            # Используем данные из предыдущих запросов или сохраненные данные
            if cart.items:
                # Берем данные из последнего добавленного предмета
                last_item = cart.items[-1]
                user_name = last_item.user_name
                user_static = last_item.user_static
                position = last_item.position
                rank = last_item.rank
                print(f"🔄 WAREHOUSE MODAL: Используем данные из корзины - должность='{position}', звание='{rank}'")
            elif self.user_data:
                # Используем сохраненные данные из модального окна
                user_name = self.user_data.get('full_name', '')
                user_static = self.user_data.get('static', '')
                position = self.user_data.get('position', 'Не назначено')
                rank = self.user_data.get('rank', 'Не назначено')
                print(f"🔄 WAREHOUSE MODAL: Используем сохраненные данные - должность='{position}', звание='{rank}'")
            else:
                # Последний вариант - запрос из кэша/БД
                print(f"⚠️ WAREHOUSE MODAL: Корзина пуста и нет сохраненных данных, запрашиваем из кэша/БД")
                from utils.user_cache import get_cached_user_info
                fresh_data = await get_cached_user_info(interaction.user.id)
                if fresh_data:
                    user_name = fresh_data.get('full_name', '')
                    user_static = fresh_data.get('static', '')
                    position = fresh_data.get('position', 'Не назначено')
                    rank = fresh_data.get('rank', 'Не назначено')
                    print(f"✅ WAREHOUSE MODAL: Получены свежие данные - должность='{position}', звание='{rank}'")
                else:
                    user_name = ''
                    user_static = ''
                    position = 'Не назначено'
                    rank = 'Не назначено'
                    print(f"❌ WAREHOUSE MODAL: Не удалось получить данные пользователя, используем значения по умолчанию")
                  # Валидация количества с учетом ограничений пользователя
            category_key = self._get_category_key(self.category)
            is_valid, corrected_quantity, validation_msg = self.warehouse_manager.validate_item_request(
                category_key, self.item_name, quantity, position, rank, cart.items
            )
            
            validation_message = ""
            item_to_add = None  # Флаг для определения, добавлять ли предмет
            
            if corrected_quantity != quantity:
                # Количество было скорректировано
                quantity = corrected_quantity
                validation_message = validation_msg
                # Создаем предмет для добавления
                item_to_add = WarehouseRequestItem(
                    category=self.category,
                    item_name=self.item_name,
                    quantity=quantity,
                    user_name=user_name,
                    user_static=user_static,
                    position=position,
                    rank=rank
                )
            elif not is_valid:
                # Полный отказ - показываем информацию в корзине
                validation_message = validation_msg
                # Предмет НЕ добавляется в корзину
            else:
                # Валидация прошла успешно
                item_to_add = WarehouseRequestItem(
                    category=self.category,
                    item_name=self.item_name,
                    quantity=quantity,
                    user_name=user_name,
                    user_static=user_static,
                    position=position,
                    rank=rank
                )
            
            # Добавляем предмет в корзину только если он создан
            if item_to_add:
                cart.add_item(item_to_add)
            
            # Ультра-быстрое отображение корзины
            await self._show_cart_ultra_fast(interaction, cart, validation_message, is_first_item=is_first_item, loading_message=loading_message)
            
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
                                   validation_message: str = "", is_first_item: bool = False, loading_message=None):
        """УЛЬТРА-БЫСТРОЕ отображение корзины для предотвращения таймаутов Discord"""
        try:
            embed = discord.Embed(
                title="📦 Ваша заявка на склад",
                description=cart.get_summary(),
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if validation_message:
                # Определяем цвет и иконку в зависимости от типа сообщения
                if "Превышен лимит" in validation_message:
                    field_name = "🚫 Лимит исчерпан"
                elif "уменьшено" in validation_message:
                    field_name = "⚠️ Внимание"
                else:
                    field_name = "ℹ️ Информация"
                embed.add_field(name=field_name, value=validation_message, inline=False)
            
            # Добавляем специальное поле для первого предмета
            if is_first_item:
                embed.add_field(
                    name="🎉 Корзина создана!",
                    value="Ваш первый предмет добавлен в корзину. Теперь вы можете добавить ещё предметы или отправить заявку.",
                    inline=False
                )
            
            embed.add_field(
                name="📊 Статистика",
                value=f"Предметов в корзине: **{len(cart.items)}**\nОбщее количество: **{cart.get_total_items()}**",
                inline=False
            )
            embed.set_footer(text="Выберите действие ниже или продолжите выбор снаряжения из закреплённого сообщения")
            
            from .views import WarehouseCartView
            view = WarehouseCartView(cart, self.warehouse_manager)
            
            # Приоритет 1: Если есть loading_message - заменяем его
            if loading_message:
                try:
                    await loading_message.edit(embed=embed, view=view)
                    set_user_cart_message(interaction.user.id, loading_message)
                    return
                except (discord.NotFound, discord.HTTPException):
                    pass
            
            # Приоритет 2: Обновляем существующее сообщение корзины
            existing_cart_message = get_user_cart_message(interaction.user.id)
            if existing_cart_message:
                try:
                    await existing_cart_message.edit(embed=embed, view=view)
                    return
                except (discord.NotFound, discord.HTTPException):
                    # Старое сообщение недоступно, создадим новое
                    pass
            
            # Приоритет 3: Создаем новое сообщение корзины
            cart_message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            set_user_cart_message(interaction.user.id, cart_message)
            
        except Exception as e:
            print(f"❌ Ошибка в _show_cart_ultra_fast: {e}")

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
            
            # Проверяем, что корзина не пуста
            if self.cart.is_empty():
                error_embed = discord.Embed(
                    title="❌ Корзина пуста",
                    description="Корзина пуста! Добавьте предметы перед отправкой.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return
            
            # Проверка кулдауна перед отправкой
            submission_channel_id = self.warehouse_manager.get_warehouse_submission_channel()
            if submission_channel_id:
                channel = interaction.guild.get_channel(submission_channel_id)
                if channel:
                    can_request, next_time = await self.warehouse_manager.check_user_cooldown(
                        interaction.user.id, channel, interaction.user
                    )
                    if not can_request and next_time:
                        from datetime import timezone, timedelta
                        moscow_tz = timezone(timedelta(hours=3))
                        current_time_moscow = datetime.now(moscow_tz).replace(tzinfo=None)
                        time_left = next_time - current_time_moscow
                        hours = int(time_left.total_seconds() // 3600)
                        minutes = int((time_left.total_seconds() % 3600) // 60)
                        
                        error_embed = discord.Embed(
                            title="⏰ Кулдаун активен",
                            description=f"Вы можете подать следующий запрос через {hours}ч {minutes}мин",
                            color=discord.Color.orange()
                        )
                        await interaction.followup.send(embed=error_embed, ephemeral=True)
                        return
            
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
            
            # Фоновая обработка без дополнительных сообщений
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
        from utils.user_cache import get_user_department_fast
        
        item = self.cart.items[0]

        # Получаем роли для пинга через ping_manager
        from utils.ping_manager import ping_manager
        ping_roles = ping_manager.get_ping_roles_for_user(interaction.user, 'warehouse')
        
        # Получение подразделения из PostgreSQL (только для отображения в embed)
        try:
            department = await get_user_department_fast(interaction.user.id)
            print(f"🏢 DEPT: Получено подразделение '{department}' для пользователя {interaction.user.id}")
        except Exception as e:
            print(f"⚠️ DEPT FALLBACK: Ошибка получения подразделения: {e}")
            department = "Не определено"
        
        embed = discord.Embed(
            title="📦 Запрос склада",
            description=f"## {interaction.user.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Информация о пользователе в правильном порядке
        embed.add_field(name="👤 Заявитель", value=f"{item.user_name} | {item.user_static}", inline=False)
        embed.add_field(name="🏢 Подразделение", value=department, inline=True)
        
        # Добавляем должность только если она указана
        if item.position and item.position.strip() and item.position != "Не назначено":
            embed.add_field(name="📍 Должность", value=item.position, inline=True)
        
        embed.add_field(name="🎖️ Звание", value=item.rank, inline=True)
        
        # Пустое поле для разделения
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        # Список запрашиваемых предметов
        embed.add_field(
            name="📋 Запрашиваемые предметы (1 поз.)",
            value=f"1. **{item.item_name}** × {item.quantity}",
            inline=False
        )
        
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
        
        # Получаем ID канала склада и затем объект канала
        warehouse_channel_id = self.warehouse_manager.get_warehouse_submission_channel()
        if not warehouse_channel_id:
            raise Exception("Канал отправки заявок склада не настроен!")
        
        warehouse_channel = interaction.guild.get_channel(warehouse_channel_id)
        if not warehouse_channel:
            raise Exception(f"Канал склада с ID {warehouse_channel_id} не найден!")
        
        # Получаем роли для пинга на основе подразделения пользователя (уже получены ранее)
        ping_content = ""
        if ping_roles:
            ping_mentions = [f"<@&{role.id}>" for role in ping_roles]
            ping_content = f"-# {' '.join(ping_mentions)}"
        
        view = WarehousePersistentRequestView()
        await warehouse_channel.send(content=ping_content, embed=embed, view=view)

    async def _send_multi_request(self, interaction: discord.Interaction):
        """Отправить множественную заявку"""
        from forms.warehouse.persistent_views import WarehousePersistentMultiRequestView
        from utils.user_cache import get_user_department_fast
        
        first_item = self.cart.items[0]

        # Получаем роли для пинга через ping_manager
        from utils.ping_manager import ping_manager
        ping_roles = ping_manager.get_ping_roles_for_user(interaction.user, 'warehouse')
        
        # Получение подразделения из PostgreSQL (только для отображения в embed)
        try:
            department = await get_user_department_fast(interaction.user.id)
            print(f"🏢 DEPT: Получено подразделение '{department}' для пользователя {interaction.user.id}")
        except Exception as e:
            print(f"⚠️ DEPT FALLBACK: Ошибка получения подразделения: {e}")
            department = "Не определено"
        
        embed = discord.Embed(
            title="📦 Запрос склада",
            description=f"## {interaction.user.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Информация о пользователе в правильном порядке
        embed.add_field(name="👤 Заявитель", value=f"{first_item.user_name} | {first_item.user_static}", inline=False)
        embed.add_field(name="🏢 Подразделение", value=department, inline=True)
        
        # Добавляем должность только если она указана
        if first_item.position and first_item.position.strip() and first_item.position != "Не назначено":
            embed.add_field(name="📍 Должность", value=first_item.position, inline=True)
        
        embed.add_field(name="🎖️ Звание", value=first_item.rank, inline=True)
        
        # Пустое поле для разделения
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        # Добавляем список предметов
        items_text = ""
        for i, item in enumerate(self.cart.items, 1):
            items_text += f"{i}. **{item.item_name}** × {item.quantity}\n"
        
        embed.add_field(
            name=f"📋 Запрашиваемые предметы ({len(self.cart.items)} поз.)",
            value=items_text,
            inline=False
        )
        
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
        
        # Получаем ID канала склада и затем объект канала
        warehouse_channel_id = self.warehouse_manager.get_warehouse_submission_channel()
        if not warehouse_channel_id:
            raise Exception("Канал отправки заявок склада не настроен!")
        
        warehouse_channel = interaction.guild.get_channel(warehouse_channel_id)
        if not warehouse_channel:
            raise Exception(f"Канал склада с ID {warehouse_channel_id} не найден!")
        
        # Получаем роли для пинга на основе подразделения пользователя (уже получены ранее)
        ping_content = ""
        if ping_roles:
            ping_mentions = [f"<@&{role.id}>" for role in ping_roles]
            ping_content = f"-# {' '.join(ping_mentions)}"
        
        view = WarehousePersistentMultiRequestView()
        await warehouse_channel.send(content=ping_content, embed=embed, view=view)

    async def _update_cart_after_submission(self, interaction: discord.Interaction):
        """Обновить корзину после отправки заявки"""
        try:
            # Получаем сообщение корзины для обновления
            cart_message = get_user_cart_message(interaction.user.id)
            
            # Очищаем корзину
            clear_user_cart_safe(interaction.user.id, "submission_completed")
            
            # Обновляем сообщение корзины с информацией об успешной отправке
            success_embed = discord.Embed(
                title="✅ Заявка отправлена!",
                description="Ваша заявка на склад успешно отправлена на рассмотрение модераторам.",
                color=discord.Color.green()
            )
            
            # Обновляем сообщение корзины без кнопок
            if cart_message:
                try:
                    await cart_message.edit(embed=success_embed, view=None)
                except (discord.NotFound, discord.HTTPException):
                    # Если сообщение корзины недоступно, обновляем основной ответ
                    await interaction.edit_original_response(embed=success_embed)
            else:
                # Если нет сообщения корзины, обновляем основной ответ
                await interaction.edit_original_response(embed=success_embed)
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении корзины после отправки: {e}")
            # В случае ошибки просто показываем успех через основной ответ
            try:
                success_embed = discord.Embed(
                    title="✅ Заявка отправлена!",
                    description="Ваша заявка на склад успешно отправлена на рассмотрение модераторам.",
                    color=discord.Color.green()
                )
                await interaction.edit_original_response(embed=success_embed)
            except:
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


class WarehouseCustomItemModal(discord.ui.Modal):
    """Модальное окно для кастомного предмета 'Прочее' с полем описания"""
    
    def __init__(self, category: str, warehouse_manager: WarehouseManager, user_data=None):
        super().__init__(title="Запрос кастомного предмета")
        self.category = category
        self.warehouse_manager = warehouse_manager
        
        # Сохраняем данные пользователя для использования в on_submit
        self.user_data = user_data or {}
        
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
            
            # Проверяем, первое ли это добавление в корзину
            cart = get_user_cart(interaction.user.id)
            is_first_item = cart.is_empty()
            
            # Создаем новое сообщение (НЕ редактируем original_response с кнопками!)
            if is_first_item:
                # Для первого предмета - создаем сообщение "Создание корзины..."
                loading_embed = discord.Embed(
                    title="📦 Создание корзины...",
                    description="Обрабатываем ваш запрос...",
                    color=discord.Color.orange()
                )
                loading_message = await interaction.followup.send(embed=loading_embed, ephemeral=True)
            else:
                # Для последующих предметов - сообщение будет создано позже
                loading_message = None
            
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
            
            # Получаем данные пользователя из корзины или сохраненных данных
            cart = get_user_cart(interaction.user.id)
            
            if cart.items:
                # Используем данные из корзины
                last_item = cart.items[-1]
                user_name = last_item.user_name
                user_static = last_item.user_static
                position = last_item.position
                rank = last_item.rank
                print(f"🔄 WAREHOUSE CUSTOM MODAL: Используем данные из корзины - должность='{position}', звание='{rank}'")
            elif self.user_data:
                # Используем сохраненные данные из модального окна
                user_name = self.user_data.get('full_name', '')
                user_static = self.user_data.get('static', '')
                position = self.user_data.get('position', 'Не назначено')
                rank = self.user_data.get('rank', 'Не назначено')
                print(f"🔄 WAREHOUSE CUSTOM MODAL: Используем сохраненные данные - должность='{position}', звание='{rank}'")
            else:
                # Последний вариант - запрос из кэша/БД
                print(f"⚠️ WAREHOUSE CUSTOM MODAL: Корзина пуста и нет сохраненных данных, запрашиваем из кэша/БД")
                from utils.user_cache import get_cached_user_info
                fresh_data = await get_cached_user_info(interaction.user.id)
                if fresh_data:
                    user_name = fresh_data.get('full_name', '')
                    user_static = fresh_data.get('static', '')
                    position = fresh_data.get('position', 'Не назначено')
                    rank = fresh_data.get('rank', 'Не назначено')
                    print(f"✅ WAREHOUSE CUSTOM MODAL: Получены свежие данные - должность='{position}', звание='{rank}'")
                else:
                    user_name = ''
                    user_static = ''
                    position = 'Не назначено'
                    rank = 'Не назначено'
                    print(f"❌ WAREHOUSE CUSTOM MODAL: Не удалось получить данные пользователя, используем значения по умолчанию")
            
            # Валидация с учетом корзины
            category_key = self._get_category_key(self.category)
            is_valid, corrected_quantity, validation_msg = self.warehouse_manager.validate_item_request(
                category_key, item_name, quantity, position, rank, cart.items
            )
            
            validation_message = ""
            item_to_add = None  # Флаг для определения, добавлять ли предмет
            
            if corrected_quantity != quantity:
                # Количество было скорректировано
                quantity = corrected_quantity
                validation_message = validation_msg
                # Создаем предмет для добавления
                item_to_add = WarehouseRequestItem(
                    category=self.category,
                    item_name=item_name,
                    quantity=quantity,
                    user_name=user_name,
                    user_static=user_static,
                    position=position,
                    rank=rank
                )
            elif not is_valid:
                # Полный отказ - показываем информацию в корзине
                validation_message = validation_msg
                # Предмет НЕ добавляется в корзину
            else:
                # Валидация прошла успешно
                item_to_add = WarehouseRequestItem(
                    category=self.category,
                    item_name=item_name,
                    quantity=quantity,
                    user_name=user_name,
                    user_static=user_static,
                    position=position,
                    rank=rank
                )
            
            # Добавляем предмет в корзину только если он создан
            if item_to_add:
                cart.add_item(item_to_add)
            
            # Показать корзину
            await self._show_cart_ultra_fast(interaction, cart, validation_message, is_first_item=is_first_item, loading_message=loading_message)
            
        except Exception as e:
            print(f"❌ Ошибка в WarehouseCustomItemModal.on_submit: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при обработке запроса",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    async def _show_cart_ultra_fast(self, interaction: discord.Interaction, cart: WarehouseRequestCart, 
                                   validation_message: str = "", is_first_item: bool = False, loading_message=None):
        """Быстрое отображение корзины для кастомных предметов"""
        try:
            embed = discord.Embed(
                title="📦 Ваша заявка на склад",
                description=cart.get_summary(),
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if validation_message:
                # Определяем цвет и иконку в зависимости от типа сообщения
                if "Превышен лимит" in validation_message:
                    field_name = "🚫 Лимит исчерпан"
                elif "уменьшено" in validation_message:
                    field_name = "⚠️ Внимание"
                else:
                    field_name = "ℹ️ Информация"
                embed.add_field(name=field_name, value=validation_message, inline=False)
            
            # Добавляем специальное поле для первого предмета
            if is_first_item:
                embed.add_field(
                    name="🎉 Корзина создана!",
                    value="Ваш первый предмет добавлен в корзину. Теперь вы можете добавить ещё предметы или отправить заявку.",
                    inline=False
                )
            
            embed.add_field(
                name="📊 Статистика",
                value=f"Предметов в корзине: **{len(cart.items)}**\nОбщее количество: **{cart.get_total_items()}**",
                inline=False
            )
            embed.set_footer(text="Выберите действие ниже или продолжите выбор снаряжения из закреплённого сообщения")
            
            from .views import WarehouseCartView
            view = WarehouseCartView(cart, self.warehouse_manager)
            
            # Приоритет 1: Если есть loading_message - заменяем его
            if loading_message:
                try:
                    await loading_message.edit(embed=embed, view=view)
                    set_user_cart_message(interaction.user.id, loading_message)
                    return
                except (discord.NotFound, discord.HTTPException):
                    pass
            
            # Приоритет 2: Обновляем существующее сообщение корзины
            existing_cart_message = get_user_cart_message(interaction.user.id)
            if existing_cart_message:
                try:
                    await existing_cart_message.edit(embed=embed, view=view)
                    return
                except (discord.NotFound, discord.HTTPException):
                    # Старое сообщение недоступно, создадим новое
                    pass
            
            # Приоритет 3: Создаем новое сообщение корзины
            cart_message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            set_user_cart_message(interaction.user.id, cart_message)
            
        except Exception as e:
            print(f"❌ Ошибка в _show_cart_ultra_fast: {e}")

    def _get_category_key(self, category: str) -> str:
        """Получить ключ категории"""
        category_mapping = {
            "Оружие": "оружие",
            "Бронежилеты": "бронежилеты", 
            "Медикаменты": "медикаменты",
            "Другое": "другое"
        }
        return category_mapping.get(category, "другое")
