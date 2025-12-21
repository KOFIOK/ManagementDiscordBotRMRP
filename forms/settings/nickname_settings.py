"""
Nickname auto-replacement settings configuration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, SectionSettingsView
from utils.department_manager import DepartmentManager


class NicknameBaseView(BaseSettingsView):
    """Base view for nickname settings with display method"""
    
    async def display(self, interaction: discord.Interaction, embed=None):
        """Display the view with embed"""
        if embed is None:
            embed = discord.Embed(
                title="🏷️ Настройки автозамены никнеймов",
                description="Настройка автоматической замены никнеймов при кадровых операциях.",
                color=discord.Color.blue()
            )
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class NicknameSettingsView(SectionSettingsView):
    """Main nickname settings interface"""
    
    def __init__(self):
        super().__init__(title="🏷️ Настройки автозамены никнеймов", description="Настройка автоматической замены никнеймов при кадровых операциях", timeout=300)
        self.add_item(NicknameSettingsSelect())


class NicknameSettingsSelect(ui.Select):
    """Nickname settings dropdown menu"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Общие настройки",
                description="Глобальное включение/отключение автозамены никнеймов",
                emoji="🌐",
                value="global_settings"
            ),
            discord.SelectOption(
                label="Настройки по подразделениям",
                description="Настроить автозамену для каждого подразделения отдельно",
                emoji="🏢",
                value="department_settings"
            ),
            discord.SelectOption(
                label="Настройки по модулям",
                description="Настроить автозамену для разных кадровых операций",
                emoji="⚙️",
                value="module_settings"
            ),
            discord.SelectOption(
                label="Управление должностями",
                description="Редактировать список известных должностей",
                emoji="📋",
                value="positions_management"
            ),
            discord.SelectOption(
                label="Форматы никнеймов",
                description="Настройка поддержки различных форматов никнеймов",
                emoji="🔠",
                value="format_settings"
            )
            #discord.SelectOption(
            #    label="Редактор шаблонов",
            #    description="Настройка шаблонов распознавания никнеймов",
            #    emoji="🔧",
            #    value="template_editor"
            #)
        ]
        
        super().__init__(
            placeholder="Выберите тип настроек...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="nickname_settings_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_option = self.values[0]
        
        if selected_option == "global_settings":
            await self.show_global_settings(interaction)
        elif selected_option == "department_settings":
            await self.show_department_settings(interaction)
        elif selected_option == "module_settings":
            await self.show_module_settings(interaction)
        elif selected_option == "positions_management":
            await self.show_positions_management(interaction)
        elif selected_option == "format_settings":
            await self.show_format_settings(interaction)
        elif selected_option == "template_editor":
            await self.show_template_editor(interaction)
    
    async def show_global_settings(self, interaction: discord.Interaction):
        """Show global nickname replacement settings"""
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        global_enabled = nickname_settings.get('enabled', True)
        
        embed = discord.Embed(
            title="⚙️ Глобальные настройки автозамены",
            description="Основные параметры автоматической замены никнеймов.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        status_emoji = "✅" if global_enabled else "❌"
        status_text = "Включена" if global_enabled else "Отключена"
        
        embed.add_field(
            name="Текущий статус:",
            value=f"{status_emoji} Автозамена никнеймов: **{status_text}**",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Описание:",
            value=(
                "Автозамена никнеймов автоматически обновляет отображаемые имена пользователей "
                "при выполнении кадровых операций (увольнение, перевод, повышение). "
                "Система использует данные из персональных карточек для формирования корректных никнеймов."
            ),
            inline=False
        )
        
        view = GlobalNicknameSettingsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_department_settings(self, interaction: discord.Interaction):
        """Show department-specific nickname settings"""
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        department_settings = nickname_settings.get('departments', {})
        
        departments = DepartmentManager.get_all_departments()
        
        embed = discord.Embed(
            title="🏢 Настройки по подразделениям",
            description="Настройка автозамены никнеймов для каждого подразделения.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Show current settings for each department
        dept_status = []
        for dept_id, dept_data in departments.items():
            dept_name = dept_data.get('name', dept_id)
            is_enabled = department_settings.get(dept_id, True)  # Default enabled
            status_emoji = "✅" if is_enabled else "❌"
            dept_status.append(f"{status_emoji} **{dept_name}**")
        
        if dept_status:
            embed.add_field(
                name="Текущие настройки:",
                value="\n".join(dept_status),
                inline=False
            )
        else:
            embed.add_field(
                name="Текущие настройки:",
                value="❌ Подразделения не настроены",
                inline=False
            )
        
        view = DepartmentNicknameSettingsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_module_settings(self, interaction: discord.Interaction):
        """Show module-specific nickname settings"""
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        module_settings = nickname_settings.get('modules', {})
        
        embed = discord.Embed(
            title="⚙️ Настройки по модулям",
            description="Настройка автозамены для разных кадровых операций.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        modules = {
            'dismissal': 'Увольнение',
            'transfer': 'Перевод',
            'promotion': 'Повышение',
            'demotion': 'Понижение'
        }
        
        # Show current settings for each module
        module_status = []
        for module_id, module_name in modules.items():
            is_enabled = module_settings.get(module_id, True)  # Default enabled
            status_emoji = "✅" if is_enabled else "❌"
            module_status.append(f"{status_emoji} **{module_name}**")
        
        embed.add_field(
            name="Текущие настройки:",
            value="\n".join(module_status),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Описание модулей:",
            value=(
                "• **Увольнение** - обновление никнейма при увольнении\n"
                "• **Перевод** - обновление при переводе в другое подразделение\n"
                "• **Повышение** - обновление при повышении в должности/звании\n"
                "• **Понижение** - обновление при понижении в должности/звании"
            ),
            inline=False
        )
        
        view = ModuleNicknameSettingsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_format_settings(self, interaction: discord.Interaction):
        """Show nickname format settings"""
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        format_support = nickname_settings.get('format_support', {})
        
        embed = discord.Embed(
            title="📋 Форматы никнеймов",
            description="Настройка поддержки различных форматов никнеймов.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        formats = {
            'standard_with_subgroup': ('С подгруппами', 'РОиО[ПГ] | Ст. Л-т | Виктор Верпов'),
            'positional_with_subgroup': ('Должностные с подгруппами', 'ГШ[АТ] | Зам. Ком. | Анна Смирнова'),
            'auto_detect_positions': ('Автоопределение должностей', 'Автоматическое распознавание должностей vs званий')
        }
        
        format_status = []
        for format_id, (format_name, example) in formats.items():
            is_enabled = format_support.get(format_id, True)
            status_emoji = "✅" if is_enabled else "❌"
            format_status.append(f"{status_emoji} **{format_name}**\n    `{example}`")
        
        embed.add_field(
            name="Текущие настройки:",
            value="\n\n".join(format_status),
            inline=False
        )
        
        embed.add_field(
            name="📋 Описание форматов:",
            value=(
                "• **С подгруппами** - поддержка квадратных скобок [ПГ], [АТ]\n"
                "• **Должностные с подгруппами** - должности + подгруппы\n"
                "• **Автоопределение должностей** - умное различение должностей и званий"
            ),
            inline=False
        )
        
        view = FormatSettingsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_positions_management(self, interaction: discord.Interaction):
        """Show positions management interface"""
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        known_positions = nickname_settings.get('known_positions', [])
        
        embed = discord.Embed(
            title="📋 Управление должностями",
            description="Редактирование списка известных должностей для правильного парсинга.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name=f"Известные должности ({len(known_positions)}):",
            value=", ".join(f"`{pos}`" for pos in known_positions) if known_positions else "Список пуст",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Описание:",
            value=(
                "Должности отличаются от званий тем, что они:\n"
                "• Не изменяются при повышении в звании\n"
                "• Имеют специальные ключевые слова (Нач., Зам., Ком.)\n"
                "• Обозначают функции, а не иерархию"
            ),
            inline=False
        )
        
        view = PositionsManagementView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_template_editor(self, interaction: discord.Interaction):
        """Show template editor interface"""
        embed = discord.Embed(
            title="🔧 Редактор шаблонов никнеймов",
            description="Настройка шаблонов распознавания различных форматов никнеймов.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Доступные шаблоны:",
            value=(
                "• **Стандартный** - `ПОДР | РАНГ | Имя Фамилия`\n"
                "• **С подгруппами** - `ПОДР[ПГ] | РАНГ | Имя Фамилия`\n"
                "• **С номерами** - `ПОДР[1] | РАНГ | Имя Фамилия`\n"
                "• **Должностной** - `ПОДР | ДОЛЖНОСТЬ | Имя Фамилия`\n"
                "• **Простой** - `Имя Фамилия`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Настройка:",
            value=(
                "Выберите шаблон для редактирования. Вы сможете:\n"
                "• Изменить структуру полей\n"
                "• Настроить разделители\n"
                "• Указать обязательные/опциональные части\n"
                "• Добавить поддержку спецсимволов"
            ),
            inline=False
        )
        
        view = TemplateEditorView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class GlobalNicknameSettingsView(NicknameBaseView):
    """View for global nickname settings"""
    
    def __init__(self):
        super().__init__()
        self.add_item(GlobalToggleButton())


class DepartmentNicknameSettingsView(NicknameBaseView):
    """View for department-specific nickname settings"""
    
    def __init__(self):
        super().__init__()
        self.add_item(DepartmentNicknameSelect())


class ModuleNicknameSettingsView(NicknameBaseView):
    """View for module-specific nickname settings"""
    
    def __init__(self):
        super().__init__()
        self.add_item(ModuleNicknameSelect())


class GlobalToggleButton(ui.Button):
    """Button to toggle global nickname replacement"""
    
    def __init__(self):
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        is_enabled = nickname_settings.get('enabled', True)
        
        label = "Отключить автозамену" if is_enabled else "Включить автозамену"
        style = discord.ButtonStyle.danger if is_enabled else discord.ButtonStyle.success
        emoji = "❌" if is_enabled else "✅"
        
        super().__init__(
            label=label,
            style=style,
            emoji=emoji,
            custom_id="toggle_global_nickname"
        )
    
    async def callback(self, interaction: discord.Interaction):
        config = load_config()
        
        # Initialize nickname settings if not exists
        if 'nickname_auto_replacement' not in config:
            config['nickname_auto_replacement'] = {}
        
        # Toggle the setting
        current_state = config['nickname_auto_replacement'].get('enabled', True)
        config['nickname_auto_replacement']['enabled'] = not current_state
        
        save_config(config)
        
        new_state = config['nickname_auto_replacement']['enabled']
        status_text = "включена" if new_state else "отключена"
        
        embed = discord.Embed(
            title="⚙️ Настройки обновлены",
            description=f"Автозамена никнеймов {status_text}.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        # Update the view with new button state
        view = GlobalNicknameSettingsView()
        await interaction.response.edit_message(embed=embed, view=view)


class DepartmentNicknameSelect(ui.Select):
    """Select for department-specific nickname settings"""
    
    def __init__(self):
        departments = DepartmentManager.get_all_departments()
        
        options = []
        for dept_id, dept_data in departments.items():
            dept_name = dept_data.get('name', dept_id)
            options.append(discord.SelectOption(
                label=dept_name,
                description=f"Настроить автозамену для {dept_name}",
                value=dept_id
            ))
        
        if not options:
            options.append(discord.SelectOption(
                label="Нет подразделений",
                description="Подразделения не настроены",
                value="none"
            ))
        
        super().__init__(
            placeholder="Выберите подразделение...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="department_nickname_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_dept = self.values[0]
        
        if selected_dept == "none":
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Подразделения не настроены. Сначала настройте подразделения.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, view=None, ephemeral=True)
            return
        
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        department_settings = nickname_settings.get('departments', {})
        
        departments = DepartmentManager.get_all_departments()
        dept_name = departments.get(selected_dept, {}).get('name', selected_dept)
        is_enabled = department_settings.get(selected_dept, True)
        
        embed = discord.Embed(
            title=f"🏢 Настройки для {dept_name}",
            description=f"Управление автозаменой никнеймов для подразделения {dept_name}.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        status_emoji = "✅" if is_enabled else "❌"
        status_text = "Включена" if is_enabled else "Отключена"
        
        embed.add_field(
            name="Текущий статус:",
            value=f"{status_emoji} Автозамена: **{status_text}**",
            inline=False
        )
        
        view = DepartmentToggleView(selected_dept, dept_name)
        await interaction.response.edit_message(embed=embed, view=view)


class ModuleNicknameSelect(ui.Select):
    """Select for module-specific nickname settings"""
    
    def __init__(self):
        modules = {
            'dismissal': ('Увольнение', '📋'),
            'transfer': ('Перевод', '🔄'),
            'promotion': ('Повышение', '⬆️'),
            'demotion': ('Понижение', '⬇️')
        }
        
        options = []
        for module_id, (module_name, emoji) in modules.items():
            options.append(discord.SelectOption(
                label=module_name,
                description=f"Настроить автозамену для операций {module_name.lower()}",
                emoji=emoji,
                value=module_id
            ))
        
        super().__init__(
            placeholder="Выберите модуль...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="module_nickname_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_module = self.values[0]
        
        modules = {
            'dismissal': 'Увольнение',
            'transfer': 'Перевод',
            'promotion': 'Повышение',
            'demotion': 'Понижение'
        }
        
        module_name = modules.get(selected_module, selected_module)
        
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        module_settings = nickname_settings.get('modules', {})
        is_enabled = module_settings.get(selected_module, True)
        
        embed = discord.Embed(
            title=f"⚙️ Настройки модуля: {module_name}",
            description=f"Управление автозаменой никнеймов для операций {module_name.lower()}.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        status_emoji = "✅" if is_enabled else "❌"
        status_text = "Включена" if is_enabled else "Отключена"
        
        embed.add_field(
            name="Текущий статус:",
            value=f"{status_emoji} Автозамена: **{status_text}**",
            inline=False
        )
        
        view = ModuleToggleView(selected_module, module_name)
        await interaction.response.edit_message(embed=embed, view=view)


class DepartmentToggleView(NicknameBaseView):
    """View for toggling department nickname settings"""
    
    def __init__(self, dept_id, dept_name):
        super().__init__()
        self.dept_id = dept_id
        self.dept_name = dept_name
        self.add_item(DepartmentToggleButton(dept_id, dept_name))


class ModuleToggleView(NicknameBaseView):
    """View for toggling module nickname settings"""
    
    def __init__(self, module_id, module_name):
        super().__init__()
        self.module_id = module_id
        self.module_name = module_name
        self.add_item(ModuleToggleButton(module_id, module_name))


class DepartmentToggleButton(ui.Button):
    """Button to toggle department-specific nickname replacement"""
    
    def __init__(self, dept_id, dept_name):
        self.dept_id = dept_id
        self.dept_name = dept_name
        
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        department_settings = nickname_settings.get('departments', {})
        is_enabled = department_settings.get(dept_id, True)
        
        label = "Отключить" if is_enabled else "Включить"
        style = discord.ButtonStyle.danger if is_enabled else discord.ButtonStyle.success
        emoji = "❌" if is_enabled else "✅"
        
        super().__init__(
            label=label,
            style=style,
            emoji=emoji,
            custom_id=f"toggle_dept_{dept_id}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        config = load_config()
        
        # Initialize nickname settings if not exists
        if 'nickname_auto_replacement' not in config:
            config['nickname_auto_replacement'] = {}
        if 'departments' not in config['nickname_auto_replacement']:
            config['nickname_auto_replacement']['departments'] = {}
        
        # Toggle the setting
        current_state = config['nickname_auto_replacement']['departments'].get(self.dept_id, True)
        config['nickname_auto_replacement']['departments'][self.dept_id] = not current_state
        
        save_config(config)
        
        new_state = config['nickname_auto_replacement']['departments'][self.dept_id]
        status_text = "включена" if new_state else "отключена"
        
        embed = discord.Embed(
            title="⚙️ Настройки обновлены",
            description=f"Автозамена никнеймов для {self.dept_name} {status_text}.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        # Update the view with new button state
        view = DepartmentToggleView(self.dept_id, self.dept_name)
        await interaction.response.edit_message(embed=embed, view=view)


class ModuleToggleButton(ui.Button):
    """Button to toggle module-specific nickname replacement"""
    
    def __init__(self, module_id, module_name):
        self.module_id = module_id
        self.module_name = module_name
        
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        module_settings = nickname_settings.get('modules', {})
        is_enabled = module_settings.get(module_id, True)
        
        label = "Отключить" if is_enabled else "Включить"
        style = discord.ButtonStyle.danger if is_enabled else discord.ButtonStyle.success
        emoji = "❌" if is_enabled else "✅"
        
        super().__init__(
            label=label,
            style=style,
            emoji=emoji,
            custom_id=f"toggle_module_{module_id}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        config = load_config()
        
        # Initialize nickname settings if not exists
        if 'nickname_auto_replacement' not in config:
            config['nickname_auto_replacement'] = {}
        if 'modules' not in config['nickname_auto_replacement']:
            config['nickname_auto_replacement']['modules'] = {}
        
        # Toggle the setting
        current_state = config['nickname_auto_replacement']['modules'].get(self.module_id, True)
        config['nickname_auto_replacement']['modules'][self.module_id] = not current_state
        
        save_config(config)
        
        new_state = config['nickname_auto_replacement']['modules'][self.module_id]
        status_text = "включена" if new_state else "отключена"
        
        embed = discord.Embed(
            title="⚙️ Настройки обновлены",
            description=f"Автозамена никнеймов для операций {self.module_name.lower()} {status_text}.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        # Update the view with new button state
        view = ModuleToggleView(self.module_id, self.module_name)
        await interaction.response.edit_message(embed=embed, view=view)


# Main function to show nickname settings
async def show_nickname_settings_overview(interaction: discord.Interaction):
    """Show the main nickname settings overview"""
    embed = discord.Embed(
        title="🏷️ Настройки автозамены никнеймов",
        description="Управление автоматической заменой никнеймов при кадровых операциях.",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    config = load_config()
    nickname_settings = config.get('nickname_auto_replacement', {})
    global_enabled = nickname_settings.get('enabled', True)
    
    status_emoji = "✅" if global_enabled else "❌"
    status_text = "Включена" if global_enabled else "Отключена"
    
    embed.add_field(
        name="Глобальный статус:",
        value=f"{status_emoji} **{status_text}**",
        inline=True
    )
    
    embed.add_field(
        name="📋 Доступные настройки:",
        value=(
            "• **Общие настройки** - глобальное включение/отключение\n"
            "• **По подразделениям** - настройка для каждого подразделения\n"
            "• **По модулям** - настройка для типов операций\n"
            "• **Управление должностями** - редактирование списка должностей\n"
            "• **Форматы никнеймов** - поддержка различных форматов"
        ),
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Описание системы:",
        value=(
            "Автозамена никнеймов автоматически обновляет отображаемые имена "
            "пользователей при выполнении кадровых операций, используя данные "
            "из персональных карточек."
        ),
        inline=False
    )
    
    view = NicknameSettingsView()
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ============================================================================
# 🎨 VIEWS ДЛЯ УПРАВЛЕНИЯ ФОРМАТАМИ И ДОЛЖНОСТЯМИ
# ============================================================================

class FormatSettingsView(NicknameBaseView):
    """View for format settings"""
    
    def __init__(self):
        super().__init__()
        self.add_item(FormatSettingsSelect())


class PositionsManagementView(NicknameBaseView):
    """View for positions management"""
    
    def __init__(self):
        super().__init__()
        self.add_item(PositionsManagementSelect())


class TemplateEditorView(NicknameBaseView):
    """View for template editing selection"""
    
    def __init__(self):
        super().__init__()
        self.add_item(TemplateEditorSelect())


class FormatSettingsSelect(ui.Select):
    """Select for format settings"""
    
    def __init__(self):
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        format_support = nickname_settings.get('format_support', {})
        
        formats = {
            'standard_with_subgroup': ('С подгруппами', '🔗'),
            'positional_with_subgroup': ('Должностные с подгруппами', '📋'),
            'auto_detect_positions': ('Автоопределение должностей', '🤖')
        }
        
        options = []
        for format_id, (format_name, emoji) in formats.items():
            is_enabled = format_support.get(format_id, True)
            status = "✅" if is_enabled else "❌"
            options.append(discord.SelectOption(
                label=f"{status} {format_name}",
                description=f"Переключить поддержку формата {format_name.lower()}",
                emoji=emoji,
                value=format_id
            ))
        
        super().__init__(
            placeholder="Выберите формат для переключения...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="format_settings_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_format = self.values[0]
        
        config = load_config()
        if 'nickname_auto_replacement' not in config:
            config['nickname_auto_replacement'] = {}
        if 'format_support' not in config['nickname_auto_replacement']:
            config['nickname_auto_replacement']['format_support'] = {}
        
        # Toggle the format
        current_state = config['nickname_auto_replacement']['format_support'].get(selected_format, True)
        config['nickname_auto_replacement']['format_support'][selected_format] = not current_state
        
        save_config(config)
        
        formats = {
            'standard_with_subgroup': 'поддержка подгрупп',
            'positional_with_subgroup': 'должностные с подгруппами',
            'auto_detect_positions': 'автоопределение должностей'
        }
        
        format_name = formats.get(selected_format, selected_format)
        new_state = config['nickname_auto_replacement']['format_support'][selected_format]
        status_text = "включена" if new_state else "отключена"
        
        embed = discord.Embed(
            title="⚙️ Настройки обновлены",
            description=f"Поддержка формата '{format_name}' {status_text}.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        view = FormatSettingsView()
        await interaction.response.edit_message(embed=embed, view=view)


class PositionsManagementSelect(ui.Select):
    """Select for positions management"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Добавить должность",
                description="Добавить новую должность в список",
                emoji="➕",
                value="add_position"
            ),
            discord.SelectOption(
                label="Удалить должность",
                description="Удалить должность из списка",
                emoji="➖",
                value="remove_position"
            ),
            discord.SelectOption(
                label="Сбросить к умолчаниям",
                description="Восстановить стандартный список должностей",
                emoji="🔄",
                value="reset_positions"
            )
        ]
        
        super().__init__(
            placeholder="Выберите действие...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="positions_management_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_action = self.values[0]
        
        if selected_action == "add_position":
            await self.show_add_position_modal(interaction)
        elif selected_action == "remove_position":
            await self.show_remove_position_menu(interaction)
        elif selected_action == "reset_positions":
            await self.reset_positions(interaction)
    
    async def show_add_position_modal(self, interaction: discord.Interaction):
        """Show modal to add new position"""
        modal = AddPositionModal()
        await interaction.response.send_modal(modal)
    
    async def show_remove_position_menu(self, interaction: discord.Interaction):
        """Show menu to remove position"""
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        known_positions = nickname_settings.get('known_positions', [])
        
        if not known_positions:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Список должностей пуст. Нечего удалять.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="➖ Удаление должности",
            description="Выберите должность для удаления из списка.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="Доступные должности:",
            value=", ".join(f"`{pos}`" for pos in known_positions),
            inline=False
        )
        
        view = RemovePositionView(known_positions)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def reset_positions(self, interaction: discord.Interaction):
        """Reset positions to default"""
        default_positions = [
            'Нач.',
            'Нач. по КР',
            'Зам.', 
            'Зам. Ком.',
            'Ком.',
            'Ком. Бриг',
            'Нач. Штаба',
            'Нач. Отдела',
            'Зам. Нач. Отдела'
        ]
        
        config = load_config()
        if 'nickname_auto_replacement' not in config:
            config['nickname_auto_replacement'] = {}
        
        config['nickname_auto_replacement']['known_positions'] = default_positions
        save_config(config)
        
        embed = discord.Embed(
            title="📋 Список сброшен",
            description=f"Список должностей восстановлен к умолчаниям ({len(default_positions)} позиций).",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="Восстановленные должности:",
            value=", ".join(f"`{pos}`" for pos in default_positions),
            inline=False
        )
        
        view = PositionsManagementView()
        await interaction.response.edit_message(embed=embed, view=view)


class AddPositionModal(ui.Modal):
    """Modal for adding new position"""
    
    def __init__(self):
        super().__init__(title="➕ Добавить должность")
        
        self.position_input = ui.TextInput(
            label="Название должности",
            placeholder="Например: Нач. отдела, Зам. Ком. Бриг, Инструктор...",
            min_length=1,
            max_length=50,
            required=True
        )
        self.add_item(self.position_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        new_position = self.position_input.value.strip()
        
        config = load_config()
        if 'nickname_auto_replacement' not in config:
            config['nickname_auto_replacement'] = {}
        if 'known_positions' not in config['nickname_auto_replacement']:
            config['nickname_auto_replacement']['known_positions'] = []
        
        known_positions = config['nickname_auto_replacement']['known_positions']
        
        # Check if position already exists
        if new_position in known_positions:
            embed = discord.Embed(
                title="⚠️ Дублирование",
                description=f"Должность `{new_position}` уже есть в списке.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Add new position
        known_positions.append(new_position)
        config['nickname_auto_replacement']['known_positions'] = known_positions
        save_config(config)
        
        embed = discord.Embed(
            title="💼 Должность добавлена",
            description=f"Должность `{new_position}` добавлена в список.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name=f"Обновленный список ({len(known_positions)}):",
            value=", ".join(f"`{pos}`" for pos in known_positions),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RemovePositionView(NicknameBaseView):
    """View for removing positions"""
    
    def __init__(self, positions):
        super().__init__()
        self.add_item(RemovePositionSelect(positions))


class RemovePositionSelect(ui.Select):
    """Select for removing specific position"""
    
    def __init__(self, positions):
        # Create options for each position
        options = []
        for pos in positions[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=pos,
                description=f"Удалить должность: {pos}",
                value=pos
            ))
        
        super().__init__(
            placeholder="Выберите должность для удаления...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="remove_position_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        position_to_remove = self.values[0]
        
        config = load_config()
        known_positions = config.get('nickname_auto_replacement', {}).get('known_positions', [])
        
        if position_to_remove in known_positions:
            known_positions.remove(position_to_remove)
            config['nickname_auto_replacement']['known_positions'] = known_positions
            save_config(config)
            
            embed = discord.Embed(
                title="🗑️ Должность удалена",
                description=f"Должность `{position_to_remove}` удалена из списка.",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            if known_positions:
                embed.add_field(
                    name=f"Остается должностей ({len(known_positions)}):",
                    value=", ".join(f"`{pos}`" for pos in known_positions),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Результат:",
                    value="Список должностей пуст.",
                    inline=False
                )
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Должность `{position_to_remove}` не найдена в списке.",
                color=discord.Color.red()
            )
        
        await interaction.response.edit_message(embed=embed, view=None)


class TemplateEditorSelect(ui.Select):
    """Select for template editing"""
    
    def __init__(self):
        # Определяем человекочитаемые шаблоны
        templates = {
            'standard': {
                'name': 'Стандартный формат',
                'description': 'ПОДР | РАНГ | Имя Фамилия', 
                'emoji': '📝'
            },
            'standard_with_subgroup': {
                'name': 'Формат с подгруппами',
                'description': 'ПОДР[ПГ] | РАНГ | Имя Фамилия',
                'emoji': '📝'
            },
            'positional': {
                'name': 'Должностной формат', 
                'description': 'ПОДР | ДОЛЖНОСТЬ | Имя Фамилия',
                'emoji': '🔗'
            },
            'simple': {
                'name': 'Простой формат',
                'description': 'Имя Фамилия',
                'emoji': '📋'
            },
            'dismissed': {
                'name': 'Формат увольнения',
                'description': 'Уволен | Имя Фамилия', 
                'emoji': '👤'
            }
        }
        
        options = []
        for template_id, template_data in templates.items():
            options.append(discord.SelectOption(
                label=template_data['name'],
                description=f"Редактировать: {template_data['description']}",
                emoji=template_data['emoji'],
                value=template_id
            ))
        
        super().__init__(
            placeholder="Выберите шаблон для редактирования...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="template_editor_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_template = self.values[0]
        await self.show_template_editor_form(interaction, selected_template)
    
    async def show_template_editor_form(self, interaction: discord.Interaction, template_id: str):
        """Show template editor form for specific template"""
        
        # Получаем текущие настройки шаблонов из конфига
        config = load_config()
        custom_templates = config.get('nickname_auto_replacement', {}).get('custom_templates', {})
        
        # Определяем человекочитаемые параметры шаблонов
        template_configs = {
            'standard': {
                'name': 'Стандартный формат',
                'example': 'ВА | Капитан | Иван Петров',
                'structure': [
                    {'field': 'subdivision', 'name': 'Подразделение', 'required': True, 'max_length': 15},
                    {'field': 'separator1', 'name': 'Разделитель 1', 'default': '|'},
                    {'field': 'rank', 'name': 'Звание/Должность', 'required': True},
                    {'field': 'separator2', 'name': 'Разделитель 2', 'default': '|'},
                    {'field': 'name', 'name': 'Имя Фамилия', 'required': True}
                ]
            },
            'standard_with_subgroup': {
                'name': 'Формат с подгруппами',
                'example': 'РОиО[ПГ] | Ст. Л-т | Виктор Верпов',
                'structure': [
                    {'field': 'subdivision', 'name': 'Подразделение', 'required': True, 'max_length': 15},
                    {'field': 'subgroup', 'name': 'Подгруппа [ПГ]', 'required': True, 'max_length': 10},
                    {'field': 'separator1', 'name': 'Разделитель 1', 'default': '|'},
                    {'field': 'rank', 'name': 'Звание/Должность', 'required': True},
                    {'field': 'separator2', 'name': 'Разделитель 2', 'default': '|'},
                    {'field': 'name', 'name': 'Имя Фамилия', 'required': True}
                ]
            },
            'positional': {
                'name': 'Должностной формат',
                'example': 'ВК | Нач. по КР | Максим Давыдов',
                'structure': [
                    {'field': 'subdivision', 'name': 'Подразделение', 'required': True, 'max_length': 15},
                    {'field': 'separator1', 'name': 'Разделитель 1', 'default': '|'},
                    {'field': 'position', 'name': 'Должность', 'required': True},
                    {'field': 'separator2', 'name': 'Разделитель 2', 'default': '|'},
                    {'field': 'name', 'name': 'Имя Фамилия', 'required': True}
                ]
            },
            'simple': {
                'name': 'Простой формат',
                'example': 'Иван Петров',
                'structure': [
                    {'field': 'name', 'name': 'Имя Фамилия', 'required': True}
                ]
            },
            'dismissed': {
                'name': 'Формат увольнения',
                'example': 'Уволен | Иван Петров',
                'structure': [
                    {'field': 'status', 'name': 'Статус', 'default': 'Уволен', 'required': True},
                    {'field': 'separator', 'name': 'Разделитель', 'default': '|'},
                    {'field': 'name', 'name': 'Имя Фамилия', 'required': True}
                ]
            }
        }
        
        if template_id not in template_configs:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Неизвестный шаблон.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        template_config = template_configs[template_id]
        current_template = custom_templates.get(template_id, {})
        
        embed = discord.Embed(
            title=f"🔧 Редактор: {template_config['name']}",
            description=f"Настройка шаблона распознавания формата никнеймов.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Пример формата:",
            value=f"`{template_config['example']}`",
            inline=False
        )
        
        # Показываем структуру шаблона
        structure_text = []
        for i, part in enumerate(template_config['structure'], 1):
            required_mark = "🔴" if part.get('required') else "🟡"
            max_len = f" (макс. {part['max_length']})" if part.get('max_length') else ""
            default_val = f" = `{part.get('default')}`" if part.get('default') else ""
            
            structure_text.append(f"{required_mark} **{i}. {part['name']}**{max_len}{default_val}")
        
        embed.add_field(
            name="🏗️ Структура шаблона:",
            value="\n".join(structure_text),
            inline=False
        )
        
        embed.add_field(
            name="💡 Обозначения:",
            value="🔴 Обязательное поле  🟡 Опциональное поле",
            inline=False
        )
        
        view = TemplateEditFormView(template_id, template_config)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TemplateEditFormView(NicknameBaseView):
    """View for editing specific template"""
    
    def __init__(self, template_id: str, template_config: dict):
        super().__init__()
        self.template_id = template_id
        self.template_config = template_config
        
        # Добавляем кнопки для редактирования
        self.add_item(EditTemplateButton(template_id, template_config))
        self.add_item(ResetTemplateButton(template_id, template_config))
        self.add_item(TestTemplateButton(template_id))


class EditTemplateButton(ui.Button):
    """Button to edit template structure"""
    
    def __init__(self, template_id: str, template_config: dict):
        self.template_id = template_id
        self.template_config = template_config
        
        super().__init__(
            label="Редактировать шаблон",
            style=discord.ButtonStyle.primary,
            emoji="✏️",
            custom_id=f"edit_template_{template_id}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        modal = TemplateEditModal(self.template_id, self.template_config)
        await interaction.response.send_modal(modal)


class ResetTemplateButton(ui.Button):
    """Button to reset template to default"""
    
    def __init__(self, template_id: str, template_config: dict):
        self.template_id = template_id
        self.template_config = template_config
        
        super().__init__(
            label="Сброс к умолчанию",
            style=discord.ButtonStyle.danger,
            emoji="🔄",
            custom_id=f"reset_template_{template_id}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        config = load_config()
        
        # Удаляем кастомный шаблон, возвращаясь к умолчанию
        if 'nickname_auto_replacement' not in config:
            config['nickname_auto_replacement'] = {}
        if 'custom_templates' not in config['nickname_auto_replacement']:
            config['nickname_auto_replacement']['custom_templates'] = {}
        
        # Удаляем кастомизацию
        if self.template_id in config['nickname_auto_replacement']['custom_templates']:
            del config['nickname_auto_replacement']['custom_templates'][self.template_id]
        
        save_config(config)
        
        embed = discord.Embed(
            title="✅ Шаблон сброшен",
            description=f"Шаблон '{self.template_config['name']}' восстановлен к настройкам по умолчанию.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


class TestTemplateButton(ui.Button):
    """Button to test template with examples"""
    
    def __init__(self, template_id: str):
        self.template_id = template_id
        
        super().__init__(
            label="Тестировать",
            style=discord.ButtonStyle.secondary,
            emoji="🧪",
            custom_id=f"test_template_{template_id}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Здесь будет тестирование шаблона с примерами
        embed = discord.Embed(
            title="🧪 Тестирование шаблона",
            description="Функция тестирования будет добавлена в следующей версии.",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TemplateEditModal(ui.Modal):
    """Modal for editing template parameters"""
    
    def __init__(self, template_id: str, template_config: dict):
        self.template_id = template_id
        self.template_config = template_config
        
        super().__init__(title=f"Редактирование: {template_config['name']}")
        
        # Загружаем текущие настройки
        config = load_config()
        custom_templates = config.get('nickname_auto_replacement', {}).get('custom_templates', {})
        current_settings = custom_templates.get(template_id, {})
        
        # Добавляем поля в зависимости от типа шаблона
        if template_id == 'dismissed':
            # Специальные поля для шаблона увольнения
            self.status_text = ui.TextInput(
                label="Текст статуса",
                placeholder="По умолчанию: Уволен",
                default=current_settings.get('status_text', 'Уволен'),
                max_length=20,
                required=False
            )
            self.add_item(self.status_text)
            
            self.separator_input = ui.TextInput(
                label="Разделитель (пробелы добавляются автоматически)",
                placeholder="По умолчанию: |",
                default=(current_settings.get('separator') or '|').strip(),
                max_length=10,
                required=False
            )
            self.add_item(self.separator_input)
            
            # Поле для настройки символов в именах
            self.name_chars = ui.TextInput(
                label="Допустимые символы в именах",
                placeholder="А-Я, а-я, A-Z, a-z, пробел, точка, дефис",
                default=current_settings.get('name_chars', 'А-ЯЁа-яёA-Za-z\\-\\.\\s'),
                max_length=100,
                required=False,
                style=discord.TextStyle.paragraph
            )
            self.add_item(self.name_chars)
            
        elif template_id in ['standard', 'standard_with_subgroup', 'positional']:
            # Единый разделитель для всех частей никнейма
            self.separator_input = ui.TextInput(
                label="Разделитель (пробелы добавляются автоматически)",
                placeholder="По умолчанию: |",
                default=(current_settings.get('separator') or current_settings.get('separator1') or '|').strip(),
                max_length=10,
                required=False
            )
            self.add_item(self.separator_input)
            
            if template_id == 'standard_with_subgroup':
                self.subgroup_brackets = ui.TextInput(
                    label="Символы для подгруппы",
                    placeholder="По умолчанию: [ ]",
                    default=current_settings.get('subgroup_brackets', '[ ]'),
                    max_length=5,
                    required=False
                )
                self.add_item(self.subgroup_brackets)
        
            # Поле для настройки символов в именах
            self.name_chars = ui.TextInput(
                label="Допустимые символы в именах",
                placeholder="А-Я, а-я, A-Z, a-z, пробел, точка, дефис",
                default=current_settings.get('name_chars', 'А-ЯЁа-яёA-Za-z\\-\\.\\s'),
                max_length=100,
                required=False,
                style=discord.TextStyle.paragraph
            )
            self.add_item(self.name_chars)
            
            # Поле для настройки символов в подразделениях
            self.subdivision_chars = ui.TextInput(
                label="Допустимые символы в подразделениях",
                placeholder="А-Я, а-я, A-Z, цифры",
                default=current_settings.get('subdivision_chars', 'А-ЯЁA-Zа-яё\\d'),
                max_length=50,
                required=False
            )
            self.add_item(self.subdivision_chars)
            
        elif template_id == 'simple':
            # Для простого шаблона только символы имен
            self.name_chars = ui.TextInput(
                label="Допустимые символы в именах",
                placeholder="А-Я, а-я, A-Z, a-z, пробел, точка, дефис",
                default=current_settings.get('name_chars', 'А-ЯЁа-яёA-Za-z\\-\\.\\s'),
                max_length=100,
                required=False,
                style=discord.TextStyle.paragraph
            )
            self.add_item(self.name_chars)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            config = load_config()
            
            # Инициализируем структуру если нужно
            if 'nickname_auto_replacement' not in config:
                config['nickname_auto_replacement'] = {}
            if 'custom_templates' not in config['nickname_auto_replacement']:
                config['nickname_auto_replacement']['custom_templates'] = {}
            
            # Сохраняем настройки шаблона в зависимости от типа
            template_settings = {}
            
            if self.template_id == 'dismissed':
                # Специальная обработка для шаблона увольнения
                if hasattr(self, 'status_text'):
                    template_settings['status_text'] = self.status_text.value or 'Уволен'
                
                if hasattr(self, 'separator_input'):
                    # Убираем пробелы из разделителя - они добавятся автоматически
                    template_settings['separator'] = (self.separator_input.value or '|').strip()
                
                # Сохраняем символы для имен
                if hasattr(self, 'name_chars'):
                    template_settings['name_chars'] = self.name_chars.value or 'А-ЯЁа-яёA-Za-z\\-\\.\\s'
                    
            else:
                # Обработка для других шаблонов
                if hasattr(self, 'separator_input'):
                    # Убираем пробелы из разделителя - они добавятся автоматически
                    separator_value = (self.separator_input.value or '|').strip()
                    template_settings['separator'] = separator_value
                
                if hasattr(self, 'subgroup_brackets'):
                    template_settings['subgroup_brackets'] = self.subgroup_brackets.value or '[ ]'
                
                # Сохраняем символы
                if hasattr(self, 'name_chars'):
                    template_settings['name_chars'] = self.name_chars.value or 'А-ЯЁа-яёA-Za-z\\-\\.\\s'
                
                if hasattr(self, 'subdivision_chars'):
                    template_settings['subdivision_chars'] = self.subdivision_chars.value or 'А-ЯЁA-Zа-яё\\d'
            
            config['nickname_auto_replacement']['custom_templates'][self.template_id] = template_settings
            save_config(config)
            
            embed = discord.Embed(
                title="✅ Шаблон обновлен",
                description=f"Настройки шаблона '{self.template_config['name']}' сохранены.",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            # Показываем что изменилось
            changes = []
            for key, value in template_settings.items():
                if key == 'separator':
                    changes.append(f"Разделитель: `{value}`")
                elif key == 'subgroup_brackets':
                    changes.append(f"Скобки подгруппы: `{value}`")
                elif key == 'name_chars':
                    changes.append(f"Символы имен: `{value}`")
                elif key == 'subdivision_chars':
                    changes.append(f"Символы подразделений: `{value}`")
                elif key == 'status_text':
                    changes.append(f"Статус увольнения: `{value}`")
                    changes.append(f"Символы подразделений: `{value}`")
            
            if changes:
                embed.add_field(
                    name="Сохраненные настройки:",
                    value="\n".join(changes),
                    inline=False
                )
            
            embed.add_field(
                name="⚠️ Важно:",
                value="Перезапустите бота для применения изменений в системе парсинга.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Не удалось сохранить настройки: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)