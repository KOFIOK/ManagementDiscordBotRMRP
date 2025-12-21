"""
Система редактирования заявок склада модераторами
"""

import re
import discord
from typing import List
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


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
        for i, (item_text, item_name, quantity, is_deleted) in enumerate(items):
            if i < 25:  # Discord лимит на select options
                if is_deleted:
                    # Удаленный предмет - отображаем с крестиком
                    options.append(discord.SelectOption(
                        label=f"❌ {i+1}. {item_name}",
                        description=f"Удален | Было: {quantity}",
                        value=str(i),
                        emoji="🗑️"
                    ))
                else:
                    # Обычный предмет
                    options.append(discord.SelectOption(
                        label=f"❌ {i+1}. {item_name}",
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
        """Парсит предметы из embed заявки, включая удаленные"""
        items = []
        
        try:
            embed = self.original_message.embeds[0]
            
            # Ищем поле с предметами
            for field in embed.fields:
                if "запрашиваемые предметы" in field.name.lower() or "предмет" in field.name.lower():
                    field_value = field.value
                    
                    # Парсим строки вида "1. **AK-74M** × 2" и "❌ ~~1. **AK-74M** × 2~~"
                    lines = field_value.split('\n')
                    for line in lines:
                        line = line.strip()
                        if '×' in line or 'x' in line:
                            is_deleted = False
                            original_line = line
                            
                            # Проверяем, удален ли предмет (зачеркнут)
                            if line.startswith('❌ ~~') and line.endswith('~~'):
                                is_deleted = True
                                # Убираем зачеркивание для парсинга
                                prefix = "❌ ~~"
                                suffix = "~~"
                                line = line[len(prefix):-len(suffix)]
                            
                            # Извлекаем номер, название и количество
                            # Паттерн для строки "1. **название** × количество"
                            match = re.match(r'(\d+)\.\s*\*\*(.*?)\*\*\s*[×x]\s*(\d+)', line)
                            if match:
                                number, item_name, quantity = match.groups()
                                items.append((original_line, item_name.strip(), int(quantity), is_deleted))
                            else:
                                # Fallback парсинг для других форматов
                                if '**' in line and ('×' in line or 'x' in line):
                                    parts = line.split('**')
                                    if len(parts) >= 3:
                                        item_name = parts[1].strip()
                                        quantity_part = line.split('×')[-1] if '×' in line else line.split('x')[-1]
                                        try:
                                            # Убираем дополнительные пометки вида "*(из 2)*"
                                            quantity_part = quantity_part.split('*')[0].strip()
                                            quantity = int(quantity_part.strip())
                                            items.append((original_line, item_name, quantity, is_deleted))
                                        except ValueError:
                                            pass
                                # Если нет звездочек, пытаемся парсить как простой формат
                                elif '×' in line or 'x' in line:
                                    # Парсим простой формат "Название × количество"
                                    parts = line.split('×') if '×' in line else line.split('x')
                                    if len(parts) == 2:
                                        item_name = parts[0].strip()
                                        # Убираем номер из начала названия (например, "4. Бинт" -> "Бинт")
                                        if re.match(r'^\d+\.\s*', item_name):
                                            item_name = re.sub(r'^\d+\.\s*', '', item_name)
                                        try:
                                            quantity = int(parts[1].strip())
                                            items.append((original_line, item_name, quantity, is_deleted))
                                        except ValueError:
                                            pass
                    break
        except Exception as e:
            logger.error("Ошибка парсинга предметов из embed: %s", e)
        
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
            
            item_text, item_name, current_quantity, is_deleted = self.parsed_items[item_index]
            
            # Показываем кнопки действий (разные для удаленных и обычных предметов)
            if is_deleted:
                # Для удаленного предмета показываем только кнопку восстановления
                view = WarehouseRestoreActionView(
                    self.original_message, 
                    item_index, 
                    item_text, 
                    item_name, 
                    current_quantity
                )
                
                embed = discord.Embed(
                    title="🔧 Восстановление предмета",
                    description=f"🗑️ **Удаленный предмет:** {item_name}\n**Было количество:** {current_quantity}",
                    color=discord.Color.orange()
                )
            else:
                # Для обычного предмета показываем стандартные действия
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
            logger.error("Ошибка при выборе предмета для редактирования: %s", e)
            await interaction.response.send_message(
                " Произошла ошибка при обработке выбора.",
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
            await interaction.response.defer(ephemeral=False)
            
            # Обновляем оригинальное сообщение заявки
            await self._update_original_message_remove_item(interaction)
            
            # Возвращаемся к Select Menu с сообщением об успехе
            await self._return_to_select_menu(interaction, f" Предмет **{self.item_name}** удален из заявки")
            
        except Exception as e:
            logger.error("Ошибка при удалении предмета: %s", e)
            await interaction.followup.send(
                " Произошла ошибка при удалении предмета.",
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
                self.current_quantity,
                parent_view=self  # Передаем ссылку на родительский view
            )
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error("Ошибка при открытии модального окна: %s", e)
            await interaction.response.send_message(
                " Произошла ошибка при открытии формы.",
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
                    from .persistent_views import WarehousePersistentMultiRequestView
                    original_view = WarehousePersistentMultiRequestView()
                else:
                    from .persistent_views import WarehousePersistentRequestView
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
            logger.error("Ошибка при обновлении сообщения: %s", e)
            raise

    async def _return_to_select_menu(self, interaction: discord.Interaction, success_message: str = None):
        """Возвращаемся к Select Menu с обновленными данными"""
        try:
            # Создаем новый Select Menu с обновленными данными
            new_view = WarehouseEditSelectView(self.original_message)
            
            # Создаем embed для Select Menu
            embed = discord.Embed(
                title="🔧 Редактирование заявки склада",
                description="Выберите предмет для редактирования из списка ниже:",
                color=discord.Color.blue()
            )
            
            # Добавляем сообщение об успехе, если есть
            if success_message:
                embed.add_field(
                    name="📋 Последнее действие",
                    value=success_message,
                    inline=False
                )
            
            # Обновляем сообщение
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=new_view)
            else:
                await interaction.response.edit_message(embed=embed, view=new_view)
                
        except Exception as e:
            logger.error("Ошибка при возврате к Select Menu: %s", e)
            raise


class WarehouseRestoreActionView(discord.ui.View):
    """View с кнопкой восстановления удаленного предмета"""
    
    def __init__(self, original_message: discord.Message, item_index: int, 
                 item_text: str, item_name: str, original_quantity: int):
        super().__init__(timeout=300)  # 5 минут на действие
        self.original_message = original_message
        self.item_index = item_index
        self.item_text = item_text
        self.item_name = item_name
        self.original_quantity = original_quantity
    
    @discord.ui.button(label="♻️ Восстановить предмет", style=discord.ButtonStyle.success)
    async def restore_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Восстановить удаленный предмет"""
        try:
            await interaction.response.defer(ephemeral=False)
            
            # Обновляем оригинальное сообщение заявки
            await self._update_original_message_restore_item(interaction)
            
            # Возвращаемся к Select Menu с сообщением об успехе
            await self._return_to_select_menu(interaction, f" Предмет **{self.item_name}** восстановлен в заявке")
            
        except Exception as e:
            logger.error("Ошибка при восстановлении предмета: %s", e)
            await interaction.followup.send(
                " Произошла ошибка при восстановлении предмета.",
                ephemeral=True
            )
    
    async def _update_original_message_restore_item(self, interaction: discord.Interaction):
        """Обновить оригинальное сообщение - восстановить предмет"""
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
                    from .persistent_views import WarehousePersistentMultiRequestView
                    original_view = WarehousePersistentMultiRequestView()
                else:
                    from .persistent_views import WarehousePersistentRequestView
                    original_view = WarehousePersistentRequestView()
            
            # Ищем поле с предметами
            for i, field in enumerate(embed.fields):
                if "запрашиваемые предметы" in field.name.lower():
                    lines = field.value.split('\n')
                    
                    # Найдем и восстановим нужную строку (убираем зачеркивание)
                    for j, line in enumerate(lines):
                        if line.strip() == self.item_text:
                            # Восстанавливаем предмет - убираем "❌ ~~" и "~~"
                            if line.startswith('❌ ~~') and line.endswith('~~'):
                                # Извлекаем содержимое без зачеркивания
                                prefix = "❌ ~~"
                                suffix = "~~"
                                content = line[len(prefix):-len(suffix)]  # Правильное удаление
                                
                                # Проверяем и восстанавливаем номер
                                expected_number = str(self.item_index + 1)
                                
                                # Проверяем, правильный ли номер в начале
                                import re
                                match = re.match(r'^(\d+)\.\s*(.*)$', content.strip())
                                if match:
                                    current_number = match.group(1)
                                    item_content = match.group(2).strip()  # Убираем лишние пробелы
                                    
                                    # Если номер неправильный, исправляем
                                    if current_number != expected_number:
                                        restored_line = f"{expected_number}. {item_content}"
                                    else:
                                        restored_line = f"{current_number}. {item_content}"  # Пересобираем правильно
                                else:
                                    # Номера нет совсем, добавляем
                                    restored_line = f"{expected_number}. {content.strip()}"
                                
                                lines[j] = restored_line
                            break
                    
                    # Обновляем поле
                    new_value = '\n'.join(lines)
                    embed.set_field_at(i, name=field.name, value=new_value, inline=field.inline)
                    break
            
            # Обновляем сообщение с восстановленным view
            await self.original_message.edit(embed=embed, view=original_view)
            
        except Exception as e:
            logger.error("Ошибка при обновлении сообщения: %s", e)
            raise

    async def _return_to_select_menu(self, interaction: discord.Interaction, success_message: str = None):
        """Возвращаемся к Select Menu с обновленными данными"""
        try:
            # Создаем новый Select Menu с обновленными данными
            new_view = WarehouseEditSelectView(self.original_message)
            
            # Создаем embed для Select Menu
            embed = discord.Embed(
                title="📦 Редактирование заявки склада",
                description="Выберите предмет для редактирования из списка ниже:",
                color=discord.Color.blue()
            )
            
            # Добавляем сообщение об успехе, если есть
            if success_message:
                embed.add_field(
                    name="📋 Последнее действие",
                    value=success_message,
                    inline=False
                )
            
            # Обновляем сообщение
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=new_view)
            else:
                await interaction.response.edit_message(embed=embed, view=new_view)
                
        except Exception as e:
            logger.error("Ошибка при возврате к Select Menu: %s", e)
            raise


class WarehouseEditQuantityModal(discord.ui.Modal):
    """Модальное окно для изменения количества предмета"""
    
    def __init__(self, original_message: discord.Message, item_index: int,
                 item_text: str, item_name: str, current_quantity: int, parent_view=None):
        super().__init__(title=f"Изменить: {item_name[:40]}")
        self.original_message = original_message
        self.item_index = item_index
        self.item_text = item_text
        self.item_name = item_name
        self.current_quantity = current_quantity
        self.parent_view = parent_view  # Ссылка на родительский view
        
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
            # Валидация нового количества
            try:
                new_quantity = int(self.quantity_input.value.strip())
                if new_quantity <= 0:
                    await interaction.response.send_message(
                        "❌ Количество должно быть больше 0!",
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ Некорректное количество! Введите число.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=False)
            
            # Обновляем оригинальное сообщение
            await self._update_original_message_quantity(interaction, new_quantity)
            
            # Возвращаемся к Select Menu с сообщением об успехе
            await self._return_to_select_menu(
                interaction, 
                f"✅ Количество **{self.item_name}** изменено с {self.current_quantity} на {new_quantity}"
            )
            
        except Exception as e:
            logger.error("Ошибка при изменении количества: %s", e)
            await interaction.followup.send(
                " Произошла ошибка при изменении количества.",
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
                            # Определяем изначальное количество
                            original_quantity = self._extract_original_quantity(line)
                            
                            # Создаем новую строку с отметкой об изменении
                            # Заменяем количество и добавляем пометку с изначальным количеством
                            match = re.match(r'(\d+\.\s*\*\*.*?\*\*)\s*[×x]\s*(\d+)', self.item_text)
                            if match:
                                item_part = match.group(1)
                                lines[j] = f"{item_part} × {new_quantity} *(из {original_quantity})*"
                            else:
                                # Fallback: находим базовую часть без количества и пометок
                                base_item = self._extract_base_item_text(self.item_text)
                                lines[j] = f"{base_item} × {new_quantity} *(из {original_quantity})*"
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
                    from .persistent_views import WarehousePersistentMultiRequestView
                    original_view = WarehousePersistentMultiRequestView()
                else:
                    from .persistent_views import WarehousePersistentRequestView
                    original_view = WarehousePersistentRequestView()
            
            await self.original_message.edit(embed=embed, view=original_view)
            
        except Exception as e:
            logger.error("Ошибка при обновлении количества в сообщении: %s", e)
            raise

    def _extract_original_quantity(self, line: str) -> int:
        """Извлекает изначальное количество из строки предмета"""
        try:
            # Проверяем, есть ли уже пометка об изменении "*(из X)*"
            existing_original_match = re.search(r'\*\(из (\d+)\)\*', line)
            if existing_original_match:
                # Если есть пометка, возвращаем изначальное количество из неё
                return int(existing_original_match.group(1))
            else:
                # Если пометки нет, значит это первое изменение - возвращаем текущее количество как изначальное
                return self.current_quantity
        except:
            # В случае ошибки возвращаем текущее количество
            return self.current_quantity

    def _extract_base_item_text(self, item_text: str) -> str:
        """Извлекает базовую часть предмета без количества и пометок"""
        try:
            # Убираем пометку об изменении "*(из X)*" если есть
            base_text = re.sub(r'\s*\*\(из \d+\)\*', '', item_text)
            
            # Убираем количество с конца: ищем последнее вхождение × или x с числом
            # Используем более точный паттерн для удаления только количества в конце
            base_text = re.sub(r'\s*[×x]\s*\d+\s*$', '', base_text)
            
            return base_text.strip()
        except:
            # В случае ошибки возвращаем исходный текст
            return item_text

    async def _return_to_select_menu(self, interaction: discord.Interaction, success_message: str = None):
        """Возвращаемся к Select Menu с обновленными данными"""
        try:
            # Находим оригинальное сообщение с редактированием (то, где был Select Menu)
            # Нужно найти interaction из родительского view или использовать webhook
            
            # Создаем новый Select Menu с обновленными данными
            new_view = WarehouseEditSelectView(self.original_message)
            
            # Создаем embed для Select Menu
            embed = discord.Embed(
                title="📦 Редактирование заявки склада",
                description="Выберите предмет для редактирования из списка ниже:",
                color=discord.Color.blue()
            )
            
            # Добавляем сообщение об успехе, если есть
            if success_message:
                embed.add_field(
                    name="📋 Последнее действие",
                    value=success_message,
                    inline=False
                )
            
            # Обновляем сообщение через followup (так как modal response уже использован)
            await interaction.edit_original_response(embed=embed, view=new_view)
                
        except Exception as e:
            logger.error("Ошибка при возврате к Select Menu: %s", e)
            raise