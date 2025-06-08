import discord
import re
from discord import ui
from utils.config_manager import load_config, save_config
from forms.dismissal_form import send_dismissal_button_message

class MainSettingsSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Настройка каналов",
                description="Настроить каналы для различных систем бота",
                emoji="📂",
                value="channels"
            ),            discord.SelectOption(
                label="Роли-исключения",
                description="Настроить роли, которые не снимаются при увольнении",
                emoji="🛡️",
                value="excluded_roles"
            ),
            discord.SelectOption(
                label="Пинги",
                description="Настроить пинги для подразделений при рапортах",
                emoji="📢",
                value="pings"
            ),
            discord.SelectOption(
                label="Показать текущие настройки",
                description="Посмотреть все текущие настройки",
                emoji="⚙️",
                value="show_config"
            )
        ]
        
        super().__init__(
            placeholder="Выберите категорию настроек...",
            min_values=1,
            max_values=1,
            options=options,        custom_id="main_settings_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_option = self.values[0]
        
        if selected_option == "channels":
            await self.show_channels_menu(interaction)
        elif selected_option == "show_config":
            await self.show_current_config(interaction)
        elif selected_option == "excluded_roles":
            await self.show_excluded_roles_config(interaction)
        elif selected_option == "pings":
            await self.show_pings_config(interaction)
    
    async def show_channels_menu(self, interaction: discord.Interaction):
        """Show submenu for channel configuration"""
        embed = discord.Embed(
            title="📂 Настройка каналов",
            description="Выберите канал для настройки из списка ниже.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Доступные каналы:",
            value=(
                "• **Канал увольнений** - для рапортов на увольнение\n"
                "• **Канал аудита** - для кадрового аудита\n"
                "• **Канал чёрного списка** - для записей чёрного списка"
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Инструкция:",
            value="1. Выберите тип канала из списка\n2. Укажите канал (ID, упоминание или название)\n3. Бот автоматически настроит канал и добавит кнопки",
            inline=False
        )
        view = ChannelsConfigView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def show_current_config(self, interaction: discord.Interaction):
        config = load_config()
        
        embed = discord.Embed(
            title="⚙️ Текущие настройки",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Dismissal channel
        dismissal_id = config.get('dismissal_channel')
        if dismissal_id:
            channel = interaction.guild.get_channel(dismissal_id)
            dismissal_text = channel.mention if channel else f"❌ Канал не найден (ID: {dismissal_id})"
        else:
            dismissal_text = "❌ Не настроен"
        
        # Audit channel
        audit_id = config.get('audit_channel')
        if audit_id:
            channel = interaction.guild.get_channel(audit_id)
            audit_text = channel.mention if channel else f"❌ Канал не найден (ID: {audit_id})"
        else:
            audit_text = "❌ Не настроен"
          # Blacklist channel
        blacklist_id = config.get('blacklist_channel')
        if blacklist_id:
            channel = interaction.guild.get_channel(blacklist_id)
            blacklist_text = channel.mention if channel else f"❌ Канал не найден (ID: {blacklist_id})"
        else:
            blacklist_text = "❌ Не настроен"
        
        embed.add_field(name="📝 Канал увольнений", value=dismissal_text, inline=False)
        embed.add_field(name="🔍 Канал аудита", value=audit_text, inline=False)
        embed.add_field(name="🚫 Канал чёрного списка", value=blacklist_text, inline=False)
        
        # Excluded roles
        excluded_roles_ids = config.get('excluded_roles', [])
        if excluded_roles_ids:
            excluded_roles = []
            for role_id in excluded_roles_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    excluded_roles.append(role.mention)
                else:
                    excluded_roles.append(f"❌ Роль не найдена (ID: {role_id})")
            excluded_text = "\n".join(excluded_roles) if excluded_roles else "❌ Роли не найдены"
        else:
            excluded_text = "❌ Не настроены"
        
        embed.add_field(name="🛡️ Роли-исключения", value=excluded_text, inline=False)
        
        # Ping settings
        ping_settings = config.get('ping_settings', {})
        if ping_settings:
            ping_text = ""
            for department_role_id, ping_roles_ids in ping_settings.items():
                department_role = interaction.guild.get_role(int(department_role_id))
                if department_role:
                    ping_roles = []
                    for ping_role_id in ping_roles_ids:
                        ping_role = interaction.guild.get_role(ping_role_id)
                        if ping_role:
                            ping_roles.append(ping_role.mention)
                    if ping_roles:
                        ping_text += f"• {department_role.mention} → {', '.join(ping_roles)}\n"
            ping_text = ping_text or "❌ Настройки не найдены"
        else:
            ping_text = "❌ Не настроены"
        
        embed.add_field(name="📢 Настройки пингов", value=ping_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def show_excluded_roles_config(self, interaction: discord.Interaction):
        """Show interface for managing excluded roles"""
        config = load_config()
        excluded_roles_ids = config.get('excluded_roles', [])
        
        embed = discord.Embed(
            title="🛡️ Управление ролями-исключениями",
            description="Роли, которые не будут сниматься при одобрении рапорта на увольнение.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Show current excluded roles
        if excluded_roles_ids:
            excluded_roles = []
            for role_id in excluded_roles_ids:
                role = interaction.guild.get_role(role_id)
                if role:
                    excluded_roles.append(f"• {role.mention}")
                else:
                    excluded_roles.append(f"• ❌ Роль не найдена (ID: {role_id})")
            
            excluded_text = "\n".join(excluded_roles)
        else:
            excluded_text = "❌ Роли-исключения не настроены"
        
        embed.add_field(name="Текущие роли-исключения:", value=excluded_text, inline=False)
        
        embed.add_field(
            name="ℹ️ Действия:",
            value=(
                "• **Добавить роли** - добавить новые роли в список исключений\n"
                "• **Удалить роли** - убрать роли из списка исключений\n"
                "• **Очистить список** - удалить все роли-исключения"
            ),
            inline=False
        )
        
        view = ExcludedRolesView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_pings_config(self, interaction: discord.Interaction):
        """Show interface for managing ping settings for departments"""
        config = load_config()
        ping_settings = config.get('ping_settings', {})
        
        embed = discord.Embed(
            title="📢 Управление пингами подразделений",
            description="Настройка ролей для уведомлений при подаче рапортов на увольнение в зависимости от подразделения подающего.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Show current ping settings
        if ping_settings:
            ping_text = ""
            for department_role_id, ping_roles_ids in ping_settings.items():
                department_role = interaction.guild.get_role(int(department_role_id))
                if department_role:
                    ping_roles = []
                    for ping_role_id in ping_roles_ids:
                        ping_role = interaction.guild.get_role(ping_role_id)
                        if ping_role:
                            ping_roles.append(ping_role.mention)
                    if ping_roles:
                        ping_text += f"• {department_role.mention} → {', '.join(ping_roles)}\n"
            
            ping_text = ping_text or "❌ Настройки пингов не найдены"
        else:
            ping_text = "❌ Настройки пингов не настроены"
        
        embed.add_field(name="Текущие настройки пингов:", value=ping_text, inline=False)
        
        embed.add_field(
            name="ℹ️ Принцип работы:",
            value=(
                "При подаче рапорта на увольнение бот определит роль подразделения у подающего "
                "и отправит уведомления указанным для этого подразделения ролям."
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎯 Действия:",
            value=(
                "• **Добавить настройку** - связать подразделение с ролями для пинга\n"
                "• **Удалить настройку** - убрать настройку для подразделения\n"
                "• **Очистить все** - удалить все настройки пингов"
            ),
            inline=False
        )
        
        view = PingSettingsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ChannelsConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.add_item(ChannelConfigSelect())

class ChannelConfigSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Канал увольнений",
                description="Настроить канал для рапортов на увольнение",
                emoji="📝",
                value="dismissal"
            ),
            discord.SelectOption(
                label="Канал аудита",
                description="Настроить канал для кадрового аудита",
                emoji="🔍",
                value="audit"
            ),            discord.SelectOption(
                label="Канал чёрного списка",
                description="Настроить канал для чёрного списка",
                emoji="🚫",
                value="blacklist"
            )
        ]
        
        super().__init__(
            placeholder="Выберите канал для настройки...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="channel_config_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        selected_option = self.values[0]
        await self.show_channel_selection(interaction, selected_option)
    
    async def show_channel_selection(self, interaction: discord.Interaction, config_type: str):
        # Create channel selection modal
        modal = ChannelSelectionModal(config_type)
        await interaction.response.send_modal(modal)

class ChannelSelectionModal(ui.Modal):
    def __init__(self, config_type: str):
        self.config_type = config_type
        
        type_names = {
            "dismissal": "увольнений",
            "audit": "аудита", 
            "blacklist": "чёрного списка"
        }
        
        super().__init__(title=f"Настройка канала {type_names.get(config_type, config_type)}")
        
        self.channel_input = ui.TextInput(
            label="ID или упоминание канала",
            placeholder="Например: #канал-увольнений или 1234567890123456789",
            min_length=1,
            max_length=100,
            required=True        )
        self.add_item(self.channel_input)
    
    def _normalize_channel_name(self, channel_name, is_text_channel=True):
        """
        Normalize channel name by removing cosmetic elements and # prefix.
        For text channels, spaces are converted to hyphens.
        For voice channels, spaces remain as spaces.
        
        Examples:
        - "#├「🚨」название канала" -> "название-канала" (text channel)
        - "#├「🚨」название канала" -> "название канала" (voice channel)
        - "#название-канала" -> "название-канала"
        - "├「🚨」название" -> "название"
        """
        import re
        
        # Remove # prefix if present
        if channel_name.startswith('#'):
            channel_name = channel_name[1:]
        
        # Remove common cosmetic patterns at the beginning
        # Pattern matches: ├「emoji」, ├, 「emoji」, └, ┬, ┴, etc.
        cosmetic_patterns = [
            r'^[├└┬┴│┌┐┘┤┼─┴┬]+[「『【\[].*?[」』】\]][^a-zA-Zа-яё0-9\-_\s]*',  # ├「🚨」
            r'^[├└┬┴│┌┐┘┤┼─┴┬]+[^a-zA-Zа-яё0-9\-_\s]*',  # ├
            r'^[「『【\[].*?[」』】\]][^a-zA-Zа-яё0-9\-_\s]*',  # 「🚨」
            r'^[^\w\-а-яё\s]*',  # any other non-word characters at start
        ]
        
        for pattern in cosmetic_patterns:
            channel_name = re.sub(pattern, '', channel_name, flags=re.UNICODE)
        
        # Remove trailing non-word characters (but keep spaces for now)
        channel_name = re.sub(r'[^\w\-а-яё\s]*$', '', channel_name, flags=re.UNICODE)
        
        # Convert spaces to hyphens for text channels
        if is_text_channel:
            channel_name = channel_name.replace(' ', '-')
        
        return channel_name.strip()
    
    def _find_channel_by_name(self, guild, search_name):
        """
        Smart channel search that ignores cosmetic elements.
        Searches both text and voice channels, with proper space/hyphen handling.
        """
        # First, try to find text channels (spaces converted to hyphens)
        normalized_search_text = self._normalize_channel_name(search_name, is_text_channel=True).lower()
        
        # If the normalized search is not empty, search text channels
        if normalized_search_text:
            # First, try exact match with normalized names in text channels
            for channel in guild.text_channels:
                normalized_channel_name = self._normalize_channel_name(channel.name, is_text_channel=True).lower()
                if normalized_channel_name == normalized_search_text:
                    return channel
            
            # If no exact match, try partial match in text channels
            for channel in guild.text_channels:
                normalized_channel_name = self._normalize_channel_name(channel.name, is_text_channel=True).lower()
                if normalized_search_text in normalized_channel_name or normalized_channel_name in normalized_search_text:
                    return channel
        
        # Then, try to find voice channels (spaces preserved)
        normalized_search_voice = self._normalize_channel_name(search_name, is_text_channel=False).lower()
        
        if normalized_search_voice:
            # First, try exact match with normalized names in voice channels
            for channel in guild.voice_channels:
                normalized_channel_name = self._normalize_channel_name(channel.name, is_text_channel=False).lower()
                if normalized_channel_name == normalized_search_voice:
                    return channel
            
            # If no exact match, try partial match in voice channels
            for channel in guild.voice_channels:
                normalized_channel_name = self._normalize_channel_name(channel.name, is_text_channel=False).lower()
                if normalized_search_voice in normalized_channel_name or normalized_channel_name in normalized_search_voice:
                    return channel
        
        # If still no match, try original Discord search as fallback (text channels only for compatibility)
        return discord.utils.get(guild.text_channels, name=search_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_text = self.channel_input.value.strip()
            
            # Try to parse channel mention or ID
            channel = None
            
            # Check if it's a mention
            if channel_text.startswith('<#') and channel_text.endswith('>'):
                channel_id = int(channel_text[2:-1])
                channel = interaction.guild.get_channel(channel_id)
            else:
                # Try to parse as ID
                try:
                    channel_id = int(channel_text)
                    channel = interaction.guild.get_channel(channel_id)
                except ValueError:
                    # Try to find by name using smart search
                    channel = self._find_channel_by_name(interaction.guild, channel_text)
            
            if not channel:
                await interaction.response.send_message(
                    "❌ Канал не найден. Убедитесь, что вы правильно указали ID, упоминание или название канала.",
                    ephemeral=True
                )
                return
            
            if not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message(
                    "❌ Указанный канал не является текстовым каналом.",
                    ephemeral=True
                )
                return
              # Save configuration
            config = load_config()
            config[f'{self.config_type}_channel'] = channel.id
            save_config(config)
            
            # Define type names and handle button messages
            type_names = {
                "dismissal": "рапортов на увольнение",
                "audit": "кадрового аудита",
                "blacklist": "чёрного списка"
            }
            type_name = type_names.get(self.config_type, self.config_type)
            
            # Send appropriate button message to the channel
            button_message_added = False
            if self.config_type == "dismissal":
                await send_dismissal_button_message(channel)
                button_message_added = True
            
            embed = discord.Embed(
                title="✅ Канал настроен успешно",
                description=f"Канал для {type_name} установлен: {channel.mention}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            # Customize the description based on whether button was added
            if button_message_added:
                embed.add_field(
                    name="Что было сделано:",
                    value=f"• Канал {channel.mention} настроен для {type_name}\n• Сообщение с кнопкой добавлено в канал",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Что было сделано:",
                    value=f"• Канал {channel.mention} настроен для {type_name}",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in channel configuration: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка при настройке канала: {e}",
                ephemeral=True
            )

class SettingsView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(MainSettingsSelect())
    
    async def on_timeout(self):
        # This won't be called for persistent views, but good to have
        for item in self.children:
            item.disabled = True

class ExcludedRolesView(ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutes timeout
    
    @discord.ui.button(label="➕ Добавить роли", style=discord.ButtonStyle.green)
    async def add_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddExcludedRolesModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Удалить роли", style=discord.ButtonStyle.red)
    async def remove_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        excluded_roles_ids = config.get('excluded_roles', [])
        
        if not excluded_roles_ids:
            await interaction.response.send_message(
                "❌ Нет настроенных ролей-исключений для удаления.",
                ephemeral=True
            )
            return
        
        modal = RemoveExcludedRolesModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Очистить все", style=discord.ButtonStyle.danger)
    async def clear_all_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        config['excluded_roles'] = []
        save_config(config)
        
        embed = discord.Embed(
            title="✅ Список очищен",
            description="Все роли-исключения были удалены. Теперь при увольнении будут сниматься все роли кроме @everyone.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AddExcludedRolesModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Добавить роли-исключения")
        
        self.roles_input = ui.TextInput(
            label="Роли (через запятую)",
            placeholder="@Роль1, @Роль2, 123456789012345678 или названия ролей",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=1000,
            required=True
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            roles_text = self.roles_input.value.strip()
            role_inputs = [r.strip() for r in roles_text.split(',')]
            
            config = load_config()
            excluded_roles = config.get('excluded_roles', [])
            
            added_roles = []
            failed_roles = []
            
            for role_input in role_inputs:
                if not role_input:
                    continue
                    
                role = None
                
                # Try to parse role mention
                if role_input.startswith('<@&') and role_input.endswith('>'):
                    try:
                        role_id = int(role_input[3:-1])
                        role = interaction.guild.get_role(role_id)
                    except ValueError:
                        pass
                else:
                    # Try to parse as ID
                    try:
                        role_id = int(role_input)
                        role = interaction.guild.get_role(role_id)
                    except ValueError:
                        # Try to find by name
                        role = discord.utils.get(interaction.guild.roles, name=role_input)
                
                if role:
                    if role.id not in excluded_roles:
                        excluded_roles.append(role.id)
                        added_roles.append(role.mention)
                    else:
                        failed_roles.append(f"{role_input} (уже в списке)")
                else:
                    failed_roles.append(f"{role_input} (не найдена)")
            
            # Save updated config
            config['excluded_roles'] = excluded_roles
            save_config(config)
            
            # Create response embed
            embed = discord.Embed(
                title="✅ Роли-исключения обновлены",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            if added_roles:
                embed.add_field(
                    name="➕ Добавленные роли:",
                    value="\n".join([f"• {role}" for role in added_roles]),
                    inline=False
                )
            
            if failed_roles:
                embed.add_field(
                    name="❌ Не удалось добавить:",
                    value="\n".join([f"• {role}" for role in failed_roles]),
                    inline=False
                )
            
            if not added_roles and not failed_roles:
                embed.description = "❌ Не удалось обработать ни одной роли."
                embed.color = discord.Color.red()
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in add excluded roles: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка при добавлении ролей: {e}",
                ephemeral=True
            )

class RemoveExcludedRolesModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Удалить роли-исключения")
        
        self.roles_input = ui.TextInput(
            label="Роли для удаления (через запятую)",
            placeholder="@Роль1, @Роль2, 123456789012345678 или названия ролей",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=1000,
            required=True
        )
        self.add_item(self.roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            roles_text = self.roles_input.value.strip()
            role_inputs = [r.strip() for r in roles_text.split(',')]
            
            config = load_config()
            excluded_roles = config.get('excluded_roles', [])
            
            removed_roles = []
            failed_roles = []
            
            for role_input in role_inputs:
                if not role_input:
                    continue
                    
                role = None
                
                # Try to parse role mention
                if role_input.startswith('<@&') and role_input.endswith('>'):
                    try:
                        role_id = int(role_input[3:-1])
                        role = interaction.guild.get_role(role_id)
                    except ValueError:
                        pass
                else:
                    # Try to parse as ID
                    try:
                        role_id = int(role_input)
                        role = interaction.guild.get_role(role_id)
                    except ValueError:
                        # Try to find by name
                        role = discord.utils.get(interaction.guild.roles, name=role_input)
                
                if role and role.id in excluded_roles:
                    excluded_roles.remove(role.id)
                    removed_roles.append(role.mention)
                else:
                    if role:
                        failed_roles.append(f"{role_input} (не в списке исключений)")
                    else:
                        failed_roles.append(f"{role_input} (роль не найдена)")
            
            # Save updated config
            config['excluded_roles'] = excluded_roles
            save_config(config)
            
            # Create response embed
            embed = discord.Embed(
                title="✅ Роли-исключения обновлены",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            if removed_roles:
                embed.add_field(
                    name="➖ Удалённые роли:",
                    value="\n".join([f"• {role}" for role in removed_roles]),
                    inline=False
                )
            
            if failed_roles:                embed.add_field(
                    name="❌ Не удалось удалить:",
                    value="\n".join([f"• {role}" for role in failed_roles]),
                    inline=False
                )
            
            if not removed_roles and not failed_roles:
                embed.description = "❌ Не удалось обработать ни одной роли."
                embed.color = discord.Color.red()
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in remove excluded roles: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка при удалении ролей: {e}",
                ephemeral=True
            )

class PingSettingsView(ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutes timeout
    
    @discord.ui.button(label="➕ Добавить настройку", style=discord.ButtonStyle.green)
    async def add_ping_setting(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddPingSettingModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Удалить настройку", style=discord.ButtonStyle.red)
    async def remove_ping_setting(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        ping_settings = config.get('ping_settings', {})
        
        if not ping_settings:
            await interaction.response.send_message(
                "❌ Нет настроенных пингов для удаления.",
                ephemeral=True
            )
            return
        
        modal = RemovePingSettingModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Очистить все", style=discord.ButtonStyle.danger)
    async def clear_all_pings(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = load_config()
        config['ping_settings'] = {}
        save_config(config)
        
        embed = discord.Embed(
            title="✅ Настройки пингов очищены",
            description="Все настройки пингов были удалены. Теперь при подаче рапортов уведомления отправляться не будут.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AddPingSettingModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Добавить настройку пингов")
        
        self.department_input = ui.TextInput(
            label="Роль подразделения",
            placeholder="@Управление Военной Полиции или ID роли",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.department_input)
        
        self.ping_roles_input = ui.TextInput(
            label="Роли для пинга (через запятую)",
            placeholder="@Командир УВП, @Зам. Командира УВП или ID ролей",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=1000,
            required=True
        )
        self.add_item(self.ping_roles_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse department role
            department_text = self.department_input.value.strip()
            department_role = None
            
            if department_text.startswith('<@&') and department_text.endswith('>'):
                try:
                    role_id = int(department_text[3:-1])
                    department_role = interaction.guild.get_role(role_id)
                except ValueError:
                    pass
            else:
                try:
                    role_id = int(department_text)
                    department_role = interaction.guild.get_role(role_id)
                except ValueError:
                    department_role = discord.utils.get(interaction.guild.roles, name=department_text)
            
            if not department_role:
                await interaction.response.send_message(
                    "❌ Роль подразделения не найдена. Убедитесь, что вы правильно указали роль.",
                    ephemeral=True
                )
                return
            
            # Parse ping roles
            ping_roles_text = self.ping_roles_input.value.strip()
            ping_role_inputs = [r.strip() for r in ping_roles_text.split(',')]
            
            ping_roles = []
            failed_roles = []
            
            for role_input in ping_role_inputs:
                if not role_input:
                    continue
                    
                role = None
                
                if role_input.startswith('<@&') and role_input.endswith('>'):
                    try:
                        role_id = int(role_input[3:-1])
                        role = interaction.guild.get_role(role_id)
                    except ValueError:
                        pass
                else:
                    try:
                        role_id = int(role_input)
                        role = interaction.guild.get_role(role_id)
                    except ValueError:
                        role = discord.utils.get(interaction.guild.roles, name=role_input)
                
                if role:
                    ping_roles.append(role)
                else:
                    failed_roles.append(role_input)
            
            if not ping_roles:
                await interaction.response.send_message(
                    "❌ Не удалось найти ни одной роли для пинга.",
                    ephemeral=True
                )
                return
            
            # Save configuration
            config = load_config()
            ping_settings = config.get('ping_settings', {})
            ping_settings[str(department_role.id)] = [role.id for role in ping_roles]
            config['ping_settings'] = ping_settings
            save_config(config)
            
            # Create response embed
            embed = discord.Embed(
                title="✅ Настройка пингов добавлена",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="Подразделение:",
                value=department_role.mention,
                inline=False
            )
            
            embed.add_field(
                name="Роли для пинга:",
                value=", ".join([role.mention for role in ping_roles]),
                inline=False
            )
            
            if failed_roles:
                embed.add_field(
                    name="❌ Не удалось добавить:",
                    value="\n".join([f"• {role}" for role in failed_roles]),
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in add ping setting: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка при добавлении настройки: {e}",
                ephemeral=True
            )

class RemovePingSettingModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Удалить настройку пингов")
        
        self.department_input = ui.TextInput(
            label="Роль подразделения для удаления",
            placeholder="@Управление Военной Полиции или ID роли",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.department_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse department role
            department_text = self.department_input.value.strip()
            department_role = None
            
            if department_text.startswith('<@&') and department_text.endswith('>'):
                try:
                    role_id = int(department_text[3:-1])
                    department_role = interaction.guild.get_role(role_id)
                except ValueError:
                    pass
            else:
                try:
                    role_id = int(department_text)
                    department_role = interaction.guild.get_role(role_id)
                except ValueError:
                    department_role = discord.utils.get(interaction.guild.roles, name=department_text)
            
            if not department_role:
                await interaction.response.send_message(
                    "❌ Роль подразделения не найдена. Убедитесь, что вы правильно указали роль.",
                    ephemeral=True
                )
                return
            
            # Remove from configuration
            config = load_config()
            ping_settings = config.get('ping_settings', {})
            
            if str(department_role.id) in ping_settings:
                del ping_settings[str(department_role.id)]
                config['ping_settings'] = ping_settings
                save_config(config)
                
                embed = discord.Embed(
                    title="✅ Настройка пингов удалена",
                    description=f"Настройка пингов для подразделения {department_role.mention} была удалена.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"❌ Настройка пингов для {department_role.mention} не найдена.",
                    ephemeral=True
                )
            
        except Exception as e:
            print(f"Error in remove ping setting: {e}")
            await interaction.response.send_message(
                f"❌ Произошла ошибка при удалении настройки: {e}",
                ephemeral=True
            )

# Function to send settings message
async def send_settings_message(interaction: discord.Interaction):
    embed = discord.Embed(        title="⚙️ Настройки Discord бота",
        description="Используйте выпадающий список ниже для управления настройками бота.",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(
        name="📝 Доступные категории:",
        value=(
            "• **📂 Настройка каналов** - настроить каналы для различных систем\n"
            "• **🛡️ Роли-исключения** - роли, не снимаемые при увольнении\n"
            "• **📢 Пинги** - настройка уведомлений для подразделений\n"
            "• **⚙️ Показать настройки** - просмотр текущих настроек"
        ),
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Как использовать:",
        value="1. Выберите категорию из главного меню\n2. Используйте подменю для настройки конкретных параметров\n3. Бот автоматически сохранит изменения",
        inline=False
    )
    
    embed.set_footer(text="Доступно только администраторам")
    
    view = SettingsView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Function to get user's department role for ping notifications
def get_user_department_role(user, ping_settings):
    """Get the user's department role that has ping settings configured"""
    for department_role_id in ping_settings.keys():
        department_role = user.guild.get_role(int(department_role_id))
        if department_role and department_role in user.roles:
            return department_role
    return None

# Function to get ping roles for department
def get_ping_roles_for_department(department_role, ping_settings, guild):
    """Get ping roles for a specific department"""
    if not department_role:
        return []
    
    ping_role_ids = ping_settings.get(str(department_role.id), [])
    ping_roles = []
    
    for role_id in ping_role_ids:
        role = guild.get_role(role_id)
        if role:
            ping_roles.append(role)
    
    return ping_roles
