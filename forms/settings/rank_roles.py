"""
Rank roles configuration management
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from .base import BaseSettingsView, BaseSettingsModal


class RankRoleModal(BaseSettingsModal):
    """Modal for adding/editing rank roles"""
    
    def __init__(self, edit_rank=None):
        self.edit_rank = edit_rank
        title = f"Редактировать звание: {edit_rank}" if edit_rank else "Добавить звание"
        super().__init__(title=title)
        
        config = load_config()
        rank_roles = config.get('rank_roles', {})
        
        # If editing, get current values
        current_role_id = ""
        if edit_rank and edit_rank in rank_roles:
            current_role_id = str(rank_roles[edit_rank])
        
        self.rank_name = ui.TextInput(
            label="Название звания",
            placeholder="Например: Рядовой, Капитан, Генерал-майор",
            min_length=2,
            max_length=50,
            required=True,
            default=edit_rank if edit_rank else ""
        )
        self.add_item(self.rank_name)
        
        self.role_id = ui.TextInput(
            label="ID роли или упоминание",
            placeholder="Например: @Рядовой или 1246114675574313021",
            min_length=1,
            max_length=100,
            required=True,
            default=current_role_id
        )
        self.add_item(self.role_id)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            rank_name = self.rank_name.value.strip()
            role_input = self.role_id.value.strip()
            
            # Parse role ID
            role_id = self._parse_role_input(role_input)
            if not role_id:
                await self.send_error_message(
                    interaction,
                    "Неверный формат роли",
                    f"Не удалось распознать роль из '{role_input}'"
                )
                return
            
            # Verify role exists
            role = interaction.guild.get_role(role_id)
            if not role:
                await self.send_error_message(
                    interaction,
                    "Роль не найдена",
                    f"Роль с ID {role_id} не найдена на сервере."
                )
                return
            
            # Save to config
            config = load_config()
            if 'rank_roles' not in config:
                config['rank_roles'] = {}
            
            # If editing and name changed, remove old entry
            if self.edit_rank and self.edit_rank != rank_name and self.edit_rank in config['rank_roles']:
                del config['rank_roles'][self.edit_rank]
            
            config['rank_roles'][rank_name] = role_id
            save_config(config)
            
            # Success message
            action = "обновлено" if self.edit_rank else "добавлено"
            embed = discord.Embed(
                title="✅ Звание успешно настроено",
                description=f"Звание **{rank_name}** {action}!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name="📋 Детали:",
                value=f"**Звание:** {rank_name}\n**Роль:** {role.mention} (`{role_id}`)",
                inline=False
            )
            
            view = RankRolesConfigView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка сохранения",
                f"Произошла ошибка при сохранении звания: {e}"
            )
    
    def _parse_role_input(self, role_input: str) -> int:
        """Parse role input and extract role ID"""
        try:
            # Remove mention brackets if present
            role_input = role_input.strip()
            if role_input.startswith('<@&') and role_input.endswith('>'):
                role_input = role_input[3:-1]
            
            # Try to convert to int
            return int(role_input)
        except ValueError:
            return None


class KeyRoleModal(BaseSettingsModal):
    """Modal for setting the key role for rank synchronization"""
    
    def __init__(self):
        super().__init__(title="Настройка ключевой роли")
        
        config = load_config()
        current_key_role_id = config.get('rank_sync_key_role')
        current_key_role_display = str(current_key_role_id) if current_key_role_id else ""
        
        self.role_input = ui.TextInput(
            label="ID роли или упоминание",
            placeholder="Например: @Военнослужащие или 1234567890123456789",
            min_length=1,
            max_length=100,
            required=True,
            default=current_key_role_display
        )
        self.add_item(self.role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            role_input = self.role_input.value.strip()
            
            # Parse role ID
            role_id = self._parse_role_input(role_input)
            if not role_id:
                await self.send_error_message(
                    interaction,
                    "Неверный формат роли",
                    f"Не удалось распознать роль из '{role_input}'"
                )
                return
            
            # Verify role exists
            role = interaction.guild.get_role(role_id)
            if not role:
                await self.send_error_message(
                    interaction,
                    "Роль не найдена",
                    f"Роль с ID {role_id} не найдена на сервере."
                )
                return
            
            # Save to config
            config = load_config()
            config['rank_sync_key_role'] = role_id
            save_config(config)
            
            embed = discord.Embed(
                title="✅ Ключевая роль настроена",
                description=f"Теперь система будет проверять активность только у участников с ролью **{role.name}**",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name="🔑 Ключевая роль:",
                value=f"{role.mention} (`{role_id}`)",
                inline=False
            )
            embed.add_field(
                name="ℹ️ Информация:",
                value=(
                    "Участники без этой роли не будут проверяться системой синхронизации званий.\n"
                    "Это значительно повышает производительность на больших серверах."
                ),
                inline=False
            )
            
            view = RankRolesConfigView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка сохранения",
                f"Произошла ошибка при сохранении ключевой роли: {e}"
            )
    
    def _parse_role_input(self, role_input: str) -> int:
        """Parse role input and extract role ID"""
        try:
            # Remove mention brackets if present
            role_input = role_input.strip()
            if role_input.startswith('<@&') and role_input.endswith('>'):
                role_input = role_input[3:-1]
            
            # Try to convert to int
            return int(role_input)
        except ValueError:
            return None


class RankRoleDeleteConfirmModal(BaseSettingsModal):
    """Confirmation modal for deleting rank roles"""
    
    def __init__(self, rank_name: str):
        self.rank_name = rank_name
        super().__init__(title=f"Удалить звание: {rank_name}")
        
        self.confirmation = ui.TextInput(
            label=f"Введите название звания для подтверждения",
            placeholder=f"{rank_name}",
            min_length=len(rank_name),
            max_length=len(rank_name) + 10,
            required=True
        )
        self.add_item(self.confirmation)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.confirmation.value.strip() != self.rank_name:
                await self.send_error_message(
                    interaction,
                    "Неверное подтверждение",
                    f"Введенное название не соответствует '{self.rank_name}'"
                )
                return
            
            # Remove from config
            config = load_config()
            if 'rank_roles' in config and self.rank_name in config['rank_roles']:
                del config['rank_roles'][self.rank_name]
                save_config(config)
                
                embed = discord.Embed(
                    title="✅ Звание удалено",
                    description=f"Звание **{self.rank_name}** успешно удалено из конфигурации.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                view = RankRolesConfigView()
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                await self.send_error_message(
                    interaction,
                    "Звание не найдено",
                    f"Звание '{self.rank_name}' не найдено в конфигурации."
                )
                
        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка удаления",
                f"Произошла ошибка при удалении звания: {e}"
            )


class RankRolesSelect(ui.Select):
    """Select menu for managing rank roles"""
    
    def __init__(self):
        config = load_config()
        rank_roles = config.get('rank_roles', {})
        
        options = [
            discord.SelectOption(
                label="➕ Добавить звание",
                description="Добавить новое звание",
                emoji="➕",
                value="add_rank"
            ),
            discord.SelectOption(
                label="🔑 Настроить ключевую роль",
                description="Роль для проверки активности игроков",
                emoji="🔑",
                value="set_key_role"
            )
        ]
        
        # Add existing ranks for editing/deletion
        for rank_name in sorted(rank_roles.keys()):
            if len(options) < 25:  # Discord limit
                options.append(
                    discord.SelectOption(
                        label=f"✏️ {rank_name}",
                        description=f"Редактировать звание {rank_name}",
                        emoji="✏️",
                        value=f"edit_{rank_name}"
                    )
                )
        
        super().__init__(
            placeholder="Выберите действие...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="rank_roles_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        
        if selected_value == "add_rank":
            modal = RankRoleModal()
            await interaction.response.send_modal(modal)
        elif selected_value == "set_key_role":
            modal = KeyRoleModal()
            await interaction.response.send_modal(modal)
        elif selected_value.startswith("edit_"):
            rank_name = selected_value[5:]  # Remove "edit_" prefix
            modal = RankRoleModal(edit_rank=rank_name)
            await interaction.response.send_modal(modal)


class RankRoleDeleteSelect(ui.Select):
    """Select menu for deleting rank roles"""
    
    def __init__(self):
        config = load_config()
        rank_roles = config.get('rank_roles', {})
        
        options = []
        
        # Add existing ranks for deletion
        for rank_name in sorted(rank_roles.keys()):
            if len(options) < 25:  # Discord limit
                options.append(
                    discord.SelectOption(
                        label=f"🗑️ {rank_name}",
                        description=f"Удалить звание {rank_name}",
                        emoji="🗑️",
                        value=rank_name
                    )
                )
        
        if not options:
            options.append(
                discord.SelectOption(
                    label="Нет званий для удаления",
                    description="Сначала добавьте звания",
                    emoji="❌",
                    value="none"
                )
            )
        
        super().__init__(
            placeholder="Выберите звание для удаления...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="rank_roles_delete_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_rank = self.values[0]
        
        if selected_rank == "none":
            embed = discord.Embed(
                title="❌ Нет званий",
                description="Нет настроенных званий для удаления.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        modal = RankRoleDeleteConfirmModal(selected_rank)
        await interaction.response.send_modal(modal)


class RankRolesConfigView(BaseSettingsView):
    """Main view for rank roles configuration"""
    
    def __init__(self):
        super().__init__()
        self.add_item(RankRolesSelect())
        self.add_item(RankRoleDeleteSelect())


async def show_rank_roles_config(interaction: discord.Interaction):
    """Show rank roles configuration interface"""
    config = load_config()
    rank_roles = config.get('rank_roles', {})
    key_role_id = config.get('rank_sync_key_role')
    
    embed = discord.Embed(
        title="🎖️ Настройка ролей званий",
        description="Управление связыванием званий с ролями на сервере.",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    # Show key role
    if key_role_id:
        key_role = interaction.guild.get_role(key_role_id)
        if key_role:
            embed.add_field(
                name="🔑 Ключевая роль:",
                value=f"{key_role.mention} - только участники с этой ролью проверяются системой",
                inline=False
            )
        else:
            embed.add_field(
                name="🔑 Ключевая роль:",
                value=f"❌ Роль не найдена (ID: {key_role_id})",
                inline=False
            )
    else:
        embed.add_field(
            name="⚠️ Ключевая роль не настроена",
            value="Система будет проверять всех участников сервера (не рекомендуется для больших серверов)",
            inline=False
        )
    
    if rank_roles:
        ranks_list = []
        for rank_name, role_id in sorted(rank_roles.items()):
            role = interaction.guild.get_role(int(role_id))
            if role:
                ranks_list.append(f"• **{rank_name}** → {role.mention}")
            else:
                ranks_list.append(f"• **{rank_name}** → `{role_id}` ❌ (роль не найдена)")
        
        embed.add_field(
            name="📋 Текущие звания:",
            value="\n".join(ranks_list) if ranks_list else "Нет настроенных званий",
            inline=False
        )
    else:
        embed.add_field(
            name="❌ Звания не настроены",
            value="Добавьте первое звание, используя кнопку ниже.",
            inline=False
        )
    
    embed.add_field(
        name="🔧 Доступные действия:",
        value=(
            "• **Настроить ключевую роль** - роль для проверки активности\n"
            "• **Добавить звание** - связать новое звание с ролью\n"
            "• **Редактировать звание** - изменить существующее звание\n"
            "• **Удалить звание** - удалить звание из конфигурации"
        ),
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Информация:",
        value=(
            "Звания используются для автоматического назначения ролей "
            "при различных операциях в системе кадрового учёта.\n\n"
            "**Ключевая роль** ограничивает проверку только участниками с определённой ролью, "
            "что повышает производительность на больших серверах."
        ),
        inline=False
    )
    
    view = RankRolesConfigView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


def initialize_default_ranks():
    """Initialize default rank roles in config if not present"""
    config = load_config()
    changes_made = False
    
    if 'rank_roles' not in config or not config['rank_roles']:
        default_ranks = {
            "Рядовой": 1246114675574313021,
            "Ефрейтор": 1246114674638983270,
            "Мл. Сержант": 1261982952275972187,
            "Сержант": 1246114673997123595,
            "Ст. Сержант": 1246114672352952403,
            "Старшина": 1246114604958879754,
            "Прапорщик": 1246114604329865327,
            "Ст. Прапорщик": 1251045305793773648,
            "Мл. Лейтенант": 1251045263062335590,
            "Лейтенант": 1246115365746901094,
            "Ст. Лейтенант": 1246114469340250214,
            "Капитан": 1246114469336322169
        }
        
        config['rank_roles'] = default_ranks
        changes_made = True
        print("✅ Initialized default rank roles in config")
    
    # Initialize default key role if not present (military role from config)
    if 'rank_sync_key_role' not in config and config.get('military_role'):
        config['rank_sync_key_role'] = config['military_role']
        changes_made = True
        print("✅ Initialized default key role for rank sync from military role")
    
    if changes_made:
        save_config(config)
        return True
    
    return False
