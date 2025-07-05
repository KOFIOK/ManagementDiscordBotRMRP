"""
Модуль управления подразделениями.
Предоставляет интерфейс для добавления, редактирования и удаления подразделений.
"""

import discord
from discord import ui
from typing import Dict, Any
import logging
from utils.department_manager import DepartmentManager

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
                color = dept_data.get('color', 'синий')
                key_role_id = dept_data.get('key_role_id')
                
                key_role_info = ""
                if key_role_id:
                    role = interaction.guild.get_role(key_role_id)
                    if role:
                        key_role_info = f" (Ключевая роль: {role.mention})"
                    else:
                        key_role_info = f" (Ключевая роль: ID {key_role_id} - не найдена)"
                
                department_list.append(f"{emoji} **{name}** - {color}{key_role_info}")
            
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
    
    @ui.button(label="🔙 Назад", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_main(self, interaction: discord.Interaction, button: ui.Button):
        """Вернуться в главное меню настроек"""
        from .main import MainSettingsView
        
        embed = discord.Embed(
            title="⚙️ Настройки бота",
            description="Выберите категорию настроек для управления:",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        view = MainSettingsView()
        await interaction.response.edit_message(embed=embed, view=view)


class AddDepartmentModal(ui.Modal):
    """Модальное окно для добавления нового подразделения"""
    
    def __init__(self):
        super().__init__(title="➕ Добавить подразделение")
    
    department_id = ui.TextInput(
        label="ID подразделения",
        placeholder="Например: custom_dept",
        required=True,
        max_length=50
    )
    
    department_name = ui.TextInput(
        label="Название подразделения",
        placeholder="Например: Пользовательское подразделение",
        required=True,
        max_length=100
    )
    
    department_emoji = ui.TextInput(
        label="Эмодзи подразделения",
        placeholder="Например: 🏛️",
        required=False,
        max_length=10
    )
    
    department_color = ui.TextInput(
        label="Цвет подразделения",
        placeholder="Выберите из списка или оставьте пустым",
        required=False,
        max_length=20
    )
    
    key_role_id = ui.TextInput(
        label="ID ключевой роли (необязательно)",
        placeholder="Например: 123456789012345678",
        required=False,
        max_length=20
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Валидация ID подразделения
            dept_id = self.department_id.value.strip().lower()
            if not dept_id.replace('_', '').replace('-', '').isalnum():
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="ID подразделения может содержать только латинские буквы, цифры, дефисы и подчеркивания.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Проверка уникальности ID
            if DepartmentManager.department_exists(dept_id):
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Подразделение с ID `{dept_id}` уже существует.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Валидация цвета
            color = self.department_color.value.strip().lower() if self.department_color.value else None
            if color and color not in DepartmentManager.get_available_colors():
                available_colors = ", ".join(DepartmentManager.get_available_colors())
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Недопустимый цвет. Доступные цвета: {available_colors}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Валидация ключевой роли
            key_role_id = None
            if self.key_role_id.value:
                try:
                    key_role_id = int(self.key_role_id.value.strip())
                    role = interaction.guild.get_role(key_role_id)
                    if not role:
                        embed = discord.Embed(
                            title="❌ Ошибка",
                            description=f"Роль с ID `{key_role_id}` не найдена на сервере.",
                            color=discord.Color.red()
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return
                except ValueError:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description="ID роли должен быть числом.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            
            # Создание подразделения
            success = DepartmentManager.add_department(
                dept_id=dept_id,
                name=self.department_name.value.strip(),
                emoji=self.department_emoji.value.strip() if self.department_emoji.value else None,
                color=color,
                key_role_id=key_role_id
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Подразделение `{dept_id}` успешно добавлено!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 Детали:",
                    value=(
                        f"**ID:** {dept_id}\n"
                        f"**Название:** {self.department_name.value.strip()}\n"
                        f"**Эмодзи:** {self.department_emoji.value.strip() or '🏛️'}\n"
                        f"**Цвет:** {color or 'синий'}\n"
                        f"**Ключевая роль:** {f'<@&{key_role_id}>' if key_role_id else 'Не указана'}"
                    ),
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description="Не удалось добавить подразделение. Проверьте логи для подробной информации.",
                    color=discord.Color.red()
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error adding department: {e}")
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Произошла ошибка при добавлении подразделения: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class EditDepartmentSelectView(ui.View):
    """Выбор подразделения для редактирования"""
    
    def __init__(self, departments: Dict[str, Any]):
        super().__init__(timeout=300)
        self.departments = departments
        
        # Добавляем селект-меню с подразделениями
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
        super().__init__(title=f"✏️ Редактировать {dept_data.get('name', dept_id)}")
        self.dept_id = dept_id
        self.original_data = dept_data.copy()
        
        # Заполняем поля текущими значениями
        self.department_name.default = dept_data.get('name', '')
        self.department_emoji.default = dept_data.get('emoji', '')
        self.department_color.default = dept_data.get('color', '')
        
        key_role_id = dept_data.get('key_role_id')
        self.key_role_id.default = str(key_role_id) if key_role_id else ''
    
    department_name = ui.TextInput(
        label="Название подразделения",
        placeholder="Например: Пользовательское подразделение",
        required=True,
        max_length=100
    )
    
    department_emoji = ui.TextInput(
        label="Эмодзи подразделения",
        placeholder="Например: 🏛️",
        required=False,
        max_length=10
    )
    
    department_color = ui.TextInput(
        label="Цвет подразделения",
        placeholder="Выберите из списка или оставьте пустым",
        required=False,
        max_length=20
    )
    
    key_role_id = ui.TextInput(
        label="ID ключевой роли (необязательно)",
        placeholder="Например: 123456789012345678",
        required=False,
        max_length=20
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Валидация цвета
            color = self.department_color.value.strip().lower() if self.department_color.value else None
            if color and color not in DepartmentManager.get_available_colors():
                available_colors = ", ".join(DepartmentManager.get_available_colors())
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"Недопустимый цвет. Доступные цвета: {available_colors}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Валидация ключевой роли
            key_role_id = None
            if self.key_role_id.value:
                try:
                    key_role_id = int(self.key_role_id.value.strip())
                    role = interaction.guild.get_role(key_role_id)
                    if not role:
                        embed = discord.Embed(
                            title="❌ Ошибка",
                            description=f"Роль с ID `{key_role_id}` не найдена на сервере.",
                            color=discord.Color.red()
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return
                except ValueError:
                    embed = discord.Embed(
                        title="❌ Ошибка",
                        description="ID роли должен быть числом.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            
            # Обновление подразделения
            success = DepartmentManager.edit_department(
                dept_id=self.dept_id,
                name=self.department_name.value.strip(),
                emoji=self.department_emoji.value.strip() if self.department_emoji.value else None,
                color=color,
                key_role_id=key_role_id
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
                        f"**Название:** {self.department_name.value.strip()}\n"
                        f"**Эмодзи:** {self.department_emoji.value.strip() or '🏛️'}\n"
                        f"**Цвет:** {color or 'синий'}\n"
                        f"**Ключевая роль:** {f'<@&{key_role_id}>' if key_role_id else 'Не указана'}"
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
        
        # Добавляем селект-меню с подразделениями
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
        
        # Показываем подтверждение удаления
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
        
        embed.add_field(
            name="📋 Информация о подразделении:",
            value=(
                f"**ID:** {dept_id}\n"
                f"**Название:** {dept_data.get('name', dept_id)}\n"
                f"**Эмодзи:** {dept_data.get('emoji', '🏛️')}\n"
                f"**Цвет:** {dept_data.get('color', 'синий')}"
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
