"""
Rank roles configuration management with PostgreSQL integration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config
from utils.database_manager import rank_manager
from .base import BaseSettingsView, BaseSettingsModal


# ---------------------------------------------------------------------------
# Вспомогательные функции отображения (эмбед-чанкование)
# ---------------------------------------------------------------------------

def _calc_embed_text_length(embed: discord.Embed) -> int:
    """Приблизительная длина текста эмбеда (title + description + поля)."""
    total = 0
    if embed.title:
        total += len(str(embed.title))
    if embed.description:
        total += len(str(embed.description))
    for field in embed.fields:
        total += len(str(field.name or "")) + len(str(field.value or ""))
    return total

def _add_chunked_list_field(embed: discord.Embed, base_name: str, lines: list[str]):
    """Разбить длинный список на чанки полей в пределах 1024 символов (без учета общего лимита)."""
    if not lines:
        embed.add_field(name=base_name, value="Нет настроенных званий", inline=False)
        return

    MAX_VALUE = 1024
    chunk = []
    chunk_len = 0
    field_index = 0

    def flush_chunk():
        nonlocal chunk, chunk_len, field_index
        if not chunk:
            return
        name = base_name if field_index == 0 else f"{base_name} (продолжение)"
        embed.add_field(name=name, value="\n".join(chunk), inline=False)
        field_index += 1
        chunk = []
        chunk_len = 0

    for line in lines:
        line_len = len(line) + 1
        if chunk_len + line_len > MAX_VALUE:
            flush_chunk()
        chunk.append(line)
        chunk_len += line_len

    flush_chunk()

def _add_chunked_list_field_capped(embed: discord.Embed, base_name: str, lines: list[str], max_total_chars: int = 5500):
    """Как _add_chunked_list_field, но с общим лимитом эмбеда ~6000 символов.

    Обрезает добавление, если суммарный текст превысит лимит, и добавляет подсказку
    о скрытых строках.
    """
    if not lines:
        embed.add_field(name=base_name, value="Нет настроенных званий", inline=False)
        return

    MAX_VALUE = 1024
    chunk = []
    chunk_len = 0
    field_index = 0
    total_len = _calc_embed_text_length(embed)
    hidden_count = 0

    def flush_chunk(force: bool = False):
        nonlocal chunk, chunk_len, field_index, total_len
        if not chunk:
            return True
        name = base_name if field_index == 0 else f"{base_name} (продолжение)"
        value = "\n".join(chunk)
        # Проверяем общий лимит
        if not force and (total_len + len(name) + len(value)) > max_total_chars:
            return False
        embed.add_field(name=name, value=value, inline=False)
        total_len += len(name) + len(value)
        field_index += 1
        chunk = []
        chunk_len = 0
        return True

    for line in lines:
        line_len = len(line) + 1
        if chunk_len + line_len > MAX_VALUE:
            if not flush_chunk():
                hidden_count += 1  # текущая строка и все следующие будут скрыты
                break
        chunk.append(line)
        chunk_len += line_len

    # Финальный флаш либо прекращение
    if chunk:
        if not flush_chunk():
            hidden_count += 1

    # Если что-то скрыто, добавим информационное поле
    if hidden_count > 0:
        remaining = max(0, len(lines) - sum(1 for f in embed.fields if f.name and f.name.startswith(base_name)))
        embed.add_field(
            name="ℹ️ Сокращение списка",
            value=f"Показаны не все записи. Всего: {len(lines)}. Список сокращен для соответствия ограничениям Discord.",
            inline=False
        )

def _add_sliced_list_fields(embed: discord.Embed, base_name: str, lines: list[str], *, lines_per_field: int = 20, max_total_chars: int = 5500):
    """Добавить список строк, разбитых на последовательные срезы по количеству строк.

    Это гарантирует, что поля не повторяют префиксы и выглядят как страницы списка.
    """
    if not lines:
        embed.add_field(name=base_name, value="Нет настроенных званий", inline=False)
        return

    total_len = _calc_embed_text_length(embed)

    def can_add(name: str, value: str) -> bool:
        return (total_len + len(name) + len(value)) <= max_total_chars

    total_items = len(lines)
    page = 1
    index = 0
    while index < total_items:
        slice_lines = lines[index:index + lines_per_field]
        name = base_name if page == 1 else f"{base_name} (стр. {page})"
        value = "\n".join(slice_lines)
        if not can_add(name, value):
            break
        embed.add_field(name=name, value=value, inline=False)
        total_len += len(name) + len(value)
        index += lines_per_field
        page += 1

    if index < total_items:
        # Добавим краткое уведомление один раз
        embed.add_field(
            name="ℹ️ Сокращение списка",
            value=f"Показаны не все записи. Отображено: {index} из {total_items}. Список сокращён для соответствия ограничениям Discord.",
            inline=False
        )

# ---------------------------------------------------------------------------
# Построение страниц списка званий в отдельных эмбедах
# ---------------------------------------------------------------------------

def _format_rank_line(guild: discord.Guild, rank_data: dict) -> str:
    """Сформировать строку для одного звания."""
    rank_name = rank_data['name']
    role_id = rank_data['role_id']
    rank_level = rank_data['rank_level']
    abbreviation = rank_data.get('abbreviation', '')

    if role_id:
        role = guild.get_role(int(role_id))
        if role:
            abbr_text = f" ({abbreviation})" if abbreviation else ""
            return f"• **{rank_name}**{abbr_text} → {role.mention} (уровень {rank_level})"
        else:
            return f"• **{rank_name}** → `{role_id}` ❌ (роль не найдена, уровень {rank_level})"
    else:
        return f"• **{rank_name}** → ❌ (role_id не найден, уровень {rank_level})"


def _build_rank_pages(guild: discord.Guild, all_ranks: list[dict], *, max_field_chars: int = 1000) -> list[discord.Embed]:
    """Построить список эмбедов-страниц, где значение поля ≤ 1024 символов.

    Разбиваем по символам: добавляем строки, пока суммарная длина не превысит порог,
    затем создаём новый эмбед-страницу.
    """
    if not all_ranks:
        empty = discord.Embed(
            title="📋 Текущие звания",
            description="Нет настроенных званий",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        return [empty]

    # Сформировать все строки
    all_lines = [
        _format_rank_line(guild, rank_data)
        for rank_data in sorted(all_ranks, key=lambda x: x['rank_level'])
    ]

    pages: list[discord.Embed] = []
    chunk: list[str] = []
    chunk_len = 0
    page_num = 1

    def flush_chunk():
        nonlocal chunk, chunk_len, page_num, pages
        if not chunk:
            return
        page_embed = discord.Embed(
            title=f"📋 Текущие звания (стр. {page_num})",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        page_embed.add_field(name="Список", value="\n".join(chunk), inline=False)
        pages.append(page_embed)
        page_num += 1
        chunk = []
        chunk_len = 0

    for line in all_lines:
        # +1 на перевод строки при склейке
        line_len = len(line) + (1 if chunk else 0)
        if chunk_len + line_len > max_field_chars:
            flush_chunk()
        chunk.append(line)
        chunk_len += line_len

    flush_chunk()

    return pages


class RankRoleModal(BaseSettingsModal):
    """Modal for adding/editing rank roles"""

    def __init__(self, edit_rank=None):
        self.edit_rank = edit_rank
        title = f"Редактировать звание: {edit_rank}" if edit_rank else "Добавить звание"
        super().__init__(title=title)

        # Get current rank data from database instead of config
        current_role_id = ""
        current_rank_level = ""
        current_abbreviation = ""

        if edit_rank:
            # Get rank data from database
            rank_data = rank_manager.get_rank_by_name(edit_rank)
            if rank_data:
                current_role_id = str(rank_data.get('role_id', ''))
                current_rank_level = str(rank_data.get('rank_level', ''))
                current_abbreviation = str(rank_data.get('abbreviation', ''))
        
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
            label="🆔 ID роли или упоминание",
            placeholder="Например: @Рядовой или 1246114675574313021",
            min_length=1,
            max_length=100,
            required=True,
            default=current_role_id
        )
        self.add_item(self.role_id)
        
        self.rank_level = ui.TextInput(
            label="Ранг звания (число)",
            placeholder="Например: 1 для Рядового, 12 для Капитана",
            min_length=1,
            max_length=3,
            required=True,
            default=current_rank_level
        )
        self.add_item(self.rank_level)

        self.abbreviation = ui.TextInput(
            label="Аббревиатура (необязательно)",
            placeholder="Например: Р-й, К-н, Мл. Л-т",
            min_length=0,
            max_length=20,
            required=False,
            default=current_abbreviation
        )
        self.add_item(self.abbreviation)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            rank_name = self.rank_name.value.strip()
            role_input = self.role_id.value.strip()
            rank_level_input = self.rank_level.value.strip()
            abbreviation = self.abbreviation.value.strip() if self.abbreviation.value else None

            # Parse and validate rank level
            try:
                rank_level = int(rank_level_input)
                if rank_level < 1 or rank_level > 50:
                    await self.send_error_message(
                        interaction,
                        "Неверный ранг",
                        "Ранг звания должен быть числом от 1 до 50."
                    )
                    return
            except ValueError:
                await self.send_error_message(
                    interaction,
                    "Неверный формат ранга",
                    "Ранг звания должен быть числом."
                )
                return

            # Parse role ID
            role_id = self._parse_role_input(role_input, interaction.guild)
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

            # Check for duplicate rank levels in database
            all_ranks = await rank_manager.get_all_active_ranks()
            for existing_rank in all_ranks:
                if existing_rank['name'] != self.edit_rank:  # Skip current rank when editing
                    if existing_rank['rank_level'] == rank_level:
                        await self.send_error_message(
                            interaction,
                            "Дублирующийся ранг",
                            f"Ранг {rank_level} уже используется для звания '{existing_rank['name']}'. Выберите другой ранг."
                        )
                        return

            # Save to database
            if self.edit_rank:
                # Update existing rank
                success, message = await rank_manager.update_rank_in_database(
                    rank_name, role_id, rank_level, abbreviation
                )
            else:
                # Add new rank
                success, message = await rank_manager.add_rank_to_database(
                    rank_name, role_id, rank_level
                )
                # Update abbreviation if provided
                if success and abbreviation:
                    await rank_manager.update_rank_in_database(
                        rank_name, role_id, rank_level, abbreviation
                    )

            if not success:
                await self.send_error_message(
                    interaction,
                    "Ошибка сохранения",
                    message
                )
                return

            await interaction.response.send_message(
                f"✅ {message}",
                ephemeral=True
            )

        except Exception as e:
            logger.error("Error in RankRoleModal.on_submit: %s", e)
            import traceback
            traceback.print_exc()
            await self.send_error_message(
                interaction,
                "Ошибка",
                "Произошла непредвиденная ошибка при сохранении звания."
            )

    def _parse_role_input(self, role_input: str, guild: discord.Guild = None) -> int:
        """Parse role input and extract role ID.

        Accepts:
        - role mention: <@&123456789012345678>
        - numeric ID: 123456789012345678
        - role name (if guild provided): "Рядовой" (case-insensitive, exact -> startswith -> substring)
        Returns role ID (int) or None if not found/parseable.
        """
        if not role_input:
            return None

        role_input = role_input.strip()

        # Strip mention format <@&ID>
        if role_input.startswith('<@&') and role_input.endswith('>'):
            role_input = role_input[3:-1]

        # If looks like an ID, try to convert
        try:
            return int(role_input)
        except (ValueError, TypeError):
            pass

        # If a guild is provided, try to resolve by role name
        if guild:
            lowered = role_input.lower()

            # 1) Exact case-insensitive match
            for role in guild.roles:
                if role.name.lower() == lowered:
                    return role.id

            # 2) Startswith match (useful for shortened input)
            for role in guild.roles:
                if role.name.lower().startswith(lowered):
                    return role.id

            # 3) Substring match
            for role in guild.roles:
                if lowered in role.name.lower():
                    return role.id

        # Not found
        return None


class KeyRoleModal(BaseSettingsModal):
    """Modal for setting the key role for rank synchronization"""
    
    def __init__(self):
        super().__init__(title="Настройка ключевой роли")
        
        config = load_config()
        current_sync_key_role_id = config.get('rank_sync_key_role')
        current_key_role_display = str(current_sync_key_role_id) if current_sync_key_role_id else ""
        
        self.role_input = ui.TextInput(
            label="🆔 ID роли или упоминание",
            placeholder="Например: @Военнослужащие или 1234567890123456789",
            min_length=1,
            max_length=100,
            required=True,
            default=current_key_role_display
        )
        self.add_item(self.role_input)
    
    def _parse_role_input(self, role_input: str, guild: discord.Guild = None) -> int:
        """Parse role input and extract role ID.

        Accepts:
        - role mention: <@&123456789012345678>
        - numeric ID: 123456789012345678
        - role name (if guild provided): "Рядовой" (case-insensitive, exact -> startswith -> substring)
        Returns role ID (int) or None if not found/parseable.
        """
        if not role_input:
            return None

        role_input = role_input.strip()

        # Strip mention format <@&ID>
        if role_input.startswith('<@&') and role_input.endswith('>'):
            role_input = role_input[3:-1]

        # If looks like an ID, try to convert
        try:
            return int(role_input)
        except (ValueError, TypeError):
            pass

        # If a guild is provided, try to resolve by role name
        if guild:
            lowered = role_input.lower()

            # 1) Exact case-insensitive match
            for role in guild.roles:
                if role.name.lower() == lowered:
                    return role.id

            # 2) Startswith match (useful for shortened input)
            for role in guild.roles:
                if role.name.lower().startswith(lowered):
                    return role.id

            # 3) Substring match
            for role in guild.roles:
                if lowered in role.name.lower():
                    return role.id

        # Not found
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

            # Remove Discord role association from database
            success, message = await rank_manager.delete_rank_from_database(self.rank_name)

            if success:
                embed = discord.Embed(
                    title="✅ Discord роль звания удалена",
                    description=f"✅ Discord роль звания **{self.rank_name}** успешно удалена из базы данных.\n\n"
                               f"**Примечание:** Название звания сохранено в истории для целостности данных.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )

                # Refresh the view with updated data
                all_ranks = await rank_manager.get_all_active_ranks()
                view = RankRolesConfigView(all_ranks)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                await self.send_error_message(
                    interaction,
                    "Ошибка удаления",
                    message
                )

        except Exception as e:
            await self.send_error_message(
                interaction,
                "Ошибка удаления",
                f"Произошла ошибка при удалении звания: {e}"
            )


class RankRolesSelect(ui.Select):
    """Select menu for managing rank roles"""

    def __init__(self, ranks_data=None):
        # If ranks_data not provided, create placeholder options
        if ranks_data is None:
            options = [
                discord.SelectOption(
                    label="Загрузка...",
                    description="Получение данных из базы данных",
                    emoji="⏳",
                    value="loading"
                )
            ]
        else:
            options = [
                discord.SelectOption(
                    label="Добавить звание",
                    description="Добавить новое звание",
                    emoji="➕",
                    value="add_rank"
                )
            ]

            # Add existing ranks for editing
            for rank_data in sorted(ranks_data, key=lambda x: x['rank_level']):
                if len(options) < 25:  # Discord limit
                    rank_name = rank_data['name']
                    options.append(
                        discord.SelectOption(
                            label=f"{rank_name}",
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

        self.ranks_data = ranks_data
    
    async def callback(self, interaction: discord.Interaction):
        try:
            selected_value = self.values[0]
            
            if selected_value == "error":
                await interaction.response.send_message(" Произошла ошибка при загрузке настроек", ephemeral=True)
                return
            
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
        except Exception as e:
            logger.warning("Error in RankRolesSelect.callback: %s", e)
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(" Произошла ошибка при обработке действия", ephemeral=True)
            except:
                await interaction.followup.send("❌ Произошла ошибка при обработке действия", ephemeral=True)


class RankRoleDeleteSelect(ui.Select):
    """Select menu for deleting rank roles"""

    def __init__(self, ranks_data=None):
        # If ranks_data not provided, create placeholder options
        if ranks_data is None:
            options = [
                discord.SelectOption(
                    label="Загрузка...",
                    description="Получение данных из базы данных",
                    emoji="⏳",
                    value="loading"
                )
            ]
        else:
            options = []

            # Add existing ranks for deletion
            for rank_data in sorted(ranks_data, key=lambda x: x['rank_level']):
                if len(options) < 25:  # Discord limit
                    rank_name = rank_data['name']
                    options.append(
                        discord.SelectOption(
                            label=f"{rank_name}",
                            description=f"Удалить Discord роль у звания {rank_name}",
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

        self.ranks_data = ranks_data
    
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


from .base import SectionSettingsView
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class RankRolesConfigView(SectionSettingsView):
    """Main view for rank roles configuration"""

    def __init__(self, ranks_data=None):
        super().__init__(title="🎖️ Настройка ролей званий", description="Управление связыванием званий с ролями на сервере")
        self.add_item(RankRolesSelect(ranks_data))
        self.add_item(RankRoleDeleteSelect(ranks_data))
        # Пагинация содержимого списка званий
        self._pages: list[str] = []
        self._page_index: int = 0
        self._total_pages: int = 0

    def set_pages(self, pages: list[str]):
        self._pages = pages or []
        self._page_index = 0
        self._total_pages = len(self._pages)

    def build_main_embed(self, guild: discord.Guild, *, refreshed: bool = False) -> discord.Embed:
        description = (
            "Управление связыванием званий с ролями на сервере.\n"
            "**Источник данных: PostgreSQL база данных**\n\n"
            + ("Обновлено из БД: последние изменения применены." if refreshed else "")
        ).strip()

        embed = discord.Embed(
            title="🎖️ Настройка ролей званий",
            description=description,
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )

        if self._pages:
            embed.add_field(
                name=f"📋 Текущие звания (стр. {self._page_index + 1}/{self._total_pages})",
                value=self._pages[self._page_index],
                inline=False
            )
        else:
            embed.add_field(
                name="❌ Звания не настроены",
                value="Добавьте первое звание, используя меню ниже.",
                inline=False
            )

        embed.add_field(
            name="🔧 Доступные действия:",
            value=(
                "• **Добавить звание** - связать новое звание с ролью\n"
                "• **Редактировать звание** - изменить существующее звание\n"
                "• **Удалить звание** - удалить Discord роль у звания\n"
                "• **Инициализировать по умолчанию** - загрузить стандартные звания"
            ),
            inline=False
        )

        embed.add_field(
            name="ℹ️ Информация о синхронизации:",
            value=(
                "**🔄 Синхронизировать с БД**: загружает актуальные данные из PostgreSQL в кэш бота\n"
                "**📤 Отправить в БД**: сохраняет текущие данные из кэша в PostgreSQL\n\n"
                "**Ключевая роль** ограничивает проверку только участниками с определённой ролью, "
                "что повышает производительность на больших серверах."
            ),
            inline=False
        )
        return embed

    @ui.button(label="⬅️ Страница", style=discord.ButtonStyle.secondary, row=3)
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        try:
            if self._total_pages <= 1:
                await interaction.response.defer(ephemeral=True)
                return
            self._page_index = max(0, self._page_index - 1)
            embed = self.build_main_embed(interaction.guild)
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.warning("Ошибка переключения на предыдущую страницу: %s", e)
            try:
                await interaction.response.defer(ephemeral=True)
            except Exception:
                pass

    @ui.button(label="Страница ➡️", style=discord.ButtonStyle.secondary, row=3)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        try:
            if self._total_pages <= 1:
                await interaction.response.defer(ephemeral=True)
                return
            self._page_index = min(self._total_pages - 1, self._page_index + 1)
            embed = self.build_main_embed(interaction.guild)
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.warning("Ошибка переключения на следующую страницу: %s", e)
            try:
                await interaction.response.defer(ephemeral=True)
            except Exception:
                pass
    
    @ui.button(label="🔄 Перезагрузить из БД", style=discord.ButtonStyle.primary, row=2)
    async def refresh_from_db(self, interaction: discord.Interaction, button: ui.Button):
        """Перезагрузить список званий из БД и обновить представление"""
        try:
            await interaction.response.defer(ephemeral=True)
            # Получаем актуальные данные из базы
            all_ranks = await rank_manager.get_all_active_ranks()

            # Пересобираем пагинацию и обновляем основной эмбед
            pages_embeds = _build_rank_pages(interaction.guild, all_ranks)
            page_values = [p.fields[0].value for p in pages_embeds]
            self.set_pages(page_values)
            self._total_pages = len(self._pages)
            self._page_index = min(self._page_index, max(0, self._total_pages - 1))

            embed = self.build_main_embed(interaction.guild, refreshed=True)
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Произошла ошибка при обновлении: {str(e)}",
                color=discord.Color.red()
            )
            try:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            except Exception:
                pass


async def show_rank_roles_config(interaction: discord.Interaction):
    """Show rank roles configuration interface"""
    try:
        # Get ranks from database instead of config
        all_ranks = await rank_manager.get_all_active_ranks()

        embed = discord.Embed(
            title="⚙️ Настройка ролей званий",
            description=(
                "Управление связыванием званий с ролями на сервере.\n"
                "**Источник данных: PostgreSQL база данных**"
            ),
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )

        # Основной эмбед без списка, чтобы не превысить лимит
        if not all_ranks:
            embed.add_field(
                name="❌ Звания не настроены",
                value="Добавьте первое звание, используя кнопку ниже.",
                inline=False
            )

        embed.add_field(
            name="📋 Доступные действия:",
            value=(
                "• **Добавить звание** - связать новое звание с ролью\n"
                "• **Редактировать звание** - изменить существующее звание\n"
                "• **Удалить звание** - удалить Discord роль у звания\n"
                "• **Инициализировать по умолчанию** - загрузить стандартные звания"
            ),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Информация о синхронизации:",
            value=(
                "** Синхронизировать с БД**: загружает актуальные данные из PostgreSQL в кэш бота\n"
                "** Отправить в БД**: сохраняет текущие данные из кэша в PostgreSQL\n\n"
                "**Ключевая роль** ограничивает проверку только участниками с определённой ролью, "
                "что повышает производительность на больших серверах."
            ),
            inline=False
        )
        
        # Сбор страниц и вывод в основном эмбеде
        pages_embeds = _build_rank_pages(interaction.guild, all_ranks)
        page_values = [p.fields[0].value for p in pages_embeds]
        view = RankRolesConfigView(all_ranks)
        view.set_pages(page_values)
        main_embed = view.build_main_embed(interaction.guild)
        await interaction.followup.send(embed=main_embed, view=view, ephemeral=True)
    
    except Exception as e:
        logger.warning("Error in show_rank_roles_config: %s", e)
        import traceback
        traceback.print_exc()
        
        error_embed = discord.Embed(
            title="❌ Ошибка",
            description=f"Произошла ошибка при загрузке настроек ролей званий: {str(e)}",
            color=discord.Color.red()
        )
        try:
            await interaction.followup.send(embed=error_embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=error_embed, ephemeral=True)
def initialize_default_ranks():
    """Initialize default rank roles in config if not present"""
    config = load_config()
    changes_made = False
    
    if 'rank_roles' not in config or not config['rank_roles']:
        default_ranks = {
            "Рядовой": {"role_id": 1246114675574313021, "rank_level": 1},
            "Ефрейтор": {"role_id": 1246114674638983270, "rank_level": 2},
            "Мл. Сержант": {"role_id": 1261982952275972187, "rank_level": 3},
            "Сержант": {"role_id": 1246114673997123595, "rank_level": 4},
            "Ст. Сержант": {"role_id": 1246114672352952403, "rank_level": 5},
            "Старшина": {"role_id": 1246114604958879754, "rank_level": 6},
            "Прапорщик": {"role_id": 1246114604329865327, "rank_level": 7},
            "Ст. Прапорщик": {"role_id": 1251045305793773648, "rank_level": 8},
            "Мл. Лейтенант": {"role_id": 1251045263062335590, "rank_level": 9},
            "Лейтенант": {"role_id": 1246115365746901094, "rank_level": 10},
            "Ст. Лейтенант": {"role_id": 1246114469340250214, "rank_level": 11},
            "Капитан": {"role_id": 1246114469336322169, "rank_level": 12},
            "Майор": {"role_id": 1246114042821607424, "rank_level": 13},
            "Подполковник": {"role_id": 1246114038744875090, "rank_level": 14},
            "Полковник": {"role_id": 1246113825791672431, "rank_level": 15}
        }
        
        config['rank_roles'] = default_ranks
        changes_made = True
        logger.info("Initialized default rank roles with hierarchy in config")
    
    # Initialize default key role if not present (military role from config)
    if 'rank_sync_key_role' not in config and config.get('military_role'):
        config['rank_sync_key_role'] = config['military_role']
        changes_made = True
        logger.info("Initialized default key role for rank sync from military role")
    
    if changes_made:
        save_config(config)
        return True
    
    return False