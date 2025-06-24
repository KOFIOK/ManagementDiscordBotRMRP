"""
Система редактирования заявок склада модераторами
"""

import re
import discord
from typing import List


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
                    from .persistent_views import WarehousePersistentMultiRequestView
                    original_view = WarehousePersistentMultiRequestView()
                else:
                    from .persistent_views import WarehousePersistentRequestView
                    original_view = WarehousePersistentRequestView()
            
            await self.original_message.edit(embed=embed, view=original_view)
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении количества в сообщении: {e}")
            raise
