"""
Department application channel configuration
"""
import discord
from discord import ui
from typing import Dict, List
from utils.config_manager import load_config, save_config
from utils.ping_manager import ping_manager
from .base import BaseSettingsView, BaseSettingsModal


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


class DepartmentChannelSelect(ui.Select):
    """Select menu for choosing which department to configure"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="УВП - Учебно-Воспитательное Подразделение",
                description="Настроить канал для заявлений в УВП",
                emoji="🎓",
                value="УВП"
            ),
            discord.SelectOption(
                label="ССО - Силы Специальных Операций",
                description="Настроить канал для заявлений в ССО",
                emoji="🎯",
                value="ССО"
            ),
            discord.SelectOption(
                label="РОиО - Разведывательный Отдел и Оборона", 
                description="Настроить канал для заявлений в РОиО",
                emoji="🔍",
                value="РОиО"
            ),
            discord.SelectOption(
                label="ВК - Военная Комендатура",
                description="Настроить канал для заявлений в ВК",
                emoji="🚔",
                value="ВК"
            ),
            discord.SelectOption(
                label="МР - Медицинская Рота",
                description="Настроить канал для заявлений в МР",
                emoji="🏥",
                value="МР"
            )
        ]
        
        super().__init__(
            placeholder="Выберите подразделение для настройки...",
            options=options
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
    ping_contexts = dept_config.get('ping_contexts', {})
    
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
    
    # Ping contexts info
    ping_info = ""
    for context, role_ids in ping_contexts.items():
        context_name = ping_manager.CONTEXTS.get(context, context)
        role_mentions = []
        for role_id in role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                role_mentions.append(role.mention)
        
        if role_mentions:
            ping_info += f"**{context_name}:** {', '.join(role_mentions)}\n"
        else:
            ping_info += f"**{context_name}:** ❌ Роли не найдены\n"
    
    if not ping_info:
        ping_info = "❌ Пинги не настроены"
    
    embed.add_field(
        name="📢 Пинги по контекстам",
        value=ping_info,
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
        self.add_item(DepartmentConfigButton("Настроить пинги", "pings", department_code))
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
                
            elif self.action == "pings":
                view = DepartmentPingContextView(self.department_code)
                embed = discord.Embed(
                    title=f"📢 Настройка пингов для {self.department_code}",
                    description="Выберите контекст для настройки пингов:",
                    color=discord.Color.blue()
                )
                await interaction.response.edit_message(embed=embed, view=view)
                
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


class DepartmentPingContextView(BaseSettingsView):
    """View for selecting ping context to configure"""
    
    def __init__(self, department_code: str):
        super().__init__()
        self.department_code = department_code
        self.add_item(PingContextSelect(department_code))


class PingContextSelect(ui.Select):
    """Select menu for choosing ping context"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        
        options = [
            discord.SelectOption(
                label="Заявления в подразделения",
                description="Пинги при подаче заявлений в подразделение",
                emoji="📋",
                value="applications"
            ),
            discord.SelectOption(
                label="Рапорты на отпуск",
                description="Пинги при подаче рапортов на отпуск",
                emoji="🏖️",
                value="leave_requests"
            ),
            discord.SelectOption(
                label="Увольнения",
                description="Пинги при увольнениях из подразделения",
                emoji="📝", 
                value="dismissals"
            ),
            discord.SelectOption(
                label="Складские запросы",
                description="Пинги при складских запросах",
                emoji="📦",
                value="warehouse"
            ),
            discord.SelectOption(
                label="Общие уведомления",
                description="Общие пинги подразделения",
                emoji="📢",
                value="general"
            )
        ]
        
        super().__init__(
            placeholder="Выберите контекст для настройки пингов...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle context selection"""
        try:
            context = self.values[0]
            modal = DepartmentPingModal(self.department_code, context)
            await interaction.response.send_modal(modal)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка: {e}",
                ephemeral=True
            )


class DepartmentPingModal(BaseSettingsModal):
    """Modal for setting ping roles for specific context"""
    
    def __init__(self, department_code: str, context: str):
        self.department_code = department_code
        self.context = context
        context_name = ping_manager.CONTEXTS.get(context, context)
        super().__init__(title=f"Пинги {department_code}: {context_name}")
        
        # Get current ping roles
        config = load_config()
        current_roles = config.get('departments', {}).get(department_code, {}).get('ping_contexts', {}).get(context, [])
        current_text = " ".join([f"<@&{role_id}>" for role_id in current_roles])
        
        self.roles_input = ui.TextInput(
            label="Роли для пинга",
            placeholder="@роль1 @роль2 или ID ролей через пробел",
            default=current_text,
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        try:
            roles_text = self.roles_input.value.strip()
            
            if not roles_text:
                # Clear ping settings for this context
                config = load_config()
                if 'departments' in config and self.department_code in config['departments']:
                    ping_contexts = config['departments'][self.department_code].get('ping_contexts', {})
                    if self.context in ping_contexts:
                        del ping_contexts[self.context]
                        save_config(config)
                
                await interaction.response.send_message(
                    f"✅ Пинги для контекста **{ping_manager.CONTEXTS.get(self.context, self.context)}** "
                    f"в подразделении **{self.department_code}** очищены.",
                    ephemeral=True
                )
                return
            
            # Parse roles
            role_ids = []
            role_parts = roles_text.split()
            
            for part in role_parts:
                role = await self.parse_role(interaction.guild, part)
                if role:
                    role_ids.append(role.id)
                else:
                    await interaction.response.send_message(
                        f"❌ Роль не найдена: {part}",
                        ephemeral=True
                    )
                    return
            
            if not role_ids:
                await interaction.response.send_message(
                    "❌ Не найдено ни одной действительной роли.",
                    ephemeral=True
                )
                return
            
            # Save to config
            ping_manager.set_ping_context(self.department_code, self.context, role_ids)
            
            # Create confirmation message
            role_mentions = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
            
            await interaction.response.send_message(
                f"✅ Пинги для контекста **{ping_manager.CONTEXTS.get(self.context, self.context)}** "
                f"в подразделении **{self.department_code}** настроены:\n"
                f"{' '.join(role_mentions)}",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при сохранении настроек: {e}",
                ephemeral=True
            )
    
    async def parse_role(self, guild: discord.Guild, role_text: str) -> discord.Role:
        """Parse role from text input"""
        # Handle mention format <@&ID>
        if role_text.startswith('<@&') and role_text.endswith('>'):
            try:
                role_id = int(role_text[3:-1])
                return guild.get_role(role_id)
            except ValueError:
                pass
        
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
