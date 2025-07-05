"""
Department application channel configuration
"""
import discord
from discord import ui
from typing import Dict, List
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal


def auto_reload_config():
    """Automatically reload configuration in ping_manager"""
    try:
        from utils.ping_manager import ping_manager
        ping_manager.reload_config()
    except Exception as e:
        print(f"Warning: Could not auto-reload config: {e}")


async def show_department_channels_config(interaction: discord.Interaction):
    """Show department channels configuration main menu"""
    embed = discord.Embed(
        title="⚙️ Настройка каналов подразделений",
        description="Выберите подразделение для настройки каналов заявлений:",
        color=discord.Color.blue()
    )
    
    view = DepartmentChannelsConfigView()
    await interaction.response.edit_message(embed=embed, view=view)


class DepartmentChannelsConfigView(BaseSettingsView):
    """View for department application channel configuration"""
    
    def __init__(self):
        super().__init__()
        self.add_item(DepartmentChannelSelect())
        self.add_item(SetupAllChannelsButton())


class SetupAllChannelsButton(ui.Button):
    """Button to setup all department channels automatically"""
    
    def __init__(self):
        super().__init__(
            label="🛂 Проверить все каналы",
            style=discord.ButtonStyle.green,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Check and setup all department channels"""
        try:
            # Check admin permissions
            config = load_config()
            administrators = config.get('administrators', {})
            
            user_role_ids = [role.id for role in interaction.user.roles]
            is_admin = (
                interaction.user.id in administrators.get('users', []) or
                any(role_id in user_role_ids for role_id in administrators.get('roles', []))
            )
            
            if not is_admin:
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этой операции.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer()
            
            # Import and use DepartmentApplicationManager
            from forms.department_applications.manager import DepartmentApplicationManager
            from discord.ext import commands
            
            # Create mock bot for manager
            class MockBot:
                def __init__(self):
                    self.user = interaction.client.user
            
            app_manager = DepartmentApplicationManager(MockBot())
            results = await app_manager.setup_all_department_channels(interaction.guild)
            
            # Create result embed
            embed = discord.Embed(
                title="� Проверка каналов заявлений",
                description="Результат проверки и настройки каналов подразделений:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="ℹ️ Как это работает",
                value="Система автоматически ищет закрепленные сообщения с кнопками заявлений. "
                      "Если сообщение не найдено - создает новое и закрепляет его.",
                inline=False
            )
            
            for dept_code, result in results.items():
                embed.add_field(
                    name=f"{dept_code}",
                    value=result,
                    inline=True
                )
            
            if not results:
                embed.description = "❌ Нет настроенных каналов для подразделений."
                embed.color = discord.Color.red()
                embed.add_field(
                    name="💡 Подсказка",
                    value="Сначала настройте каналы для подразделений через меню выше.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🤖 Автоматический режим",
                    value="При каждом запуске бота система автоматически проверяет все каналы "
                          "и восстанавливает недостающие сообщения.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Произошла ошибка: {e}",
                ephemeral=True
            )


class DepartmentChannelSelect(ui.Select):
    """Select menu for choosing which department to configure"""
    
    def __init__(self):
        # Динамическая загрузка подразделений из конфигурации
        from utils.department_manager import DepartmentManager
        dept_manager = DepartmentManager()
        departments = dept_manager.get_all_departments()
        
        options = []
        for dept_code, dept_data in departments.items():
            name = dept_data.get('name', dept_code)
            description = f"Настроить канал для заявлений в {dept_code}"
            if dept_data.get('description'):
                description = f"Настроить канал для {dept_data['description'][:50]}..."
            emoji = dept_data.get('emoji', '�')
            
            # Ограничиваем длину описания для Discord
            if len(description) > 100:
                description = description[:97] + "..."
            
            options.append(discord.SelectOption(
                label=f"{dept_code} - {name}",
                description=description,
                emoji=emoji,
                value=dept_code
            ))
        
        # Сортируем по коду подразделения для стабильного порядка
        options.sort(key=lambda x: x.value)
        
        super().__init__(
            placeholder="Выберите подразделение для настройки...",
            options=options[:25]  # Discord ограничение на 25 опций
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle department selection"""
        try:
            department_code = self.values[0]
            await show_department_config(interaction, department_code)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка: {e}",
                ephemeral=True
            )


async def show_department_config(interaction: discord.Interaction, department_code: str):
    """Show configuration for a specific department"""
    config = load_config()
    departments = config.get('departments', {})
    dept_config = departments.get(department_code, {})
    
    # Get current settings
    channel_id = dept_config.get('application_channel_id')
    role_id = dept_config.get('role_id')
    
    # Create embed with current configuration
    embed = discord.Embed(
        title=f"⚙️ Настройка подразделения {department_code}",
        color=discord.Color.blue()
    )
    
    # Channel info
    if channel_id:
        channel = interaction.guild.get_channel(channel_id)
        channel_text = channel.mention if channel else f"❌ Канал не найден (ID: {channel_id})"
    else:
        channel_text = "❌ Не настроен"
    
    embed.add_field(
        name="📋 Канал заявлений",
        value=channel_text,
        inline=False
    )
    
    # Role info
    if role_id:
        role = interaction.guild.get_role(role_id)
        role_text = role.mention if role else f"❌ Роль не найдена (ID: {role_id})"
    else:
        role_text = "❌ Не настроена"
    
    embed.add_field(
        name="👤 Роль подразделения",
        value=role_text,
        inline=False
    )
    
    # Position roles info
    position_role_ids = dept_config.get('position_role_ids', [])
    assignable_position_role_ids = dept_config.get('assignable_position_role_ids', [])
    
    if position_role_ids:
        position_roles = []
        for role_id in position_role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                position_roles.append(role.mention)
            else:
                position_roles.append(f"❌ ID: {role_id}")
        position_text = "\n".join(position_roles) if position_roles else "❌ Не настроены"
    else:
        position_text = "❌ Не настроены"
    
    embed.add_field(
        name="🎖️ Роли должностей (все)",
        value=position_text[:1024],  # Discord field limit
        inline=False
    )
    
    if assignable_position_role_ids:
        assignable_roles = []
        for role_id in assignable_position_role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                assignable_roles.append(role.mention)
            else:
                assignable_roles.append(f"❌ ID: {role_id}")
        assignable_text = "\n".join(assignable_roles) if assignable_roles else "❌ Не настроены"
    else:
        assignable_text = "❌ Не настроены"
    
    embed.add_field(
        name="⭐ Выдаваемые должности",
        value=assignable_text[:1024],  # Discord field limit
        inline=False
    )
    
    # Add note about ping settings
    embed.add_field(
        name="📢 Настройки пингов",
        value="Пинги для этого подразделения настраиваются через `/settings - Настройки пингов`",
        inline=False
    )
    
    # Create view with configuration options
    view = DepartmentConfigActionsView(department_code)
    
    await interaction.response.edit_message(embed=embed, view=view)


class DepartmentConfigActionsView(BaseSettingsView):
    """View with actions for department configuration"""
    
    def __init__(self, department_code: str):
        super().__init__()
        self.department_code = department_code
        
        # Add configuration buttons
        self.add_item(DepartmentConfigButton("Настроить канал", "channel", department_code))
        self.add_item(DepartmentConfigButton("Настроить роль", "role", department_code))
        self.add_item(DepartmentConfigButton("Роли должностей (все)", "position_roles", department_code))
        self.add_item(DepartmentConfigButton("Выдаваемые должности", "assignable_positions", department_code))
        self.add_item(DepartmentConfigButton("◀️ Назад", "back", department_code))


class DepartmentConfigButton(ui.Button):
    """Button for department configuration actions"""
    
    def __init__(self, label: str, action: str, department_code: str):
        self.action = action
        self.department_code = department_code
        
        style = discord.ButtonStyle.primary
        if action == "back":
            style = discord.ButtonStyle.secondary
        
        super().__init__(label=label, style=style)
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button press"""
        try:
            if self.action == "back":
                view = DepartmentChannelsConfigView()
                embed = discord.Embed(
                    title="⚙️ Настройка каналов подразделений",
                    description="Выберите подразделение для настройки:",
                    color=discord.Color.blue()
                )
                await interaction.response.edit_message(embed=embed, view=view)
                
            elif self.action == "channel":
                modal = DepartmentChannelModal(self.department_code)
                await interaction.response.send_modal(modal)
                
            elif self.action == "role":
                modal = DepartmentRoleModal(self.department_code)
                await interaction.response.send_modal(modal)
                
            elif self.action == "position_roles":
                modal = DepartmentPositionRolesModal(self.department_code)
                await interaction.response.send_modal(modal)
                
            elif self.action == "assignable_positions":
                modal = DepartmentAssignablePositionsModal(self.department_code)
                await interaction.response.send_modal(modal)
                
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка: {e}",
                ephemeral=True
            )


class DepartmentChannelModal(BaseSettingsModal):
    """Modal for setting department application channel"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        super().__init__(title=f"Настройка канала {department_code}")
        
        # Get current channel
        config = load_config()
        current_channel_id = config.get('departments', {}).get(department_code, {}).get('application_channel_id')
        current_text = f"#{current_channel_id}" if current_channel_id else ""
        
        self.channel_input = ui.TextInput(
            label="Канал для заявлений",
            placeholder="#канал-заявлений или ID канала",
            default=current_text,
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        try:
            channel_text = self.channel_input.value.strip()
            
            # Parse channel
            channel = await self.parse_channel(interaction.guild, channel_text)
            if not channel:
                await interaction.response.send_message(
                    "❌ Канал не найден. Убедитесь, что вы указали правильное название или ID канала.",
                    ephemeral=True
                )
                return
            
            # Validate permissions
            bot_member = interaction.guild.get_member(interaction.client.user.id)
            permissions = channel.permissions_for(bot_member)
            
            missing_perms = []
            if not permissions.send_messages:
                missing_perms.append("Отправка сообщений")
            if not permissions.embed_links:
                missing_perms.append("Встраивание ссылок")
            if not permissions.manage_messages:
                missing_perms.append("Управление сообщениями")
            
            if missing_perms:
                await interaction.response.send_message(
                    f"❌ Боту не хватает следующих разрешений в канале {channel.mention}:\n" +
                    "\n".join(f"• {perm}" for perm in missing_perms),
                    ephemeral=True
                )
                return
            
            # Save to config
            config = load_config()
            if 'departments' not in config:
                config['departments'] = {}
            if self.department_code not in config['departments']:
                config['departments'][self.department_code] = {}
            
            config['departments'][self.department_code]['application_channel_id'] = channel.id
            save_config(config)
            auto_reload_config()  # Автоматическая перезагрузка конфигурации
            
            await interaction.response.send_message(
                f"✅ Канал заявлений для подразделения **{self.department_code}** установлен: {channel.mention}",
                ephemeral=True
            )
            
            # Refresh the configuration view
            await show_department_config(interaction, self.department_code)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при сохранении настроек: {e}",
                ephemeral=True
            )
    
    async def parse_channel(self, guild: discord.Guild, channel_text: str) -> discord.TextChannel:
        """Parse channel from text input"""
        # Remove # if present
        if channel_text.startswith('#'):
            channel_text = channel_text[1:]
        
        # Try to parse as ID
        try:
            channel_id = int(channel_text)
            return guild.get_channel(channel_id)
        except ValueError:
            pass
        
        # Try to find by name
        for channel in guild.text_channels:
            if channel.name == channel_text:
                return channel
        
        return None


class DepartmentRoleModal(BaseSettingsModal):
    """Modal for setting department role"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        super().__init__(title=f"Настройка роли {department_code}")
        
        # Get current role
        config = load_config()
        current_role_id = config.get('departments', {}).get(department_code, {}).get('role_id')
        current_text = f"@{current_role_id}" if current_role_id else ""
        
        self.role_input = ui.TextInput(
            label="Роль подразделения",
            placeholder="@роль или ID роли",
            default=current_text,
            required=True
        )
        self.add_item(self.role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        try:
            role_text = self.role_input.value.strip()
            
            # Parse role
            role = await self.parse_role(interaction.guild, role_text)
            if not role:
                await interaction.response.send_message(
                    "❌ Роль не найдена. Убедитесь, что вы указали правильное название или ID роли.",
                    ephemeral=True
                )
                return
            
            # Validate role hierarchy
            bot_member = interaction.guild.get_member(interaction.client.user.id)
            if role.position >= bot_member.top_role.position:
                await interaction.response.send_message(
                    f"❌ Роль {role.mention} находится выше роли бота в иерархии.\n"
                    f"Бот не сможет управлять этой ролью.",
                    ephemeral=True
                )
                return
            
            if role.managed:
                await interaction.response.send_message(
                    f"❌ Роль {role.mention} управляется интеграцией и не может быть изменена ботом.",
                    ephemeral=True
                )
                return
            
            # Save to config
            config = load_config()
            if 'departments' not in config:
                config['departments'] = {}
            if self.department_code not in config['departments']:
                config['departments'][self.department_code] = {}
            
            config['departments'][self.department_code]['role_id'] = role.id
            save_config(config)
            auto_reload_config()  # Автоматическая перезагрузка конфигурации
            
            await interaction.response.send_message(
                f"✅ Роль подразделения **{self.department_code}** установлена: {role.mention}",
                ephemeral=True
            )
            
            # Refresh the configuration view
            await show_department_config(interaction, self.department_code)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при сохранении настроек: {e}",
                ephemeral=True
            )
    
    async def parse_role(self, guild: discord.Guild, role_text: str) -> discord.Role:
        """Parse role from text input"""
        # Remove @ if present
        if role_text.startswith('@'):
            role_text = role_text[1:]
        
        # Try to parse as ID
        try:
            role_id = int(role_text)
            return guild.get_role(role_id)
        except ValueError:
            pass
        
        # Try to find by name
        for role in guild.roles:
            if role.name == role_text:
                return role
        
        return None


class DepartmentPositionRolesModal(BaseSettingsModal):
    """Modal for configuring all position roles for a department"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        
        # Get current configuration
        config = load_config()
        departments = config.get('departments', {})
        dept_config = departments.get(department_code, {})
        current_roles = dept_config.get('position_role_ids', [])
        
        # Convert to text
        current_text = "\n".join([str(role_id) for role_id in current_roles]) if current_roles else ""
        
        super().__init__(title=f"Роли должностей - {department_code}")
        
        self.roles_input = ui.TextInput(
            label="Роли должностей (все)",
            placeholder="ID ролей или @упоминания через новую строку\nПример: @Рядовой",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            default=current_text,
            required=False
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle position roles configuration"""
        try:
            await interaction.response.defer()
            
            roles_text = self.roles_input.value.strip()
            role_ids = []
            
            if roles_text:
                # Parse roles
                lines = [line.strip() for line in roles_text.split('\n') if line.strip()]
                for line in lines:
                    role = await self.parse_role(interaction.guild, line)
                    if role:
                        role_ids.append(role.id)
                    else:
                        await interaction.followup.send(
                            f"❌ Роль не найдена: `{line}`\nНастройка отменена.",
                            ephemeral=True
                        )
                        return
            
            # Save configuration
            config = load_config()
            if 'departments' not in config:
                config['departments'] = {}
            if self.department_code not in config['departments']:
                config['departments'][self.department_code] = {}
            
            config['departments'][self.department_code]['position_role_ids'] = role_ids
            save_config(config)
            auto_reload_config()  # Автоматическая перезагрузка конфигурации
            
            roles_mention = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    roles_mention.append(role.mention)
            
            await interaction.followup.send(
                f"✅ **Роли должностей для {self.department_code} обновлены!**\n"
                f"📝 Количество ролей: {len(role_ids)}\n"
                f"🎖️ Роли: {', '.join(roles_mention) if roles_mention else 'Нет ролей'}",
                ephemeral=True
            )
            
            # Return to department config using edit instead of response
            await self._refresh_department_config(interaction)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Произошла ошибка при настройке ролей должностей: {e}",
                ephemeral=True
            )
    
    async def _refresh_department_config(self, interaction: discord.Interaction):
        """Refresh department configuration view after defer"""
        config = load_config()
        departments = config.get('departments', {})
        dept_config = departments.get(self.department_code, {})
        
        # Get current settings
        channel_id = dept_config.get('application_channel_id')
        role_id = dept_config.get('role_id')
        
        # Create embed with current configuration
        embed = discord.Embed(
            title=f"⚙️ Настройка подразделения {self.department_code}",
            color=discord.Color.blue()
        )
        
        # Channel info
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            channel_text = channel.mention if channel else f"❌ Канал не найден (ID: {channel_id})"
        else:
            channel_text = "❌ Не настроен"
        
        embed.add_field(
            name="📋 Канал заявлений",
            value=channel_text,
            inline=False
        )
        
        # Role info
        if role_id:
            role = interaction.guild.get_role(role_id)
            role_text = role.mention if role else f"❌ Роль не найдена (ID: {role_id})"
        else:
            role_text = "❌ Не настроена"
        
        embed.add_field(
            name="👤 Роль подразделения",
            value=role_text,
            inline=False
        )
        
        # Position roles info
        position_role_ids = dept_config.get('position_role_ids', [])
        assignable_position_role_ids = dept_config.get('assignable_position_role_ids', [])
        
        if position_role_ids:
            position_roles = []
            for role_id in position_role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    position_roles.append(role.mention)
                else:
                    position_roles.append(f"❌ ID: {role_id}")
            position_text = "\n".join(position_roles) if position_roles else "❌ Не настроены"
        else:
            position_text = "❌ Не настроены"
        
        embed.add_field(
            name="🎖️ Роли должностей (все)",
            value=position_text[:1024],  # Discord field limit
            inline=False
        )
        
        if assignable_position_role_ids:
            assignable_roles = []
            for role_id in assignable_position_role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    assignable_roles.append(role.mention)
                else:
                    assignable_roles.append(f"❌ ID: {role_id}")
            assignable_text = "\n".join(assignable_roles) if assignable_roles else "❌ Не настроены"
        else:
            assignable_text = "❌ Не настроены"
        
        embed.add_field(
            name="⭐ Выдаваемые должности",
            value=assignable_text[:1024],  # Discord field limit
            inline=False
        )
        
        # Add note about ping settings
        embed.add_field(
            name="📢 Настройки пингов",
            value="Пинги для этого подразделения настраиваются через `/settings - Настройки пингов`",
            inline=False
        )
        
        # Create view with configuration options
        view = DepartmentConfigActionsView(self.department_code)
        
        await interaction.edit_original_response(embed=embed, view=view)


class DepartmentAssignablePositionsModal(BaseSettingsModal):
    """Modal for configuring assignable position roles for a department"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        
        # Get current configuration
        config = load_config()
        departments = config.get('departments', {})
        dept_config = departments.get(department_code, {})
        current_roles = dept_config.get('assignable_position_role_ids', [])
        
        # Convert to text
        current_text = "\n".join([str(role_id) for role_id in current_roles]) if current_roles else ""
        
        super().__init__(title=f"Выдаваемые должности - {department_code}")
        
        self.roles_input = ui.TextInput(
            label="Выдаваемые должности",
            placeholder="ID ролей или @упоминания через новую строку\nАвтоматически выдаются новичкам",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            default=current_text,
            required=False
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle assignable position roles configuration"""
        try:
            await interaction.response.defer()
            
            roles_text = self.roles_input.value.strip()
            role_ids = []
            
            if roles_text:
                # Parse roles
                lines = [line.strip() for line in roles_text.split('\n') if line.strip()]
                for line in lines:
                    role = await self.parse_role(interaction.guild, line)
                    if role:
                        role_ids.append(role.id)
                    else:
                        await interaction.followup.send(
                            f"❌ Роль не найдена: `{line}`\nНастройка отменена.",
                            ephemeral=True
                        )
                        return
            
            # Save configuration
            config = load_config()
            if 'departments' not in config:
                config['departments'] = {}
            if self.department_code not in config['departments']:
                config['departments'][self.department_code] = {}
            
            config['departments'][self.department_code]['assignable_position_role_ids'] = role_ids
            save_config(config)
            auto_reload_config()  # Автоматическая перезагрузка конфигурации
            
            roles_mention = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    roles_mention.append(role.mention)
            
            await interaction.followup.send(
                f"✅ **Выдаваемые должности для {self.department_code} обновлены!**\n"
                f"📝 Количество ролей: {len(role_ids)}\n"
                f"⭐ Роли: {', '.join(roles_mention) if roles_mention else 'Нет ролей'}\n"
                f"💡 Эти роли будут автоматически выдаваться при одобрении заявлений.",
                ephemeral=True
            )
            
            # Return to department config using edit instead of response
            await self._refresh_department_config(interaction)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Произошла ошибка при настройке выдаваемых должностей: {e}",
                ephemeral=True
            )
    
    async def _refresh_department_config(self, interaction: discord.Interaction):
        """Refresh department configuration view after defer"""
        config = load_config()
        departments = config.get('departments', {})
        dept_config = departments.get(self.department_code, {})
        
        # Get current settings
        channel_id = dept_config.get('application_channel_id')
        role_id = dept_config.get('role_id')
        
        # Create embed with current configuration
        embed = discord.Embed(
            title=f"⚙️ Настройка подразделения {self.department_code}",
            color=discord.Color.blue()
        )
        
        # Channel info
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            channel_text = channel.mention if channel else f"❌ Канал не найден (ID: {channel_id})"
        else:
            channel_text = "❌ Не настроен"
        
        embed.add_field(
            name="📋 Канал заявлений",
            value=channel_text,
            inline=False
        )
        
        # Role info
        if role_id:
            role = interaction.guild.get_role(role_id)
            role_text = role.mention if role else f"❌ Роль не найдена (ID: {role_id})"
        else:
            role_text = "❌ Не настроена"
        
        embed.add_field(
            name="👤 Роль подразделения",
            value=role_text,
            inline=False
        )
        
        # Position roles info
        position_role_ids = dept_config.get('position_role_ids', [])
        assignable_position_role_ids = dept_config.get('assignable_position_role_ids', [])
        
        if position_role_ids:
            position_roles = []
            for role_id in position_role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    position_roles.append(role.mention)
                else:
                    position_roles.append(f"❌ ID: {role_id}")
            position_text = "\n".join(position_roles) if position_roles else "❌ Не настроены"
        else:
            position_text = "❌ Не настроены"
        
        embed.add_field(
            name="🎖️ Роли должностей (все)",
            value=position_text[:1024],  # Discord field limit
            inline=False
        )
        
        if assignable_position_role_ids:
            assignable_roles = []
            for role_id in assignable_position_role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    assignable_roles.append(role.mention)
                else:
                    assignable_roles.append(f"❌ ID: {role_id}")
            assignable_text = "\n".join(assignable_roles) if assignable_roles else "❌ Не настроены"
        else:
            assignable_text = "❌ Не настроены"
        
        embed.add_field(
            name="⭐ Выдаваемые должности",
            value=assignable_text[:1024],  # Discord field limit
            inline=False
        )
        
        # Add note about ping settings
        embed.add_field(
            name="📢 Настройки пингов",
            value="Пинги для этого подразделения настраиваются через `/settings - Настройки пингов`",
            inline=False
        )
        
        # Create view with configuration options
        view = DepartmentConfigActionsView(self.department_code)
        
        await interaction.edit_original_response(embed=embed, view=view)
