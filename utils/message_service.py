"""
Unified Message Service for Discord bot interactions
Provides standardized methods for sending messages, embeds, and DMs
"""
import discord
from typing import Dict, Any, List
from utils.message_manager import get_message, get_private_messages, get_faction_name
from utils.database_manager.rank_manager import rank_manager
from utils.message_constants import MessageColors, MessageEmojis
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

class MessageService:
    """
    Unified service for sending messages in Discord bot
    Handles interaction responses, channel messages, and DMs with consistent formatting
    """

    @staticmethod
    def send_response(interaction: discord.Interaction,
                     content: str = None,
                     embed: discord.Embed = None,
                     view: discord.ui.View = None,
                     ephemeral: bool = False) -> bool:
        """
        Send response to interaction, automatically choosing between response and followup

        Args:
            interaction: Discord interaction object
            content: Text content of the message
            embed: Discord embed object
            view: Discord view with components
            ephemeral: Whether message should be ephemeral (private)

        Returns:
            bool: True if message was sent successfully
        """
        try:
            kwargs = {"ephemeral": ephemeral}
            if embed:
                kwargs["embed"] = embed
            if view:
                kwargs["view"] = view
            if content:
                kwargs["content"] = content

            if interaction.response.is_done():
                # Interaction already responded, use followup
                if hasattr(interaction, 'followup'):
                    interaction.followup.send(**kwargs)
                else:
                    logger.info("MessageService: Cannot send followup - no followup available")
                    return False
            else:
                # Interaction not responded yet, use response
                interaction.response.send_message(**kwargs)

            return True
        except Exception as e:
            logger.error("MessageService.send_response error: %s", e)
            return False

    @staticmethod
    def send_error(interaction: discord.Interaction,
                  message: str,
                  ephemeral: bool = True) -> bool:
        """
        Send standardized error message

        Args:
            interaction: Discord interaction object
            message: Error message text
            ephemeral: Whether message should be ephemeral

        Returns:
            bool: True if message was sent successfully
        """
        embed = discord.Embed(
            title=f"{MessageEmojis.ERROR} Ошибка",
            description=message,
            color=MessageColors.ERROR,
            timestamp=discord.utils.utcnow()
        )
        return MessageService.send_response(interaction, embed=embed, ephemeral=ephemeral)

    @staticmethod
    def send_success(interaction: discord.Interaction,
                    message: str,
                    ephemeral: bool = True) -> bool:
        """
        Send standardized success message

        Args:
            interaction: Discord interaction object
            message: Success message text
            ephemeral: Whether message should be ephemeral

        Returns:
            bool: True if message was sent successfully
        """
        embed = discord.Embed(
            title=f"{MessageEmojis.SUCCESS} Успешно",
            description=message,
            color=MessageColors.SUCCESS,
            timestamp=discord.utils.utcnow()
        )
        return MessageService.send_response(interaction, embed=embed, ephemeral=ephemeral)

    @staticmethod
    def send_info(interaction: discord.Interaction,
                 message: str,
                 ephemeral: bool = True) -> bool:
        """
        Send standardized info message

        Args:
            interaction: Discord interaction object
            message: Info message text
            ephemeral: Whether message should be ephemeral

        Returns:
            bool: True if message was sent successfully
        """
        embed = discord.Embed(
            title=f"{MessageEmojis.INFO} Информация",
            description=message,
            color=MessageColors.INFO,
            timestamp=discord.utils.utcnow()
        )
        return MessageService.send_response(interaction, embed=embed, ephemeral=ephemeral)

    @staticmethod
    def create_embed(title: str = None,
                    description: str = None,
                    color: discord.Color = MessageColors.INFO,
                    fields: List[Dict[str, Any]] = None,
                    timestamp: bool = True) -> discord.Embed:
        """
        Create standardized embed with optional fields

        Args:
            title: Embed title
            description: Embed description
            color: Embed color
            fields: List of field dictionaries with 'name', 'value', 'inline' keys
            timestamp: Whether to add timestamp

        Returns:
            discord.Embed: Created embed object
        """
        embed = discord.Embed(color=color)

        if title:
            embed.title = title
        if description:
            embed.description = description
        if timestamp:
            embed.timestamp = discord.utils.utcnow()

        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', ''),
                    value=field.get('value', ''),
                    inline=field.get('inline', False)
                )

        return embed

    @staticmethod
    def get_template(guild_id: int, key_path: str, default: str = None) -> str:
        """
        Get message template from YAML files

        Args:
            guild_id: Guild ID for guild-specific messages
            key_path: Dot-separated path to template (e.g., 'templates.errors.general')
            default: Default value if template not found

        Returns:
            str: Template string
        """
        return get_message(guild_id, key_path, default)

    @staticmethod
    def get_private_template(guild_id: int, key_path: str, default: str = None) -> str:
        """
        Get private message template from YAML files

        Args:
            guild_id: Guild ID for guild-specific messages
            key_path: Dot-separated path to template (e.g., 'role_assignment.approval.title')
            default: Default value if template not found

        Returns:
            str: Template string
        """
        return get_private_messages(guild_id, key_path, default)

    @staticmethod
    async def send_dm(user: discord.User,
                     title: str = None,
                     description: str = None,
                     fields: List[Dict[str, Any]] = None,
                     color: discord.Color = MessageColors.INFO) -> bool:
        """
        Send standardized DM (Direct Message) to user with embed

        Args:
            user: Discord user to send DM to
            title: Embed title
            description: Embed description
            fields: List of field dictionaries with 'name', 'value', 'inline' keys
            color: Embed color

        Returns:
            bool: True if DM was sent successfully
        """
        try:
            embed = MessageService.create_embed(
                title=title,
                description=description,
                color=color,
                fields=fields,
                timestamp=True
            )

            await user.send(embed=embed)
            return True
        except discord.Forbidden:
            logger.info("MessageService: Cannot send DM to %s - DMs disabled", user)
            return False
        except Exception as e:
            logger.error("MessageService.send_dm error for %s: %s", user, e)
            return False

    @staticmethod
    async def send_approval_dm(user: discord.User,
                              guild_id: int,
                              role_type: str = "сотрудника") -> bool:
        """
        Send standardized approval DM using templates

        Args:
            user: Discord user to send DM to
            guild_id: Guild ID for template localization
            role_type: Type of role being approved (сотрудника, госслужащего, etc.)

        Returns:
            bool: True if DM was sent successfully
        """
        try:
            title = MessageService.get_private_template(guild_id, 'role_assignment.approval.title', '✅ Заявка одобрена!')
            description = MessageService.get_private_template(guild_id, 'role_assignment.approval.description', '').format(role_type=role_type)

            return await MessageService.send_dm(
                user=user,
                title=title,
                description=description,
                color=MessageColors.SUCCESS
            )
        except Exception as e:
            logger.error("MessageService.send_approval_dm error for %s: %s", user, e)
            return False

    @staticmethod
    async def send_rejection_dm(user: discord.User,
                               guild_id: int,
                               rejection_reason: str = None,
                               role_type: str = "сотрудника") -> bool:
        """
        Send standardized rejection DM using templates

        Args:
            user: Discord user to send DM to
            guild_id: Guild ID for template localization
            rejection_reason: Specific reason for rejection (optional)
            role_type: Type of role being rejected (сотрудника, госслужащего, etc.)

        Returns:
            bool: True if DM was sent successfully
        """
        try:
            title = MessageService.get_private_template(guild_id, 'role_assignment.rejection.title', '❌ Заявка отклонена')

            if rejection_reason:
                description = MessageService.get_private_template(guild_id, 'role_assignment.rejection.description', '').format(rejection_reason=rejection_reason)
            else:
                description = MessageService.get_private_template(guild_id, 'role_assignment.rejection.simple', '').format(role_type=role_type)

            return await MessageService.send_dm(
                user=user,
                title=title,
                description=description,
                color=MessageColors.ERROR
            )
        except Exception as e:
            logger.error("MessageService.send_rejection_dm error for %s: %s", user, e)
            return False

    @staticmethod
    async def send_notification_dm(user: discord.User,
                                  title: str,
                                  description: str,
                                  fields: List[Dict[str, Any]] = None) -> bool:
        """
        Send general notification DM

        Args:
            user: Discord user to send DM to
            title: Notification title
            description: Notification description
            fields: Additional fields for embed

        Returns:
            bool: True if DM was sent successfully
        """
        return await MessageService.send_dm(
            user=user,
            title=title,
            description=description,
            fields=fields,
            color=MessageColors.NOTIFICATION
        )

    @staticmethod
    async def send_welcome_dm(member: discord.Member) -> bool:
        """
        Send welcome DM with multiple embeds to new member

        Args:
            member: Discord member to welcome

        Returns:
            bool: True if DM was sent successfully
        """
        try:
            # Get role assignment link/channel info
            from utils.config_manager import load_config, get_role_assignment_message_link
            config = load_config()
            role_assignment_channel_id = config.get('role_assignment_channel')

            message_link = get_role_assignment_message_link(member.guild.id)
            if message_link:
                step_text = f"1. **[🎯 Подать заявку на роль]({message_link})**\n"
            elif role_assignment_channel_id:
                role_channel = member.guild.get_channel(role_assignment_channel_id)
                if role_channel:
                    step_text = f"1. **Получите роль** - перейдите в {role_channel.mention}\n"
                else:
                    step_text = "1. **Получите роль** - перейдите в канал получения ролей\n"
            else:
                step_text = "1. **Получите роль** - перейдите в канал получения ролей\n"

            # Create main welcome embed
            embed = discord.Embed(
                title=MessageService.get_private_template(member.guild.id, "welcome.title", "🎖️ Добро пожаловать в нашу Фракцию!"),
                color=MessageColors.SUCCESS,
                timestamp=discord.utils.utcnow()
            )
            embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")

            embed.add_field(
                name="📋 Что делать дальше?",
                value=MessageService.get_private_template(member.guild.id, "welcome.description", "").format(step_text=step_text),
                inline=False
            )

            embed.add_field(
                name="👤 Уже являетесь госслужащим?",
                value=MessageService.get_private_template(member.guild.id, "welcome.existing_member_info", ""),
                inline=False
            )

            # Create military ticket embed
            embed_ticket = discord.Embed(
                title=MessageService.get_private_template(member.guild.id, "welcome.military_ticket_title", "🎟️ Как получить военный билет?"),
                color=MessageColors.SUCCESS,
                timestamp=discord.utils.utcnow()
            )

            embed_ticket.add_field(
                name="",
                value=MessageService.get_private_template(member.guild.id, "welcome.military_ticket_info", ""),
                inline=False
            )

            embed_ticket.set_footer(
                text=MessageService.get_private_template(member.guild.id, "welcome.footer", "Желаем успешной службы! | Руководство ВС РФ"),
                icon_url=member.guild.icon.url if member.guild.icon else None
            )

            # Send both embeds
            await member.send(embeds=[embed, embed_ticket])
            logger.info(f"Sent welcome message to {member.display_name} ({member.id})")
            return True

        except discord.Forbidden:
            logger.info(f"MessageService: Cannot send welcome DM to {member.display_name} - DMs disabled")
            return False
        except Exception as e:
            logger.error("MessageService.send_welcome_dm error for %s: %s", member, e)
            return False

    @staticmethod
    async def send_recruitment_dm(user: discord.User,
                                 guild_id: int,
                                 full_name: str,
                                 static: str) -> bool:
        """
        Send recruitment DM to newly recruited user

        Args:
            user: Discord user who was recruited
            guild_id: Guild ID for template localization
            full_name: Full name of the recruited person
            static: Static identifier

        Returns:
            bool: True if DM was sent successfully
        """
        try:
            title = MessageService.get_private_template(guild_id, 'recruitment.title', '🎖️ Вы приняты на службу!')
            description = MessageService.get_private_template(guild_id, 'recruitment.description', 'Поздравляем! Вы успешно приняты в Вооруженные Силы.')

            fields = [
                {
                    'name': MessageService.get_private_template(guild_id, 'recruitment.fields.name', 'ФИО'),
                    'value': full_name,
                    'inline': True
                },
                {
                    'name': MessageService.get_private_template(guild_id, 'recruitment.fields.static', 'Статический'),
                    'value': static,
                    'inline': True
                },
                {
                    'name': MessageService.get_private_template(guild_id, 'recruitment.fields.rank', 'Звание'),
                    'value': rank_manager.get_default_recruit_rank_sync(),
                    'inline': True
                },
                {
                    'name': MessageService.get_private_template(guild_id, 'recruitment.fields.department', 'Подразделение'),
                    'value': "Военная Академия",
                    'inline': False
                }
            ]

            return await MessageService.send_dm(
                user=user,
                title=title,
                description=description,
                fields=fields,
                color=MessageColors.SUCCESS
            )
        except Exception as e:
            logger.error("MessageService.send_recruitment_dm error for %s: %s", user, e)
            return False

    @staticmethod
    async def send_dismissal_dm(user: discord.User,
                               guild_id: int,
                               reason: str,
                               dismissed_by: str) -> bool:
        """
        Send dismissal DM to dismissed user

        Args:
            user: Discord user who was dismissed
            guild_id: Guild ID for template localization
            reason: Reason for dismissal
            dismissed_by: Name of person who performed dismissal

        Returns:
            bool: True if DM was sent successfully
        """
        try:
            title = MessageService.get_private_template(guild_id, 'dismissal.title', '⚠️ Увольнение со службы')
            description = MessageService.get_private_template(guild_id, 'dismissal.description', f'К сожалению, ваша служба в {get_faction_name(guild_id)} завершена.')

            fields = [
                {
                    'name': MessageService.get_private_template(guild_id, 'dismissal.fields.reason', 'Причина увольнения'),
                    'value': reason,
                    'inline': False
                },
                {
                    'name': MessageService.get_private_template(guild_id, 'dismissal.fields.dismissed_by', 'Уволен'),
                    'value': dismissed_by,
                    'inline': False
                }
            ]

            return await MessageService.send_dm(
                user=user,
                title=title,
                description=description,
                fields=fields,
                color=MessageColors.WARNING
            )
        except Exception as e:
            logger.error("MessageService.send_dismissal_dm error for %s: %s", user, e)
            return False

    @staticmethod
    async def send_leave_approval_dm(user: discord.User,
                                    guild_id: int,
                                    start_time: str,
                                    end_time: str,
                                    reason: str,
                                    approved_by: str) -> bool:
        """
        Send leave request approval DM to user

        Args:
            user: Discord user whose leave was approved
            guild_id: Guild ID for template localization
            start_time: Start time of leave
            end_time: End time of leave
            reason: Reason for leave
            approved_by: Mention of person who approved

        Returns:
            bool: True if DM was sent successfully
        """
        try:
            title = MessageService.get_private_template(guild_id, 'leave_requests.approval.title', '✅ Отпуск одобрен')
            description = MessageService.get_private_template(guild_id, 'leave_requests.approval.description',
                'Ваш отпуск на {date} с {time} по причине "{reason}" был одобрен.').format(
                    date=discord.utils.format_dt(discord.utils.utcnow(), 'd'),
                    time=f"{start_time} - {end_time}",
                    reason=reason
                )

            fields = [
                {
                    'name': MessageService.get_private_template(guild_id, 'leave_requests.approval.approved_by', 'Одобрено'),
                    'value': approved_by,
                    'inline': True
                }
            ]

            return await MessageService.send_dm(
                user=user,
                title=title,
                description=description,
                fields=fields,
                color=MessageColors.SUCCESS
            )
        except Exception as e:
            logger.error("MessageService.send_leave_approval_dm error for %s: %s", user, e)
            return False