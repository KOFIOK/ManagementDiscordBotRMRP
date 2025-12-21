"""
Base classes and utilities for settings forms
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class BaseSettingsView(ui.View):
    """Base class for all settings views with common functionality"""
    
    def __init__(self, timeout=300):
        super().__init__(timeout=timeout)
        # Уникальный тег контекста для семантического определения: используется при решении edit vs new
        # По умолчанию имя класса. Может переопределяться в наследниках.
        self.context_tag = self.__class__.__name__
    
    async def send_success_message(self, interaction: discord.Interaction, title: str, description: str):
        """Send a standardized success message"""
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def send_error_message(self, interaction: discord.Interaction, title: str, description: str):
        """Send a standardized error message"""
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BaseSettingsModal(ui.Modal):
    """Base class for all settings modals with common functionality"""
    
    async def send_success_message(self, interaction: discord.Interaction, title: str, description: str):
        """Send a standardized success message"""
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def send_error_message(self, interaction: discord.Interaction, title: str, description: str):
        """Send a standardized error message"""
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def parse_role(self, guild: discord.Guild, role_text: str) -> discord.Role:
        """Parse role from text input using RoleParser"""
        return RoleParser.parse_role_input(role_text, guild)
    
    async def parse_channel(self, guild: discord.Guild, channel_text: str) -> discord.TextChannel:
        """Parse channel from text input using ChannelParser"""
        return ChannelParser.parse_channel_input(channel_text, guild)
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfigDisplayHelper:
    """Helper class for displaying configuration information"""
    
    @staticmethod
    def format_channel_info(config: dict, channel_key: str, guild: discord.Guild) -> str:
        """Format channel information for display"""
        channel_id = config.get(channel_key)
        if channel_id:
            channel = guild.get_channel(channel_id)
            return channel.mention if channel else f"❌ Канал не найден (ID: {channel_id})"
        return " Не настроен"
    
    @staticmethod
    def format_role_info(config: dict, role_key: str, guild: discord.Guild) -> str:
        """Format role information for display"""
        role_id = config.get(role_key)
        if role_id:
            role = guild.get_role(role_id)
            return role.mention if role else f"❌ Роль не найдена (ID: {role_id})"
        return " Не настроена"
    
    @staticmethod
    def format_roles_list(config: dict, roles_key: str, guild: discord.Guild) -> str:
        """Format list of roles for display"""
        role_ids = config.get(roles_key, [])
        if role_ids:
            roles = []
            for role_id in role_ids:
                role = guild.get_role(role_id)
                if role:
                    roles.append(role.mention)
                else:
                    roles.append(f"❌ Роль не найдена (ID: {role_id})")
            return "\n".join(roles) if roles else "❌ Роли не найдены"
        return " Не настроены"
    
    @staticmethod
    def format_roles_info(config: dict, roles_key: str, guild: discord.Guild) -> str:
        """Format roles information for display (alias to format_roles_list)"""
        return ConfigDisplayHelper.format_roles_list(config, roles_key, guild)


class RoleParser:
    """Helper class for parsing role inputs"""
    
    @staticmethod
    def parse_role_input(role_text: str, guild: discord.Guild) -> discord.Role:
        """Parse role from mention, ID, or name"""
        role_text = role_text.strip()
        
        # Try to parse role mention
        if role_text.startswith('<@&') and role_text.endswith('>'):
            role_id = int(role_text[3:-1])
            return guild.get_role(role_id)
        
        # Try to parse role ID
        if role_text.isdigit():
            return guild.get_role(int(role_text))
        
        # Try to find role by name
        return discord.utils.get(guild.roles, name=role_text)
    
    @staticmethod
    def parse_multiple_roles(roles_text: str, guild: discord.Guild) -> list[discord.Role]:
        """Parse multiple roles from comma-separated input"""
        roles = []
        for role_part in roles_text.split(','):
            role = RoleParser.parse_role_input(role_part.strip(), guild)
            if role:
                roles.append(role)
        return roles


class ChannelParser:
    """Helper class for parsing channel inputs"""
    
    @staticmethod
    def parse_channel_input(channel_text: str, guild: discord.Guild) -> discord.TextChannel:
        """Parse channel from mention, ID, or name"""
        channel_text = channel_text.strip()
        
        # Try to parse channel mention
        if channel_text.startswith('<#') and channel_text.endswith('>'):
            channel_id = int(channel_text[2:-1])
            return guild.get_channel(channel_id)
        
        # Try to parse channel ID
        if channel_text.isdigit():
            return guild.get_channel(int(channel_text))
        
        # Remove # if present for name-based search
        if channel_text.startswith('#'):
            channel_text = channel_text[1:]
        
        # Try to find channel by exact name first
        channel = discord.utils.get(guild.text_channels, name=channel_text)
        if channel:
            return channel
        
        # Try to find channel by name (with smart normalization)
        return ChannelParser._find_channel_by_name(guild, channel_text)
    
    # ---------------------------------------------------------------------------
    # Базовый шаблон секции настроек: единая кнопка «Назад» и генератор эмбедов
    # ---------------------------------------------------------------------------

class SectionSettingsView(BaseSettingsView):
    """Базовый шаблон для секций настроек.

    Предоставляет:
      - Единообразную кнопку «⬅️ Назад» к главному меню настроек
      - Помощник создания стандартного эмбеда для раздела
    """

    def __init__(self, *, title: str | None = None, description: str | None = None, back_enabled: bool = True, timeout: int | None = 300):
        super().__init__(timeout=timeout)
        self.section_title = title
        self.section_description = description

        if back_enabled:
            self.add_item(self._BackButton())

    def create_section_embed(self, *, title: str | None = None, description: str | None = None, color: discord.Color = discord.Color.blue()) -> discord.Embed:
        """Создать стандартный эмбед для секции.

        Если параметры не переданы, используются значения из self.section_title/section_description.
        """
        final_title = title or self.section_title or "Настройки"
        final_description = description or self.section_description or ""

        embed = discord.Embed(
            title=final_title,
            description=final_description,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        return embed

    class _BackButton(ui.Button):
        def __init__(self):
            super().__init__(label="⬅️ Назад", style=discord.ButtonStyle.secondary, row=4)

        async def callback(self, interaction: discord.Interaction):
            try:
                # Ленивая загрузка главного меню, чтобы избежать циклических импортов
                from .main import send_settings_message
                await send_settings_message(interaction)
            except Exception as e:
                logger.warning("Ошибка возврата к главному меню настроек: %s", e)
                try:
                    # Фолбэк: минимальный эмбед + главное меню
                    from .main import SettingsView
                    fallback = discord.Embed(
                        title="⚙️ Панель настроек бота",
                        description="Возврат к главному меню.",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    await safe_send(interaction, embed=fallback, view=SettingsView(), ephemeral=True)
                except Exception:
                    pass
    @staticmethod
    def _normalize_channel_name(channel_name: str, is_text_channel=True) -> str:
        """Normalize channel name by removing cosmetic elements"""
        # Remove # prefix if present
        if channel_name.startswith('#'):
            channel_name = channel_name[1:]
        
        # Remove common cosmetic patterns
        import re
        cosmetic_patterns = [
            r'^[├└┬┴│┌┐┘┤┼─┴┬]+[「『【\[].*?[」』】\]][^a-zA-Zа-яё0-9\-_\s]*',
            r'^[├└┬┴│┌┐┘┤┼─┴┬]+[^a-zA-Zа-яё0-9\-_\s]*',
            r'^[「『【\[].*?[」』】\]][^a-zA-Zа-яё0-9\-_\s]*',
            r'^[^\w\-а-яё\s]*',
        ]
        
        for pattern in cosmetic_patterns:
            channel_name = re.sub(pattern, '', channel_name, flags=re.UNICODE)
        
        # Remove trailing non-word characters
        channel_name = re.sub(r'[^\w\-а-яё\s]*$', '', channel_name, flags=re.UNICODE)
        
        # Convert spaces to hyphens for text channels
        if is_text_channel:
            channel_name = channel_name.replace(' ', '-')
        
        return channel_name.strip()
    
    @staticmethod
    def _find_channel_by_name(guild: discord.Guild, search_name: str) -> discord.TextChannel:
        """Smart channel search that ignores cosmetic elements"""
        normalized_search_text = ChannelParser._normalize_channel_name(search_name, is_text_channel=True).lower()
        
        if normalized_search_text:
            # Try exact match
            for channel in guild.text_channels:
                normalized_channel_name = ChannelParser._normalize_channel_name(channel.name, is_text_channel=True).lower()
                if normalized_channel_name == normalized_search_text:
                    return channel
            
            # Try partial match
            for channel in guild.text_channels:
                normalized_channel_name = ChannelParser._normalize_channel_name(channel.name, is_text_channel=True).lower()
                if normalized_search_text in normalized_channel_name or normalized_channel_name in normalized_search_text:
                    return channel
        
        # Fallback to Discord's built-in search
        return discord.utils.get(guild.text_channels, name=search_name)


# ---------------------------------------------------------------------------
# Interaction / message response helpers для унифицированной логики обновления
# ---------------------------------------------------------------------------

async def safe_send(interaction: discord.Interaction, *, embed: discord.Embed = None, view: ui.View = None, content: str = None, ephemeral: bool = True):
    """Безопасная отправка нового сообщения (если response уже использован — followup).

    Использование:
        await safe_send(interaction, embed=my_embed, view=my_view)
    """
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
        else:
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
    except Exception as e:
        logger.warning("safe_send error: %s", e)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ Ошибка отправки сообщения: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Ошибка отправки сообщения: {e}", ephemeral=True)
        except Exception:
            pass


async def safe_edit_or_send(interaction: discord.Interaction, *, embed: discord.Embed = None, view: ui.View = None, content: str = None, ephemeral: bool = True):
    """Попытка обновить текущее ephemeral сообщение, иначе отправить новое.

    Подходит для случаев «логическое обновление» (изменение данных той же секции).
    """
    try:
        if not interaction.response.is_done():
            await interaction.response.edit_message(content=content, embed=embed, view=view)
        else:
            # edit_message возможен только если есть ссылка на исходное; fallback на followup
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
    except Exception as e:
        logger.warning("safe_edit_or_send error: %s", e)
        try:
            await safe_send(interaction, content=f"❌ Ошибка обновления: {e}", ephemeral=True)
        except Exception:
            pass


async def semantic_update_or_new(interaction: discord.Interaction, *, embed: discord.Embed, view: BaseSettingsView, previous_context_tag: str | None, force_new: bool = False, ephemeral: bool = True):
    """Семантическое решение: обновить или отправить новое сообщение.

    Логика:
      - Если force_new=True -> всегда новое сообщение.
      - Если previous_context_tag совпадает с view.context_tag -> edit (safe_edit_or_send)
      - Иначе -> новое (safe_send)

    Использование:
        prev_tag = getattr(existing_view, 'context_tag', None)  # сохраняется вызывающим кодом
        await semantic_update_or_new(interaction, embed=embed, view=new_view, previous_context_tag=prev_tag)
    """
    try:
        if force_new:
            await safe_send(interaction, embed=embed, view=view, ephemeral=ephemeral)
            return view.context_tag
        if previous_context_tag and previous_context_tag == getattr(view, 'context_tag', None):
            await safe_edit_or_send(interaction, embed=embed, view=view, ephemeral=ephemeral)
        else:
            await safe_send(interaction, embed=embed, view=view, ephemeral=ephemeral)
        return view.context_tag
    except Exception as e:
        logger.warning("semantic_update_or_new error: %s", e)
        try:
            await safe_send(interaction, content=f"❌ Ошибка отображения: {e}", ephemeral=True)
        except Exception:
            pass
        return getattr(view, 'context_tag', None)