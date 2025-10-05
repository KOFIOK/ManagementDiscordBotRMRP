"""
Nickname auto-replacement settings configuration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView
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


class NicknameSettingsView(NicknameBaseView):
    """Main nickname settings interface"""
    
    def __init__(self):
        super().__init__()
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
            )
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
    
    async def show_global_settings(self, interaction: discord.Interaction):
        """Show global nickname replacement settings"""
        config = load_config()
        nickname_settings = config.get('nickname_auto_replacement', {})
        global_enabled = nickname_settings.get('enabled', True)
        
        embed = discord.Embed(
            title="🌐 Глобальные настройки автозамены",
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
            title="✅ Настройки обновлены",
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
            title="✅ Настройки обновлены",
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
            title="✅ Настройки обновлены",
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
            "• **По модулям** - настройка для типов операций"
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
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)