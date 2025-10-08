"""
Представления (Views) для системы склада
Включает в себя выбор категорий, предметов, управление корзиной и подтверждения
"""

import asyncio
import discord
from datetime import datetime, timezone, timedelta
from typing import Dict
from utils.warehouse_manager import WarehouseManager
from .cart import WarehouseRequestCart, clear_user_cart_safe, get_user_cart_message, user_cart_messages


async def safe_interaction_response(interaction: discord.Interaction, content: str = None, embed: discord.Embed = None, 
                                  view: discord.ui.View = None, file: discord.File = None, ephemeral: bool = True):
    """
    Безопасная отправка ответа на интеракцию с защитой от истёкших интеракций
    """
    try:
        # Подготавливаем параметры, исключая None значения
        kwargs = {"ephemeral": ephemeral}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view
        if file is not None:
            kwargs["file"] = file
            
        if not interaction.response.is_done():
            await interaction.response.send_message(**kwargs)
        else:
            # Интеракция уже была обработана, используем followup
            await interaction.followup.send(**kwargs)
    except discord.NotFound as e:
        if e.code == 10062:  # Unknown interaction
            print(f"⚠️ INTERACTION EXPIRED: Истекла интеракция для {interaction.user.display_name}")
            return False
        else:
            raise
    except Exception as e:
        print(f"❌ Ошибка при отправке ответа на интеракцию: {e}")
        import traceback
        traceback.print_exc()
        return False
    return True


async def safe_modal_response(interaction: discord.Interaction, modal: discord.ui.Modal):
    """
    Безопасная отправка модального окна с защитой от истёкших интеракций
    """
    try:
        if modal is None:
            print(f"❌ MODAL ERROR: Модальное окно равно None для {interaction.user.display_name}")
            return False
            
        if not interaction.response.is_done():
            await interaction.response.send_modal(modal)
            return True
        else:
            print(f"⚠️ INTERACTION: Интеракция уже была обработана для {interaction.user.display_name}")
            # Для модальных окон followup не работает, отправляем уведомление
            try:
                await interaction.followup.send(
                    "⚠️ Интеракция истекла. Попробуйте выбрать предмет заново.",
                    ephemeral=True
                )
            except:
                pass
            return False
    except discord.NotFound as e:
        if e.code == 10062:  # Unknown interaction
            print(f"⚠️ INTERACTION EXPIRED: Истекла интеракция для {interaction.user.display_name}")
            return False
        else:
            raise
    except Exception as e:
        print(f"❌ Ошибка при отправке модального окна: {e}")
        import traceback
        traceback.print_exc()
        return False


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
            # КРИТИЧЕСКИ ВАЖНО: немедленно откладываем ответ, чтобы избежать timeout
            await interaction.response.defer(ephemeral=True)
            
            # Используем локальный warehouse_manager из utils
            from utils.warehouse_manager import WarehouseManager
            warehouse_manager = WarehouseManager()
            
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
                        
                        await interaction.followup.send(
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
                await interaction.followup.send(
                    "❌ Неизвестная категория! Попробуйте ещё раз.",
                    ephemeral=True
                )
                return
            
            # Получение информации о категории из warehouse_manager
            category_info = warehouse_manager.item_categories.get(selected_category)
            
            if not category_info:
                await interaction.followup.send(
                    f"❌ Категория '{selected_category}' не найдена в системе!",
                    ephemeral=True
                )
                return
            
            # Создание выбора предметов
            view = WarehouseItemSelectView(selected_category, category_info, warehouse_manager)
            
            # Безопасное получение emoji с fallback
            category_emoji = category_info.get('emoji', '📦')
            
            embed = discord.Embed(
                title=f"{category_emoji} {selected_category}",
                description="Выберите конкретный предмет для запроса:",
                color=discord.Color.blue()
            )
            
            # Безопасная отправка с защитой от истёкших интеракций
            # Используем followup так как interaction уже deferred
            try:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                print(f"✅ Отправлен выбор предметов для категории {selected_category}")
            except discord.NotFound as e:
                if e.code == 10062:  # Unknown interaction
                    print(f"⚠️ INTERACTION EXPIRED: Истекла интеракция для {interaction.user.display_name}")
                    print(f"⚠️ Не удалось отправить выбор предметов для категории {selected_category}")
                else:
                    raise
            except Exception as e:
                print(f"❌ Ошибка при отправке выбора предметов: {e}")
                print(f"⚠️ Не удалось отправить выбор предметов для категории {selected_category}")
            
        except Exception as e:
            print(f"❌ Ошибка при выборе категории склада: {e}")
            import traceback
            traceback.print_exc()
            try:
                # Пробуем followup сначала (если interaction был deferred)
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"❌ Произошла ошибка: {str(e)}", ephemeral=True
                    )
                else:
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
        
        # Добавляем кнопку "Характеристики оружия" для категории "Оружие"
        if category == "Оружие":
            weapons_info_button = discord.ui.Button(
                label="Характеристики оружия",
                style=discord.ButtonStyle.primary,
                emoji="📊",
                custom_id="warehouse_weapons_info",
                row=0
            )
            weapons_info_button.callback = self._weapons_info_callback
            self.add_item(weapons_info_button)
        
        # Добавление кнопок для каждого предмета
        items = category_info["items"]
        for i, item in enumerate(items):
            if i < 20:  # Максимум 20 кнопок (4 ряда по 5)
                try:
                    # Делаем custom_id уникальным для каждой категории!
                    unique_id = f"warehouse_{self.category.lower()}_{i}_{hash(item) % 10000}"
                    
                    # Для категории "Оружие" сдвигаем кнопки, чтобы освободить место для кнопки характеристик
                    row_offset = 1 if category == "Оружие" else 0
                    current_row = (i // 5) + row_offset
                    
                    button = discord.ui.Button(
                        label=item[:80] if len(item) > 80 else item,  # Ограничение длины
                        style=discord.ButtonStyle.secondary,
                        custom_id=unique_id,  # Уникальный ID!
                        row=current_row  # Распределение по рядам с учетом offset
                    )
                    button.callback = self._create_item_callback(item)
                    self.add_item(button)
                except Exception as e:
                    print(f"❌ Ошибка создания кнопки для предмета '{item}': {e}")
        
        print(f"🔍 VIEW_CREATED: Добавлено {len(self.children)} элементов в view")

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
            
            # Защита от истёкших интеракций при отправке модального окна
            success = await safe_modal_response(interaction, modal)
            if not success:
                print(f"⚠️ Не удалось отправить модальное окно для предмета {item_name}")
            
        return callback

    async def _weapons_info_callback(self, interaction: discord.Interaction):
        """Callback для кнопки характеристик оружия"""
        try:
            # Путь к файлу с характеристиками оружия
            weapons_info_path = "files/weapons_info.png"
            
            # Проверяем существование файла
            import os
            if not os.path.exists(weapons_info_path):
                await interaction.response.send_message(
                    "❌ Файл с характеристиками оружия не найден.",
                    ephemeral=True
                )
                return
            
            # Отправляем файл как ephemeral сообщение
            file = discord.File(weapons_info_path, filename="weapons_info.png")
            
            # Безопасная отправка с защитой от истёкших интеракций
            success = await safe_interaction_response(
                interaction, 
                content="📊 **Характеристики оружия:**", 
                file=file
            )
            if not success:
                print(f"⚠️ Не удалось отправить характеристики оружия")
            
        except Exception as e:
            print(f"❌ Ошибка при отправке характеристик оружия: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при загрузке характеристик оружия.",
                ephemeral=True
            )


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
            # КРИТИЧЕСКИ ВАЖНО: откладываем ответ для длительных операций
            await interaction.response.defer(ephemeral=True)
            
            if self.cart.is_empty():
                await interaction.followup.send(
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
                        await interaction.followup.send(
                            f"⏰ Кулдаун! Вы можете подать следующий запрос через {hours}ч {minutes}мин",
                            ephemeral=True
                        )
                        return
            
            # НЕ устанавливаем флаг отправки здесь - только после реальной отправки в канал!
              # Показываем модальное окно
            try:
                from utils.user_cache import prepare_modal_data
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
        
        # Создаем view для подтверждения
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
            # СНАЧАЛА получаем сообщение корзины ДО очистки отслеживания!
            cart_message = get_user_cart_message(interaction.user.id)
            
            # Очищаем корзину
            self.cart.clear()
            
            # Теперь работаем с полученным сообщением корзины
            if cart_message:
                try:
                    # Сразу удаляем сообщение корзины БЕЗ обновления и задержек
                    await cart_message.delete()
                    print(f"🧹 CART: Сообщение корзины удалено для пользователя {interaction.user.id}")
                        
                except (discord.NotFound, discord.HTTPException) as e:
                    print(f"Не удалось удалить сообщение корзины: {e}")
            else:
                print(f"⚠️ CART: Сообщение корзины не найдено для пользователя {interaction.user.id}")
            
            # В конце очищаем отслеживание
            clear_user_cart_safe(interaction.user.id, "пользователь подтвердил очистку")
            
            # Удаляем сообщение подтверждения немедленно
            await interaction.response.edit_message(content="✅ Корзина очищена!", embed=None, view=None)

            # Удаляем сообщение подтверждения через 1 секунду
            await asyncio.sleep(1)
            try:
                await interaction.delete_original_response()
            except:
                pass  # Игнорируем ошибки удаления
                    
        except Exception as e:
            print(f"❌ Ошибка при очистке корзины: {e}")
            try:
                await interaction.response.edit_message(
                    content="❌ Произошла ошибка при очистке корзины",
                    embed=None,
                    view=None
                )
            except:
                pass
    
    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отменить очистку корзины"""
        # Просто удаляем сообщение подтверждения
        await interaction.response.edit_message(content="❌ Очистка отменена", embed=None, view=None)
        
        # Удаляем сообщение через 2 секунды
        await asyncio.sleep(2)
        try:
            await interaction.delete_original_response()
        except:
            pass  # Игнорируем ошибки удаления
    
    async def _auto_delete_message(self, message):
        """Автоматически удалить сообщение через 10 секунд (DEPRECATED - заменен на delete_original_response)"""
        # Этот метод больше не используется для ephemeral сообщений
        pass


class WarehouseSubmittedView(discord.ui.View):
    """View для уже отправленной заявки - только статическое сообщение без кнопок"""
    
    def __init__(self):
        super().__init__(timeout=None)
        # Пустая view - только для статического отображения
