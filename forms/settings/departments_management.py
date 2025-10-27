"""
Модуль управления подразделениями.
Предоставляет интерфейс для добавления, редактирования и удаления подразделений.
"""

import discord
from discord import ui
from typing import Dict, Any, Optional
import logging
from utils.department_manager import DepartmentManager # Убедитесь, что это правильный путь к вашему DepartmentManager

logger = logging.getLogger(__name__)

class DepartmentsManagementView(ui.View):
    """Основное меню управления подразделениями"""

    def __init__(self):
        super().__init__(timeout=300)

    @ui.button(label="➕ Добавить подразделение", style=discord.ButtonStyle.success, row=0)
    async def add_department(self, interaction: discord.Interaction, button: ui.Button):
        """Добавить новое подразделение"""
        modal = AddDepartmentModal()
        await interaction.response.send_modal(modal)

    @ui.button(label="✏️ Редактировать подразделение", style=discord.ButtonStyle.primary, row=0)
    async def edit_department(self, interaction: discord.Interaction, button: ui.Button):
        """Редактировать существующее подразделение"""
        departments = DepartmentManager.get_all_departments()

        if not departments:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Нет доступных подразделений для редактирования.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = EditDepartmentSelectView(departments)
        embed = discord.Embed(
            title="✏️ Выберите подразделение для редактирования",
            description="Выберите подразделение, которое хотите отредактировать:",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="🗑️ Удалить подразделение", style=discord.ButtonStyle.danger, row=0)
    async def delete_department(self, interaction: discord.Interaction, button: ui.Button):
        """Удалить подразделение"""
        departments = DepartmentManager.get_all_departments()

        if not departments:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Нет доступных подразделений для удаления.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = DeleteDepartmentSelectView(departments)
        embed = discord.Embed(
            title="🗑️ Выберите подразделение для удаления",
            description="⚠️ **Внимание!** Удаление подразделения приведет к удалению всех связанных настроек.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="📋 Список подразделений", style=discord.ButtonStyle.secondary, row=1)
    async def list_departments(self, interaction: discord.Interaction, button: ui.Button):
        """Показать список всех подразделений"""
        departments = DepartmentManager.get_all_departments()

        embed = discord.Embed(
            title="📋 Список подразделений",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        if not departments:
            embed.description = "❌ Подразделения не настроены."
        else:
            department_list = []
            for dept_id, dept_data in departments.items():
                emoji = dept_data.get('emoji', '🏛️')
                name = dept_data.get('name', dept_id)

                # Получаем отображаемое название цвета
                color_value = dept_data.get('color', 0x3498db)
                if isinstance(color_value, str):
                    # Цвет хранится как название
                    color_display = color_value
                elif isinstance(color_value, int):
                    # Цвет хранится как HEX значение
                    # Сначала проверяем, является ли это предустановленным цветом
                    color_display = "Неизвестный цвет"
                    for name_key, hex_val in DepartmentManager.PRESET_COLORS.items():
                        if hex_val == color_value:
                            color_display = name_key
                            break
                    else:
                        # Если не предустановленный, показываем HEX код
                        color_display = f"#{color_value:06x}"

                department_list.append(f"{emoji} **{name}** - {color_display}")

            embed.description = "\n".join(department_list)

        embed.add_field(
            name="ℹ️ Информация",
            value=(
                f"Всего подразделений: **{len(departments)}**\n"
                "Подразделения используются в системах заявок, уведомлений и каналов."
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# --------------------------------------------------------------------------------------
# Модальные окна и Селект-меню
# --------------------------------------------------------------------------------------

class AddDepartmentModal(ui.Modal):
    """Модальное окно для добавления нового подразделения"""

    def __init__(self):
        super().__init__(title="➕ Добавить подразделение")

    department_id = ui.TextInput(
        label="ID подразделения",
        placeholder="Например: genshtab"
    )

    department_name = ui.TextInput(
        label="Название подразделения",
        placeholder="Полное название подразделения"
    )

    department_emoji = ui.TextInput(
        label="Эмодзи подразделения",
        placeholder="Например: 🏛️"
    )

    department_color = ui.TextInput(
        label="Цвет подразделения",
        placeholder="Красный, Blue, #FF0000 или ff0000"
    )

    role_id = ui.TextInput(
        label="ID основной роли подразделения",
        placeholder="Например: 123456789012345678"
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Получаем введенные данные
            dept_id = self.department_id.value.strip().lower() if self.department_id.value else ""
            dept_name = self.department_name.value.strip() if self.department_name.value else ""
            dept_emoji = self.department_emoji.value.strip() if self.department_emoji.value else ""
            dept_color = self.department_color.value.strip() if self.department_color.value else ""
            role_id_str = self.role_id.value.strip() if self.role_id.value else ""

            # Простая валидация
            if not dept_id or not dept_name:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="ID и название подразделения обязательны!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Проверяем, существует ли уже подразделение с таким ID
            existing_departments = DepartmentManager.get_all_departments()
            if dept_id in existing_departments:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Подразделение с ID `{dept_id}` уже существует!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # --- ВАЛИДАЦИЯ ЦВЕТА (HEX коды + названия для совместимости) ---
            color_to_pass_to_manager = None # Цвет, который будет передан в DepartmentManager
            display_color_name = '#3498db (по умолчанию)' # Цвет для отображения в embed

            if dept_color:
                # Сначала проверяем, является ли ввод названием цвета (обратная совместимость)
                found_color_name = None
                for preset_name in DepartmentManager.PRESET_COLORS.keys():
                    if preset_name.lower() == dept_color.lower():
                        found_color_name = preset_name
                        color_to_pass_to_manager = preset_name
                        display_color_name = preset_name
                        break

                # Если не нашли среди названий, пробуем как HEX код
                if not found_color_name:
                    is_valid_hex, hex_value = DepartmentManager.validate_hex_color(dept_color)
                    if is_valid_hex:
                        color_to_pass_to_manager = f'#{dept_color.lstrip("#").upper()}'  # Передаем строку HEX
                        display_color_name = f'#{dept_color.lstrip("#").upper()}'
                    else:
                        # Недопустимый цвет
                        embed = discord.Embed(
                            title="❌ Ошибка",
                            description=(
                                "Недопустимый цвет. Укажите:\n"
                                "• Название цвета: Синий, Красный, Blue, Red...\n"
                                "• HEX код: #ffffff, #fff, ffffff или fff"
                            ),
                            color=discord.Color.red()
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return
            # --- КОНЕЦ ВАЛИДАЦИИ ЦВЕТА ---

            # Валидация основной роли подразделения
            role_id_value = None
            if role_id_str:
                try:
                    role_id_value = int(role_id_str.strip())
                    role = interaction.guild.get_role(role_id_value)
                    if not role:
                        embed = discord.Embed(
                            title="❌ Ошибка",
                            description=f"Роль с ID `{role_id_value}` не найдена на сервере.",
                            color=discord.Color.red()
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return
                except ValueError:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description="ID основной роли должен быть числом.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

            # Создание подразделения
            success = DepartmentManager.add_department(
                dept_id=dept_id,
                name=dept_name,
                emoji=dept_emoji if dept_emoji else None,
                color=color_to_pass_to_manager,
                role_id=role_id_value,
                description="Описание отсутствует"
            )

            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Подразделение `{dept_id}` успешно создано!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 Данные подразделения:",
                    value=(
                        f"**ID:** {dept_id}\n"
                        f"**Название:** {dept_name}\n"
                        f"**Эмодзи:** {dept_emoji or '🏛️'}\n"
                        f"**Цвет:** {display_color_name}\n"
                        f"**Основная роль:** {f'<@&{role_id_value}>' if role_id_value else 'Не указана'}"
                    ),
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Не удалось создать подразделение. Проверьте логи для подробной информации.",
                    color=discord.Color.red()
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Произошла ошибка: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class EditDepartmentSelectView(ui.View):
    """Выбор подразделения для редактирования"""

    def __init__(self, departments: Dict[str, Any]):
        super().__init__(timeout=300)
        self.departments = departments

        self.add_item(EditDepartmentSelect(departments))


class EditDepartmentSelect(ui.Select):
    """Селект-меню для выбора подразделения для редактирования"""

    def __init__(self, departments: Dict[str, Any]):
        self.departments = departments

        options = []
        for dept_id, dept_data in departments.items():
            emoji = dept_data.get('emoji', '🏛️')
            name = dept_data.get('name', dept_id)
            options.append(discord.SelectOption(
                label=name,
                value=dept_id,
                emoji=emoji,
                description=f"ID: {dept_id}"
            ))

        super().__init__(
            placeholder="Выберите подразделение для редактирования...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        dept_id = self.values[0]
        dept_data = self.departments[dept_id]

        modal = EditDepartmentModal(dept_id, dept_data)
        await interaction.response.send_modal(modal)


class EditDepartmentModal(ui.Modal):
    """Модальное окно для редактирования подразделения"""

    def __init__(self, dept_id: str, dept_data: Dict[str, Any]):
        # Определяем placeholder значения (показываем текущие значения)
        name_placeholder = dept_data.get('name', '')
        
        # Определяем placeholder для цвета
        color_value = dept_data.get('color', 0x3498db)
        if isinstance(color_value, str):
            # Если цвет хранится как строка, конвертируем в HEX
            if color_value in DepartmentManager.PRESET_COLORS:
                color_placeholder = f"#{DepartmentManager.PRESET_COLORS[color_value]:06x}"
            else:
                color_placeholder = color_value
        elif isinstance(color_value, int):
            # Показываем HEX код
            color_placeholder = f"#{color_value:06x}"

        emoji_placeholder = dept_data.get('emoji', '')
        abbreviation_placeholder = dept_data.get('abbreviation', dept_id.lower())
        
        role_id = dept_data.get('role_id')
        role_placeholder = str(role_id) if role_id else ""

        # Создаем поля с placeholder и default значениями
        self.department_abbreviation = ui.TextInput(
            label="Аббревиатура подразделения",
            placeholder=abbreviation_placeholder,
            default=abbreviation_placeholder,
            max_length=10
        )

        self.department_name = ui.TextInput(
            label="Название подразделения",
            placeholder=name_placeholder,
            default=name_placeholder
        )

        self.department_emoji = ui.TextInput(
            label="Эмодзи подразделения",
            placeholder=emoji_placeholder,
            default=emoji_placeholder
        )

        self.department_color = ui.TextInput(
            label="Цвет подразделения",
            placeholder=color_placeholder,
            default=color_placeholder
        )

        self.role_id = ui.TextInput(
            label="ID основной роли подразделения",
            placeholder=role_placeholder,
            default=role_placeholder
        )

        super().__init__(title=f"✏️ Редактировать {dept_data.get('name', dept_id)}")
        
        # Добавляем поля в модальное окно
        self.add_item(self.department_abbreviation)
        self.add_item(self.department_name)
        self.add_item(self.department_emoji)
        self.add_item(self.department_color)
        self.add_item(self.role_id)
        
        self.dept_id = dept_id
        self.original_data = dept_data.copy()

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # --- ВАЛИДАЦИЯ ЦВЕТА (HEX коды + названия для совместимости) ---
            color_input_value = self.department_color.value.strip() # Оригинальный ввод пользователя
            color_to_pass_to_manager = None # Цвет, который будет передан в DepartmentManager
            display_color_name = '#3498db (по умолчанию)' # Цвет для отображения в embed

            if color_input_value:
                # Сначала проверяем, является ли ввод названием цвета (обратная совместимость)
                found_color_name = None
                for preset_name in DepartmentManager.PRESET_COLORS.keys():
                    if preset_name.lower() == color_input_value.lower():
                        found_color_name = preset_name
                        color_to_pass_to_manager = preset_name
                        display_color_name = preset_name
                        break

                # Если не нашли среди названий, пробуем как HEX код
                if not found_color_name:
                    is_valid_hex, hex_value = DepartmentManager.validate_hex_color(color_input_value)
                    if is_valid_hex:
                        color_to_pass_to_manager = f'#{color_input_value.lstrip("#").upper()}'  # Передаем строку HEX
                        display_color_name = f'#{color_input_value.lstrip("#").upper()}'
                    else:
                        # Недопустимый цвет
                        embed = discord.Embed(
                            title="❌ Ошибка",
                            description=(
                                "Недопустимый цвет. Укажите:\n"
                                "• Название цвета: Синий, Зелёный, Красный...\n"
                                "• HEX код: #ffffff или ffffff"
                            ),
                            color=discord.Color.red()
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return
            # --- КОНЕЦ ВАЛИДАЦИИ ЦВЕТА ---

            # Валидация основной роли подразделения
            role_id_value = None
            if self.role_id.value:
                try:
                    role_id_value = int(self.role_id.value.strip())
                    role = interaction.guild.get_role(role_id_value)
                    if not role:
                        embed = discord.Embed(
                            title="❌ Ошибка",
                            description=f"Роль с ID `{role_id_value}` не найдена на сервере.",
                            color=discord.Color.red()
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return
                except ValueError:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description="ID основной роли должен быть числом.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

            # Обновление подразделения
            success = DepartmentManager.edit_department(
                dept_id=self.dept_id,
                abbreviation=self.department_abbreviation.value.strip() if self.department_abbreviation.value else None,
                name=self.department_name.value.strip(),
                emoji=self.department_emoji.value.strip() if self.department_emoji.value else None,
                color=color_to_pass_to_manager, # Передаем название цвета
                role_id=role_id_value
            )

            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Подразделение `{self.dept_id}` успешно обновлено!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 Новые значения:",
                    value=(
                        f"**ID:** {self.dept_id}\n"
                        f"**Аббревиатура:** {self.department_abbreviation.value.strip() or self.dept_id.lower()}\n"
                        f"**Название:** {self.department_name.value.strip()}\n"
                        f"**Эмодзи:** {self.department_emoji.value.strip() or '🏛️'}\n"
                        f"**Цвет:** {display_color_name}\n" # Отображаем найденное название
                        f"**Основная роль:** {f'<@&{role_id_value}>' if role_id_value else 'Не указана'}"
                    ),
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Не удалось обновить подразделение. Проверьте логи для подробной информации.",
                    color=discord.Color.red()
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error editing department: {e}")
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Произошла ошибка при редактировании подразделения: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class DeleteDepartmentSelectView(ui.View):
    """Выбор подразделения для удаления"""

    def __init__(self, departments: Dict[str, Any]):
        super().__init__(timeout=300)
        self.departments = departments

        self.add_item(DeleteDepartmentSelect(departments))


class DeleteDepartmentSelect(ui.Select):
    """Селект-меню для выбора подразделения для удаления"""

    def __init__(self, departments: Dict[str, Any]):
        self.departments = departments

        options = []
        for dept_id, dept_data in departments.items():
            emoji = dept_data.get('emoji', '🏛️')
            name = dept_data.get('name', dept_id)
            options.append(discord.SelectOption(
                label=name,
                value=dept_id,
                emoji=emoji,
                description=f"ID: {dept_id}"
            ))

        super().__init__(
            placeholder="Выберите подразделение для удаления...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        dept_id = self.values[0]
        dept_data = self.departments[dept_id]

        view = DeleteConfirmationView(dept_id, dept_data)

        embed = discord.Embed(
            title="⚠️ Подтверждение удаления",
            description=f"Вы действительно хотите удалить подразделение **{dept_data.get('name', dept_id)}**?",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="🗑️ Что будет удалено:",
            value=(
                "• Подразделение из списка доступных\n"
                "• Все настройки пингов для этого подразделения\n"
                "• Настройки каналов подразделения\n"
                "• Заявки в это подразделение станут недоступными"
            ),
            inline=False
        )

        # Получаем отображаемое название цвета
        color_value = dept_data.get('color', 0x3498db)
        if isinstance(color_value, str):
            color_display = color_value
        elif isinstance(color_value, int):
            color_display = "Неизвестный цвет"
            for name_key, hex_val in DepartmentManager.PRESET_COLORS.items():
                if hex_val == color_value:
                    color_display = name_key
                    break
            else:
                color_display = f"#{color_value:06x}"

        embed.add_field(
            name="📋 Информация о подразделении:",
            value=(
                f"**ID:** {dept_id}\n"
                f"**Название:** {dept_data.get('name', dept_id)}\n"
                f"**Эмодзи:** {dept_data.get('emoji', '🏛️')}\n"
                f"**Цвет:** {color_display}"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class DeleteConfirmationView(ui.View):
    """Подтверждение удаления подразделения"""

    def __init__(self, dept_id: str, dept_data: Dict[str, Any]):
        super().__init__(timeout=300)
        self.dept_id = dept_id
        self.dept_data = dept_data

    @ui.button(label="✅ Да, удалить", style=discord.ButtonStyle.danger, row=0)
    async def confirm_delete(self, interaction: discord.Interaction, button: ui.Button):
        """Подтвердить удаление подразделения"""
        try:
            success = DepartmentManager.delete_department(self.dept_id)

            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Подразделение `{self.dept_id}` и все связанные настройки успешно удалены!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="🗑️ Удалено:",
                    value=(
                        f"**Подразделение:** {self.dept_data.get('name', self.dept_id)}\n"
                        f"**ID:** {self.dept_id}\n"
                        "**Связанные настройки:** Все настройки пингов и каналов"
                    ),
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Не удалось удалить подразделение. Проверьте логи для подробной информации.",
                    color=discord.Color.red()
                )

            # Отключаем все кнопки
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"Error deleting department: {e}")
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Произошла ошибка при удалении подразделения: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_delete(self, interaction: discord.Interaction, button: ui.Button):
        """Отменить удаление"""
        embed = discord.Embed(
            title="❌ Отменено",
            description="Удаление подразделения отменено.",
            color=discord.Color.blue()
        )

        # Отключаем все кнопки
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)