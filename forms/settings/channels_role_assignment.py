"""
Role assignment channel configuration
"""
import discord
from discord import ui
from utils.config_manager import load_config, save_config, get_recruitment_config
from .base import BaseSettingsView, BaseSettingsModal, ConfigDisplayHelper
from .channels_base import ChannelSelectionModal


class RoleAssignmentChannelView(BaseSettingsView):
    """View for role assignment channel configuration"""
    
    @discord.ui.button(label="📂 Настроить канал", style=discord.ButtonStyle.green)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelSelectionModal("role_assignment")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🏷️ Роли для этой фракции", style=discord.ButtonStyle.primary)
    async def set_military_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("military_roles", "🪖 Настройка ролей для этой фракции", "Укажите роли для этой фракции (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🏷️ Роли доступа к поставкам", style=discord.ButtonStyle.secondary)
    async def set_supplier_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("supplier_roles", "📦 Настройка ролей доступа к поставкам", "Укажите роли для доступа к поставкам (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🏷️ Роли гражданских", style=discord.ButtonStyle.secondary)
    async def set_civilian_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("civilian_roles", "👤 Настройка ролей гражданских", "Укажите роли для гражданских (через запятую)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📢 Настроить ping-роли", style=discord.ButtonStyle.green)
    async def set_ping_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RolePingConfigView()
        await view.show_ping_config(interaction)

    @discord.ui.button(label="⚙️ Настройки приёма", style=discord.ButtonStyle.grey)
    async def set_recruitment_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RecruitmentConfigView()
        await view.show_config(interaction)


class RolePingConfigView(BaseSettingsView):
    """View for configuring role assignment ping settings"""
    
    def __init__(self):
        super().__init__()
    
    async def show_ping_config(self, interaction: discord.Interaction):
        """Show ping role configuration interface"""
        embed = discord.Embed(
            title="📢 Настройка пинг-ролей",
            description="Настройте роли для уведомлений о новых заявках.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        config = load_config()
        helper = ConfigDisplayHelper()
        
        embed.add_field(
            name="📣 Пинг-роли для военных заявок:",
            value=helper.format_roles_list(config, 'military_role_assignment_ping_roles', interaction.guild),
            inline=False
        )
        
        embed.add_field(
            name="📦 Пинг-роли для заявок доступа к поставкам:",
            value=helper.format_roles_list(config, 'supplier_role_assignment_ping_roles', interaction.guild),
            inline=False
        )
        
        embed.add_field(
            name="📣 Пинг-роли для гражданских заявок:",
            value=helper.format_roles_list(config, 'civilian_role_assignment_ping_roles', interaction.guild),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Информация:",
            value="Выберите роли, которые будут получать уведомления при подаче новых заявок. Можно указать несколько ролей через запятую. Формат пинга: `-# @роль1 @роль2`",
            inline=False
        )
        
        view = RolePingButtonsView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class RolePingButtonsView(BaseSettingsView):
    """Buttons for ping role configuration"""
    
    @discord.ui.button(label="📣 Пинг военных", style=discord.ButtonStyle.green)
    async def set_military_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("military_role_assignment_ping_roles", "🪖 Пинг-роли для военных", "Укажите роли для уведомлений о военных заявках")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📣 Пинг доступа к поставкам", style=discord.ButtonStyle.secondary)
    async def set_supplier_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("supplier_role_assignment_ping_roles", "📦 Пинг-роли для доступа к поставкам", "Укажите роли для уведомлений о заявках доступа к поставкам")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="‍⚕️ Пинг госслужащих", style=discord.ButtonStyle.secondary)
    async def set_civilian_ping(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .role_config import SetMultipleRolesModal
        modal = SetMultipleRolesModal("civilian_role_assignment_ping_roles", "👤 Пинг-роли для гражданских", "Укажите роли для уведомлений о гражданских заявках")
        await interaction.response.send_modal(modal)


class SetAllowedRecruitRanksModal(BaseSettingsModal):
    """Модаль для установки списка ID рангов, доступных при приёме"""

    def __init__(self):
        super().__init__(title="🎖️ Разрешённые ранги (ID)")

    rank_ids_input = ui.TextInput(
        label="ID рангов через запятую",
        placeholder="Например: 1,2,3 или оставьте пустым для всех",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            text = (self.rank_ids_input.value or "").strip()
            config = load_config()
            recruitment_cfg = config.get('recruitment', {}) or {}

            if not text:
                recruitment_cfg['allowed_rank_ids'] = []
            else:
                ids = []
                for part in text.replace('\n', ',').split(','):
                    val = part.strip()
                    if not val:
                        continue
                    try:
                        ids.append(int(val))
                    except ValueError:
                        continue
                recruitment_cfg['allowed_rank_ids'] = ids

            config['recruitment'] = recruitment_cfg
            save_config(config)

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="✅ Сохранено",
                    description="Разрешённые ранги обновлены",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Ошибка",
                    description=str(e),
                    color=discord.Color.red()
                ),
                ephemeral=True
            )


class RecruitmentConfigView(BaseSettingsView):
    """Настройки приёма (ранги, дефолты). Подразделение — заглушка."""

    def __init__(self):
        super().__init__()

    async def _resolve_ranks_text(self, rank_ids: list[int], guild: discord.Guild) -> str:
        if not rank_ids:
            return "Все ранги"

        from utils.database_manager.rank_manager import RankManager
        rm = RankManager()
        parts = []
        for rid in rank_ids[:25]:
            rank = await rm.get_rank_by_id(rid)
            if rank:
                parts.append(f"• {rank['name']} (ID: {rid})")
        return "\n".join(parts) if parts else "Ранги не найдены в БД"

    async def _resolve_default_rank_text(self, rank_id: int | None) -> str:
        if not rank_id:
            return "❌ Не настроено"
        from utils.database_manager.rank_manager import RankManager
        rm = RankManager()
        rank = await rm.get_rank_by_id(rank_id)
        if not rank:
            return f"⚠️ Ранг ID {rank_id} не найден"
        return f"✅ {rank['name']} (ID: {rank_id})"

    async def show_config(self, interaction: discord.Interaction):
        cfg = get_recruitment_config()

        embed = discord.Embed(
            title="🛠 Настройки приёма",
            description="Управление дефолтным званием и выбором ранга при подаче заявки.",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(
            name="Статус",
            value="✅ Включено" if cfg.get('enabled', True) else "❌ Выключено",
            inline=True
        )
        embed.add_field(
            name="Выбор ранга пользователем",
            value="✅ Разрешён" if cfg.get('allow_user_rank_selection') else "❌ Запрещён",
            inline=True
        )

        default_rank_text = await self._resolve_default_rank_text(cfg.get('default_rank_id'))
        allowed_ranks_text = await self._resolve_ranks_text(cfg.get('allowed_rank_ids'), interaction.guild)

        embed.add_field(name="Дефолтный ранг", value=default_rank_text, inline=False)
        embed.add_field(name="Разрешённые ранги", value=allowed_ranks_text, inline=False)

        embed.add_field(
            name="Подразделение (заглушка)",
            value="Всегда ВА (выбор отключён)",
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="🔀 Переключить выбор ранга", style=discord.ButtonStyle.primary)
    async def toggle_rank_select(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            config = load_config()
            rec = config.get('recruitment', {}) or {}
            rec['allow_user_rank_selection'] = not rec.get('allow_user_rank_selection', False)
            config['recruitment'] = rec
            save_config(config)
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="✅ Переключено",
                    description=f"Выбор ранга теперь: {'разрешён' if rec['allow_user_rank_selection'] else 'запрещён'}",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(title="❌ Ошибка", description=str(e), color=discord.Color.red()),
                ephemeral=True
            )

    @discord.ui.button(label="🎯 Дефолтный ранг", style=discord.ButtonStyle.secondary)
    async def set_default_rank_recruit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DefaultRankSelectionModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📜 Разрешённые ранги", style=discord.ButtonStyle.secondary)
    async def set_allowed_ranks(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetAllowedRecruitRanksModal()
        await interaction.response.send_modal(modal)



class DefaultRankSelectionModal(BaseSettingsModal):
    """Modal for selecting default recruit rank by ID or name"""
    
    def __init__(self):
        super().__init__(title="🎖️ Начальное звание")
    
    rank_input = ui.TextInput(
        label="Ранг (ID или название)",
        placeholder="Например: 1 или Рядовой",
        style=discord.TextStyle.short,
        required=False,
        max_length=50
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle rank input - accept both ID and name"""
        try:
            rank_input = self.rank_input.value.strip()
            
            if not rank_input:
                # Clear the default rank
                config = load_config()
                if 'recruitment' in config:
                    config['recruitment']['default_rank_id'] = None
                    save_config(config)
                
                embed = discord.Embed(
                    title="✅ Сброшено",
                    description="Начальное звание сброшено. Будет использоваться дефолт из БД.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Try to parse as rank ID first
            rank_id = None
            rank_obj = None
            
            from utils.database_manager.rank_manager import RankManager
            rm = RankManager()
            
            # Try as ID
            try:
                rank_id = int(rank_input)
                rank_obj = await rm.get_rank_by_id(rank_id)
            except ValueError:
                pass
            
            # Try as name
            if not rank_obj:
                ranks = await rm.get_all_active_ranks()
                for rank in ranks:
                    if rank['name'].lower() == rank_input.lower():
                        rank_obj = rank
                        rank_id = rank['id']
                        break
            
            if not rank_obj:
                embed = discord.Embed(
                    title="❌ Ранг не найден",
                    description=f"Не удалось найти ранг '{rank_input}' по ID или названию.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Save configuration
            config = load_config()
            recruitment_cfg = config.get('recruitment', {}) or {}
            recruitment_cfg['default_rank_id'] = rank_id
            config['recruitment'] = recruitment_cfg
            save_config(config)
            
            embed = discord.Embed(
                title="✅ Настроено",
                description=f"Начальное звание: **{rank_obj['name']}** (ID: {rank_id})",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Произошла ошибка: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def show_role_assignment_config(interaction: discord.Interaction):
    """Show role assignment channel configuration with role management"""
    embed = discord.Embed(
        title="🎖️ Настройка канала получения ролей",
        description="Управление каналом и ролями для системы получения ролей.",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    config = load_config()
    helper = ConfigDisplayHelper()
    
    # Show current channel and message
    embed.add_field(
        name="📂 Текущий канал:",
        value=helper.format_channel_info(config, 'role_assignment_channel', interaction.guild),
        inline=False
    )
    
    # Show role assignment message info
    message_id = config.get('role_assignment_message_id')
    channel_id = config.get('role_assignment_channel')
    if message_id and channel_id:
        message_link = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{message_id}"
        embed.add_field(
            name="📌 Сообщение с кнопками:",
            value=f"[Перейти к сообщению]({message_link}) (ID: {message_id})",
            inline=False
        )
    else:
        embed.add_field(
            name="📌 Сообщение с кнопками:",
            value="❌ Не настроено или не найдено",
            inline=False
        )
    
    # Show current roles
    embed.add_field(
        name="🏷️ Роли военнослужащих:",
        value=helper.format_roles_info(config, 'military_roles', interaction.guild),
        inline=True
    )
    embed.add_field(
        name="🏷️ Роли доступа к поставкам:",
        value=helper.format_roles_info(config, 'supplier_roles', interaction.guild),
        inline=True
    )
    embed.add_field(
        name="🏷️ Роли гражданских:",
        value=helper.format_roles_info(config, 'civilian_roles', interaction.guild),
        inline=True
    )
    
    # Show ping roles
    embed.add_field(
        name="📣 Пинг роли:",
        value=(
            f"🪖 Военные: {helper.format_roles_list(config, 'military_role_assignment_ping_roles', interaction.guild)}\n"
            f"📦 Доступ к поставкам: {helper.format_roles_list(config, 'supplier_role_assignment_ping_roles', interaction.guild)}\n"
            f"👤 Гражданские: {helper.format_roles_list(config, 'civilian_role_assignment_ping_roles', interaction.guild)}"
        ),
        inline=False
    )
    
    # Show default recruit rank
    default_rank_id = config.get('default_recruit_rank_id')
    default_rank_text = "❌ Не настроено"
    
    if default_rank_id:
        from utils.database_manager.rank_manager import RankManager
        rank_manager = RankManager()
        try:
            rank = await rank_manager.get_rank_by_id(default_rank_id)
            if rank:
                role = interaction.guild.get_role(rank.role_id)
                default_rank_text = f"✅ {rank.name} ({role.mention if role else 'Роль не найдена'})"
            else:
                default_rank_text = "❌ Звание не найдено в базе данных"
        except Exception as e:
            default_rank_text = f"❌ Ошибка загрузки: {str(e)}"
    
    embed.add_field(
        name="⭐ Начальное звание для рекрутов:",
        value=default_rank_text,
        inline=False
    )
    
    embed.add_field(
        name="📋 Доступные действия:",
        value=(
            "• **Настроить канал** - установить канал для получения ролей\n"
            "• **Настроить роли** - настроить роли для военных, доступа к поставкам и госслужащих\n"
            "• **Настроить пинги** - настроить роли для уведомлений\n"
            "• **Начальное звание** - настроить звание для новых рекрутов\n"
            "• **Полная настройка** - настроить всё сразу"
        ),
        inline=False
    )
    
    view = RoleAssignmentChannelView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)