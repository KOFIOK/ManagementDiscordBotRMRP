"""
Modern ping settings configuration with context support
"""
import discord
from discord import ui
from typing import Dict, List, Optional
from utils.config_manager import load_config, save_config
from utils.ping_manager import ping_manager
from .base import BaseSettingsView, BaseSettingsModal, RoleParser


async def show_ping_settings_overview(interaction: discord.Interaction):
    """Show overview of current ping settings"""
    config = load_config()
    departments = config.get('departments', {})
    legacy_settings = config.get('ping_settings', {})
    
    embed = discord.Embed(
        title="📢 Настройки пингов",
        description="Управление уведомлениями для подразделений по различным типам заявок.",
        color=discord.Color.orange()
    )
    
    # Show current department ping contexts
    has_modern_settings = False
    for dept_code, dept_config in departments.items():
        ping_contexts = dept_config.get('ping_contexts', {})
        if ping_contexts:
            has_modern_settings = True
            context_info = ""
            for context, role_ids in ping_contexts.items():
                context_name = ping_manager.CONTEXTS.get(context, context)
                role_mentions = []
                for role_id in role_ids:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_mentions.append(role.mention)
                
                if role_mentions:
                    context_info += f"**{context_name}:** {', '.join(role_mentions)}\n"
            
            if context_info:
                embed.add_field(
                    name=f"🎯 {dept_code}",
                    value=context_info,
                    inline=False
                )
    
    # Show legacy settings if they exist
    if legacy_settings:
        legacy_info = ""
        for dept_role_id_str, ping_role_ids in legacy_settings.items():
            dept_role = interaction.guild.get_role(int(dept_role_id_str))
            if dept_role:
                ping_roles = []
                for role_id in ping_role_ids:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        ping_roles.append(role.mention)
                
                if ping_roles:
                    legacy_info += f"**{dept_role.mention}:** {', '.join(ping_roles)}\n"
        
        if legacy_info:
            embed.add_field(
                name="⚠️ Устаревшие настройки",
                value=f"{legacy_info}\n*Рекомендуется выполнить миграцию для полной совместимости.*",
                inline=False
            )
    
    if not has_modern_settings and not legacy_settings:
        embed.add_field(
            name="📝 Состояние",
            value="❌ Пинги не настроены. Выберите подразделение для настройки.",
            inline=False
        )
    
    embed.add_field(
        name="ℹ️ Инструкция:",
        value=(
            "1. Выберите подразделение из списка ниже\n"
            "2. Выберите тип уведомлений для настройки\n"
            "3. Укажите роли для пинга\n"
            "4. При необходимости мигрируйте старые настройки"
        ),
        inline=False
    )
    
    view = ModernPingSettingsView()
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class ModernPingSettingsView(BaseSettingsView):
    """Modern view for managing ping settings with context support"""
    
    def __init__(self):
        super().__init__()
        self.add_item(DepartmentPingSelect())
        
        # Add legacy migration button if needed
        config = load_config()
        if config.get('ping_settings', {}):
            self.add_item(MigrateLegacyButton())
        
        self.add_item(ShowOverviewButton())


class DepartmentPingSelect(ui.Select):
    """Select menu for choosing department to configure pings"""
    
    def __init__(self):
        # Динамическая загрузка подразделений из конфигурации
        from utils.department_manager import DepartmentManager
        dept_manager = DepartmentManager()
        departments = dept_manager.get_all_departments()
        
        options = []
        for dept_code, dept_data in departments.items():
            name = dept_data.get('name', dept_code)
            description = dept_data.get('description', f'Настроить пинги для {dept_code}')
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
            placeholder="Выберите подразделение для настройки пингов...",
            options=options[:25]  # Discord ограничение на 25 опций
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle department selection"""
        try:
            department_code = self.values[0]
            await show_department_ping_config(interaction, department_code)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка: {e}",
                ephemeral=True
            )


async def show_department_ping_config(interaction: discord.Interaction, department_code: str):
    """Show ping configuration for a specific department"""
    config = load_config()
    departments = config.get('departments', {})
    dept_config = departments.get(department_code, {})
    ping_contexts = dept_config.get('ping_contexts', {})
    
    # Create embed with current configuration
    embed = discord.Embed(
        title=f"📢 Настройка пингов для {department_code}",
        description="Настройте уведомления для различных типов заявок и действий:",
        color=discord.Color.orange()
    )
    
    # Show current ping contexts
    for context_key, context_name in ping_manager.CONTEXTS.items():
        role_ids = ping_contexts.get(context_key, [])
        
        if role_ids:
            role_mentions = []
            for role_id in role_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
            
            value = ', '.join(role_mentions) if role_mentions else "❌ Роли не найдены"
        else:
            value = "❌ Не настроено"
        
        embed.add_field(
            name=f"**{context_name}**",
            value=value,
            inline=False
        )
    
    # Add migration info if legacy settings exist
    legacy_settings = config.get('ping_settings', {})
    if legacy_settings:
        embed.add_field(
            name="⚠️ Обнаружены устаревшие настройки",
            value="Рекомендуется выполнить миграцию настроек пингов для полной совместимости.",
            inline=False
        )
    
    view = DepartmentPingActionsView(department_code)
    await interaction.response.edit_message(embed=embed, view=view)


class DepartmentPingActionsView(BaseSettingsView):
    """View with actions for department ping configuration"""
    
    def __init__(self, department_code: str):
        super().__init__()
        self.department_code = department_code
        
        # Add context selection
        self.add_item(PingContextSelect(department_code))
        
        # Add navigation buttons
        self.add_item(BackToPingSettingsButton())
        self.add_item(MigrateLegacyButton())


class PingContextSelect(ui.Select):
    """Select menu for choosing ping context to configure"""
    
    def __init__(self, department_code: str):
        self.department_code = department_code
        
        options = []
        for context_key, context_name in ping_manager.CONTEXTS.items():
            options.append(discord.SelectOption(
                label=context_name,
                description=f"Настроить пинги для: {context_name.lower()}",
                value=context_key
            ))
        
        super().__init__(
            placeholder="Выберите тип уведомлений для настройки...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle context selection"""
        try:
            context = self.values[0]
            modal = PingContextModal(self.department_code, context)
            await interaction.response.send_modal(modal)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка: {e}",
                ephemeral=True
            )


class PingContextModal(BaseSettingsModal):
    """Modal for setting ping roles for a specific context"""
    
    def __init__(self, department_code: str, context: str):
        self.department_code = department_code
        self.context = context
        context_name = ping_manager.CONTEXTS.get(context, context)
        
        super().__init__(title=f"Пинги {department_code}: {context_name}")
        
        # Get current settings
        config = load_config()
        dept_config = config.get('departments', {}).get(department_code, {})
        ping_contexts = dept_config.get('ping_contexts', {})
        current_role_ids = ping_contexts.get(context, [])
        
        # Build current roles display
        current_text = ""
        if current_role_ids:
            current_text = ", ".join(f"<@&{role_id}>" for role_id in current_role_ids)
        
        self.roles_input = ui.TextInput(
            label=f"Роли уведомлений: {context_name}",
            placeholder="@Роль1, @Роль2, ID1, ID2 или 'очистить' для удаления",
            style=discord.TextStyle.paragraph,
            default=current_text,
            required=False,
            max_length=1000
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            input_value = self.roles_input.value.strip()
            context_name = ping_manager.CONTEXTS.get(self.context, self.context)
            
            # Handle clearing
            if input_value.lower() in ['очистить', 'удалить', 'clear', '']:
                await self._clear_ping_context(interaction)
                return
            
            # Parse roles
            ping_roles = RoleParser.parse_multiple_roles(input_value, interaction.guild)
            
            if not ping_roles:
                await self.send_error_message(
                    interaction,
                    "Роли не найдены",
                    f"Не удалось найти роли для пинга: `{input_value}`"
                )
                return
            
            # Save to config
            config = load_config()
            if 'departments' not in config:
                config['departments'] = {}
            if self.department_code not in config['departments']:
                config['departments'][self.department_code] = {}
            if 'ping_contexts' not in config['departments'][self.department_code]:
                config['departments'][self.department_code]['ping_contexts'] = {}
            
            config['departments'][self.department_code]['ping_contexts'][self.context] = [role.id for role in ping_roles]
            save_config(config)
            
            ping_roles_mentions = [role.mention for role in ping_roles]
            await self.send_success_message(
                interaction,
                f"Пинги настроены для {self.department_code}",
                f"**{context_name}:** {', '.join(ping_roles_mentions)}\n\n"
                f"Теперь при {context_name.lower()} в {self.department_code} будут уведомлены указанные роли."
            )
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка",
                f"Произошла ошибка при настройке пингов: {str(e)}"
            )
    
    async def _clear_ping_context(self, interaction: discord.Interaction):
        """Clear ping context for department"""
        config = load_config()
        dept_config = config.get('departments', {}).get(self.department_code, {})
        ping_contexts = dept_config.get('ping_contexts', {})
        
        if self.context in ping_contexts:
            del ping_contexts[self.context]
            
            # Clean up empty ping_contexts
            if not ping_contexts:
                dept_config.pop('ping_contexts', None)
            
            save_config(config)
        
        context_name = ping_manager.CONTEXTS.get(self.context, self.context)
        await self.send_success_message(
            interaction,
            f"Пинги очищены для {self.department_code}",
            f"Уведомления для **{context_name}** в {self.department_code} отключены."
        )


class BackToPingSettingsButton(ui.Button):
    """Button to go back to main ping settings"""
    
    def __init__(self):
        super().__init__(
            label="◀️ К настройкам пингов",
            style=discord.ButtonStyle.secondary
        )
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📢 Настройки пингов",
            description="Выберите подразделение для настройки уведомлений:",
            color=discord.Color.orange()
        )
        
        view = ModernPingSettingsView()
        await interaction.response.edit_message(embed=embed, view=view)


class MigrateLegacyButton(ui.Button):
    """Button to migrate legacy ping settings"""
    
    def __init__(self):
        super().__init__(
            label="🔄 Мигрировать старые настройки",
            style=discord.ButtonStyle.danger
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Migrate legacy ping settings to new structure"""
        try:
            config = load_config()
            legacy_settings = config.get('ping_settings', {})
            
            if not legacy_settings:
                await interaction.response.send_message(
                    "ℹ️ Старые настройки пингов не найдены.",
                    ephemeral=True
                )
                return
            
            migrated_count = 0
            migration_log = []
            
            # Migrate each legacy setting
            for dept_role_id_str, ping_role_ids in legacy_settings.items():
                dept_role = interaction.guild.get_role(int(dept_role_id_str))
                if not dept_role:
                    continue
                
                # Try to match role to department
                department_code = self._match_role_to_department(dept_role.name)
                if not department_code:
                    migration_log.append(f"❌ Не удалось определить подразделение для роли {dept_role.mention}")
                    continue
                
                # Migrate to new structure
                if 'departments' not in config:
                    config['departments'] = {}
                if department_code not in config['departments']:
                    config['departments'][department_code] = {}
                if 'ping_contexts' not in config['departments'][department_code]:
                    config['departments'][department_code]['ping_contexts'] = {}
                
                # Set role_id if not set
                if 'role_id' not in config['departments'][department_code]:
                    config['departments'][department_code]['role_id'] = int(dept_role_id_str)
                
                # Migrate ping roles to general context (backward compatibility)
                config['departments'][department_code]['ping_contexts']['general'] = ping_role_ids
                config['departments'][department_code]['ping_contexts']['dismissals'] = ping_role_ids
                config['departments'][department_code]['ping_contexts']['leave_requests'] = ping_role_ids
                
                migrated_count += 1
                migration_log.append(f"✅ {department_code}: {dept_role.mention} -> общие уведомления")
            
            # Clear legacy settings
            if migrated_count > 0:
                config['ping_settings'] = {}
                save_config(config)
            
            # Report results
            if migrated_count > 0:
                log_text = "\n".join(migration_log)
                await interaction.response.send_message(
                    f"✅ **Миграция завершена!**\n\n"
                    f"Мигрировано настроек: **{migrated_count}**\n\n"
                    f"**Детали:**\n{log_text}\n\n"
                    f"Старые настройки удалены. Теперь используется новая система с поддержкой контекстов.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "⚠️ Не удалось мигрировать настройки. Проверьте логи для подробностей.",
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при миграции: {e}",
                ephemeral=True
            )
    
    def _match_role_to_department(self, role_name: str) -> Optional[str]:
        """Match role name to department code"""
        role_name_lower = role_name.lower()
        
        for dept_code, patterns in ping_manager.DEPARTMENT_PATTERNS.items():
            for pattern in patterns:
                if pattern in role_name_lower:
                    return dept_code
        
        return None


class ShowOverviewButton(ui.Button):
    """Button to show ping settings overview"""
    
    def __init__(self):
        super().__init__(
            label="📋 Обзор настроек",
            style=discord.ButtonStyle.secondary
        )
    
    async def callback(self, interaction: discord.Interaction):
        await show_ping_settings_overview(interaction)
