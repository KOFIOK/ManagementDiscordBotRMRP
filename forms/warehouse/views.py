"""
Представления (Views) для системы склада
Включает в себя выбор категорий, предметов, управление корзиной и подтверждения
"""

import asyncio
import discord
from datetime import datetime, timezone, timedelta
from typing import Dict
from utils.warehouse_manager import WarehouseManager
from .cart import WarehouseRequestCart, get_user_cart, clear_user_cart_safe, get_user_cart_message, user_cart_messages


class WarehouseCategorySelect(discord.ui.Select):
    """Выбор категории склада"""
    
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
                        interaction.user.id, channel, interaction.user
                    )
                    
                    if not can_request and next_time:
                        # next_time уже в московском времени из warehouse_manager
                        moscow_tz = timezone(timedelta(hours=3))  # UTC+3 для Москвы
                        current_time_moscow = datetime.now(moscow_tz).replace(tzinfo=None)
                        time_left = next_time - current_time_moscow
                        hours = int(time_left.total_seconds() // 3600)
                        minutes = int((time_left.total_seconds() % 3600) // 60)
                        
                        await interaction.response.send_message(
                            f"⏰ Кулдаун! Вы можете подать следующий запрос через {hours}ч {minutes}мин",
                            ephemeral=True
                        )
                        return
            
            # Преобразование value в полное название категории
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
    """View для выбора конкретного предмета"""
    
    def __init__(self, category: str, category_info: Dict, warehouse_manager: WarehouseManager):
        super().__init__(timeout=None)  # 5 минут таймаут для выбора предмета
        self.category = category
        self.category_info = category_info
        self.warehouse_manager = warehouse_manager
        
        # Добавление кнопок для каждого предмета
        items = category_info["items"]
        for i, item in enumerate(items):
            if i < 20:  # Максимум 20 кнопок (4 ряда по 5)
                # Делаем custom_id уникальным для каждой категории!
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
        """Создать callback для кнопки предмета"""        # ВАЖНО: захватываем значения по значению, а не по ссылке!
        category = self.category
        warehouse_manager = self.warehouse_manager
        
        async def callback(interaction: discord.Interaction):
            # ОТЛАДКА: выводим что именно открываем
            print(f"🔍 CALLBACK: Пользователь {interaction.user.display_name} нажал '{item_name}' в категории '{category}'")
            
            # Специальная обработка для кастомного предмета "Прочее"
            if item_name == "Прочее":
                from .modals import WarehouseCustomItemModal
                modal = WarehouseCustomItemModal(category, warehouse_manager)
            else:
                # Создание упрощенного модального окна только для количества
                from .modals import WarehouseQuantityModal
                modal = WarehouseQuantityModal(category, item_name, warehouse_manager)
            await interaction.response.send_modal(modal)
            
        return callback


class WarehousePinMessageView(discord.ui.View):
    """View для закрепленного сообщения склада"""
    
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
                        interaction.user.id, channel, interaction.user
                    )
                    if not can_request and next_time:
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
                from .modals import WarehouseFinalDetailsModal
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
                    from .modals import WarehouseFinalDetailsModal
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
        
        from .modals import RemoveItemByNumberModal
        modal = RemoveItemByNumberModal(self.cart, self.warehouse_manager)
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
                ephemeral=True
            )


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
            # Очищаем корзину
            self.cart.clear()
            
            # Безопасно очищаем отслеживание
            clear_user_cart_safe(interaction.user.id, "пользователь подтвердил очистку")
            
            success_embed = discord.Embed(
                title="✅ Корзина очищена",
                description="Все предметы удалены из корзины.\n\nДля новых запросов используйте закрепленное сообщение склада.",
                color=discord.Color.green()
            )
            
            # Обновляем ephemeral сообщение
            await interaction.response.edit_message(embed=success_embed, view=None)
            
            # Автоматически удаляем сообщение через 5 секунд
            asyncio.create_task(self._auto_delete_message(interaction.message))
            
            # Обновляем исходное сообщение корзины
            cart_message = get_user_cart_message(interaction.user.id)
            if cart_message:
                try:
                    empty_embed = discord.Embed(
                        title="📦 Корзина очищена",
                        description="Все предметы удалены из корзины.\n\nДля новых запросов используйте закрепленное сообщение склада.",
                        color=discord.Color.blue()
                    )
                    empty_embed.set_footer(text="Сообщение автоматически исчезнет через 10 секунд")
                    
                    await cart_message.edit(embed=empty_embed, view=None)
                    
                    # Удаляем сообщение корзины через 10 секунд
                    await asyncio.sleep(10)
                    try:
                        await cart_message.delete()
                    except:
                        pass
                        
                except (discord.NotFound, discord.HTTPException):
                    pass  # Сообщение уже удалено или недоступно
                    
        except Exception as e:
            print(f"❌ Ошибка при очистке корзины: {e}")
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при очистке корзины",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=error_embed, view=None)
    
    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отменить очистку корзины"""
        cancel_embed = discord.Embed(
            title="❌ Очистка отменена",
            description="Корзина не была изменена.",
            color=discord.Color.blue()
        )
        
        await interaction.response.edit_message(embed=cancel_embed, view=None)
        asyncio.create_task(self._auto_delete_message(interaction.message))
    
    async def _auto_delete_message(self, message):
        """Автоматически удалить сообщение через 10 секунд"""
        await asyncio.sleep(10)
        try:
            await message.delete()
        except:
            pass  # Игнорируем ошибки удаления


class WarehouseSubmittedView(discord.ui.View):
    """View для уже отправленной заявки - только статическое сообщение без кнопок"""
    
    def __init__(self):
        super().__init__(timeout=None)
        # Пустая view - только для статического отображения
