"""
Modal forms for personnel context menu operations
"""

import discord
from discord import ui
from datetime import datetime, timezone, timedelta
import re

from .rank_utils import RankHierarchy
from utils.config_manager import load_config, is_moderator_or_admin, is_administrator
from utils.message_manager import get_role_reason
from utils.role_utils import role_utils
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


async def send_audit_message(channel: discord.TextChannel, audit_data: dict, action_type: str = "default"):
    """Common function to send audit messages to channel"""
    moscow_tz = timezone(timedelta(hours=3))
    current_time = datetime.now(moscow_tz)
    
    # Color based on action type
    color_map = {
        "promotion": discord.Color.green(),
        "demotion": discord.Color.orange(),
        "position": discord.Color.blue(),
        "recruitment": discord.Color.green(),
        "dismissal": discord.Color.red(),
        "default": discord.Color.blue()
    }
    
    # Title based on action type
    title_map = {
        "recruitment": "📊 Кадровый аудит - Принятие на службу",
        "dismissal": "🥀 Кадровый аудит - Увольнение",
        "default": "📊 Кадровый аудит"
    }
    
    embed = discord.Embed(
        title=title_map.get(action_type, title_map["default"]),
        color=color_map.get(action_type, color_map["default"]),
        timestamp=discord.utils.utcnow()
    )
    
    # Format name with static
    name_with_static = audit_data['full_name']
    if audit_data.get('static'):
        name_with_static = f"{audit_data['full_name']} | {audit_data['static']}"
    
    embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
    embed.add_field(name="Действие", value=audit_data['action'], inline=False)
    if audit_data.get('reason', ''):
        embed.add_field(name="Причина", value=audit_data['reason'], inline=False)
    embed.add_field(name="Дата Действия", value=current_time.strftime('%d.%m.%Y'), inline=False)
    embed.add_field(name="Подразделение", value=audit_data.get('department', 'Не указано'), inline=False)
    embed.add_field(name="Воинское звание", value=audit_data['rank'], inline=False)
    if audit_data.get('position'):
        embed.add_field(name="Должность", value=audit_data['position'], inline=False)
    embed.add_field(name="Кадровую отписал", value=audit_data['moderator_signed_name'], inline=False)
    
    embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
    
    await channel.send(content=f"<@{audit_data['discord_id']}>", embed=embed)


class PromotionModal(ui.Modal, title="Повышение в звании"):
    """Modal for rank promotion"""
    
    def __init__(self, target_user: discord.Member, current_rank: str, next_rank: str):
        super().__init__()
        self.target_user = target_user
        self.current_rank = current_rank
        
        # Pre-fill with next rank
        self.new_rank = ui.TextInput(
            label="Новое звание",
            placeholder="Звание для назначения",
            default=next_rank,
            min_length=3,
            max_length=50,
            required=True
        )
        self.add_item(self.new_rank)
        
        self.restoration = ui.TextInput(
            label="Восстановление? Поставьте \"+\", если да",
            placeholder="Оставьте пустым для обычного повышения",
            default="-",
            min_length=1,
            max_length=1,
            required=True
        )
        self.add_item(self.restoration)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    " У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return
            
            new_rank_name = self.new_rank.value.strip()
            is_restoration = self.restoration.value.strip() == "+"
            
            # Validate new rank exists
            rank_info = RankHierarchy.get_rank_info(new_rank_name)
            if not rank_info:
                await interaction.response.send_message(
                    f"❌ Звание '{new_rank_name}' не найдено в системе.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # TODO: Implement PersonnelManager integration for promotion
            # For now, create mock user data
            user_data = {
                'first_name': self.target_user.display_name.split()[0] if self.target_user.display_name.split() else 'Имя',
                'last_name': ' '.join(self.target_user.display_name.split()[1:]) if len(self.target_user.display_name.split()) > 1 else 'Фамилия',
                'static': '00-000',
                'department': 'Не указано',
                'position': 'Не указано',
                'rank': self.current_rank
            }
            
            # Determine action text based on restoration
            action = "Восстановлен в звании" if is_restoration else "Повышен в звании"
            
            # Process the promotion
            success = await self._process_promotion(
                interaction, 
                new_rank_name, 
                action,
                user_data
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Пользователь {self.target_user.mention} {action.lower()}!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 Детали:",
                    value=f"**Старое звание:** {self.current_rank}\n**Новое звание:** {new_rank_name}",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    " Произошла ошибка при обработке повышения.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error("Error in promotion modal: %s", e)
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке запроса.",
                ephemeral=True
            )
    
    async def _process_promotion(self, interaction: discord.Interaction, new_rank: str, action: str, user_data: dict) -> bool:
        """Process the promotion - update roles and add to audit using RoleUtils"""
        try:
            # Use RoleUtils to assign new rank role (this will clear old rank roles automatically)
            rank_assigned = await role_utils.assign_rank_role(
                self.target_user,
                new_rank,
                interaction.user,
                reason=f"Повышение ранга: {self.current_rank} → {new_rank}"
            )

            if not rank_assigned:
                logger.error(f"PROMOTION: Failed to assign rank role %s to {self.target_user}", new_rank)
                return False

            logger.info(f"PROMOTION: Successfully assigned rank role %s to {self.target_user}", new_rank)

            # TODO: Update PersonnelManager database with new rank
            try:
                # For now, assume success
                sheet_update_success = True
                if sheet_update_success:
                    logger.info("PROMOTION: Mock database update for new rank: %s", new_rank)
                else:
                    logger.error(f"PROMOTION: Mock database update failed for user {self.target_user.id}")
            except Exception as e:
                logger.error("PROMOTION: Error updating database: %s", e)
            
            # Add to audit using existing personnel system
            from cogs.personnel_commands import PersonnelCommands
            personnel_cog = interaction.client.get_cog('PersonnelCommands')
            
            if personnel_cog:
                # Get moderator signed name
                moderator_signed_name = await personnel_cog._get_moderator_signed_name(interaction.user.id)
                if not moderator_signed_name:
                    moderator_signed_name = interaction.user.display_name
                
                # Prepare audit data
                full_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                if not full_name:
                    full_name = self.target_user.display_name
                
                audit_data = {
                    'discord_id': self.target_user.id,
                    'user_mention': self.target_user.mention,
                    'full_name': full_name,
                    'static': user_data.get('static', ''),
                    'action': action,
                    'department': user_data.get('department', ''),
                    'position': user_data.get('position', ''),
                    'rank': new_rank,
                    'reason': f"",
                    'moderator_signed_name': moderator_signed_name
                }
                
                # Add to Audit sheet
                try:
                    sheets_success = await personnel_cog._add_to_audit_sheet(audit_data)
                    if sheets_success:
                        logger.info("PROMOTION: Added to Audit sheet successfully")
                    else:
                        logger.error("PROMOTION: Failed to add to Audit sheet")
                except Exception as e:
                    logger.error("PROMOTION: Error adding to Audit sheet: %s", e)
                
                # Send to audit channel
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        await send_audit_message(audit_channel, audit_data, "promotion")
            
            return True
            
        except Exception as e:
            logger.error("Error processing promotion: %s", e)
            return False


class DemotionModal(ui.Modal, title="Разжалование в звании"):
    """Modal for rank demotion"""
    
    def __init__(self, target_user: discord.Member, current_rank: str, previous_rank: str):
        super().__init__()
        self.target_user = target_user
        self.current_rank = current_rank
        
        # Pre-fill with previous rank
        self.new_rank = ui.TextInput(
            label="Новое звание",
            placeholder="Звание для назначения",
            default=previous_rank,
            min_length=3,
            max_length=50,
            required=True
        )
        self.add_item(self.new_rank)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    " У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return
            
            new_rank_name = self.new_rank.value.strip()
            
            # Validate new rank exists
            rank_info = RankHierarchy.get_rank_info(new_rank_name)
            if not rank_info:
                await interaction.response.send_message(
                    f" Звание '{new_rank_name}' не найдено в системе.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # TODO: Implement PersonnelManager integration for demotion
            # For now, create mock user data
            user_data = {
                'first_name': self.target_user.display_name.split()[0] if self.target_user.display_name.split() else 'Имя',
                'last_name': ' '.join(self.target_user.display_name.split()[1:]) if len(self.target_user.display_name.split()) > 1 else 'Фамилия',
                'static': '00-000',
                'department': 'Не указано',
                'position': 'Не указано',
                'rank': self.current_rank
            }
            
            # Process the demotion
            success = await self._process_demotion(
                interaction, 
                new_rank_name,
                user_data
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Пользователь {self.target_user.mention} разжалован!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 Детали:",
                    value=f"**Старое звание:** {self.current_rank}\n**Новое звание:** {new_rank_name}",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    " Произошла ошибка при обработке разжалования.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error("Error in demotion modal: %s", e)
            await interaction.followup.send(
                " Произошла ошибка при обработке запроса.",
                ephemeral=True
            )
    
    async def _process_demotion(self, interaction: discord.Interaction, new_rank: str, user_data: dict) -> bool:
        """Process the demotion - update roles and add to audit using RoleUtils"""
        # Same logic as promotion but with "Понижен в звании" action
        try:
            # Use RoleUtils to assign new rank role (this will clear old rank roles automatically)
            rank_assigned = await role_utils.assign_rank_role(
                self.target_user,
                new_rank,
                interaction.user,
                reason=f"Понижение ранга: {self.current_rank} → {new_rank}"
            )

            if not rank_assigned:
                logger.error(f"DEMOTION: Failed to assign rank role %s to {self.target_user}", new_rank)
                return False

            logger.info(f"DEMOTION: Successfully assigned rank role %s to {self.target_user}", new_rank)

            # TODO: Update PersonnelManager database with new rank
            try:
                # For now, assume success
                sheet_update_success = True
                if sheet_update_success:
                    logger.info("DEMOTION: Mock database update for new rank: %s", new_rank)
                else:
                    logger.error(f"DEMOTION: Mock database update failed for user {self.target_user.id}")
            except Exception as e:
                logger.error("DEMOTION: Error updating database: %s", e)
            
            personnel_cog = interaction.client.get_cog('PersonnelCommands')
            
            if personnel_cog:
                # Get moderator signed name
                moderator_signed_name = await personnel_cog._get_moderator_signed_name(interaction.user.id)
                if not moderator_signed_name:
                    moderator_signed_name = interaction.user.display_name
                
                # Prepare audit data
                full_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                if not full_name:
                    full_name = self.target_user.display_name
                
                audit_data = {
                    'discord_id': self.target_user.id,
                    'user_mention': self.target_user.mention,
                    'full_name': full_name,
                    'static': user_data.get('static', ''),
                    'action': "Разжалован в звании",
                    'department': user_data.get('department', ''),
                    'position': user_data.get('position', ''),
                    'rank': new_rank,
                    'reason': "",
                    'moderator_signed_name': moderator_signed_name
                }
                
                # Add to Audit sheet
                try:
                    sheets_success = await personnel_cog._add_to_audit_sheet(audit_data)
                    if sheets_success:
                        logger.info("DEMOTION: Added to Audit sheet successfully")
                    else:
                        logger.error("DEMOTION: Failed to add to Audit sheet")
                except Exception as e:
                    logger.error("DEMOTION: Error adding to Audit sheet: %s", e)
                
                # Send to audit channel
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        await send_audit_message(audit_channel, audit_data, "demotion")
            
            return True
            
        except Exception as e:
            logger.error("Error processing demotion: %s", e)
            return False


class PositionModal(ui.Modal, title="Назначение/Снятие должности"):
    """Modal for position assignment/removal"""
    
    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user
        
        self.position = ui.TextInput(
            label="Новая должность",
            placeholder="Оставьте пустым для снятия с должности",
            required=False,
            max_length=100
        )
        self.add_item(self.position)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    " У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # TODO: Implement PersonnelManager integration for positions
            # For now, create mock user data
            user_data = {
                'first_name': self.target_user.display_name.split()[0] if self.target_user.display_name.split() else 'Имя',
                'last_name': ' '.join(self.target_user.display_name.split()[1:]) if len(self.target_user.display_name.split()) > 1 else 'Фамилия',
                'static': '00-000',
                'department': 'Не указано',
                'position': 'Не указано',
                'rank': 'Рядовой'
            }
            
            new_position = self.position.value.strip()
            action = "Назначение на должность" if new_position else "Разжалование с должности"
            
            # Process position change
            success = await self._process_position_change(
                interaction,
                new_position,
                action,
                user_data
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Пользователь {self.target_user.mention} {action.lower()}!",
                    color=discord.Color.green()
                )
                if new_position:
                    embed.add_field(
                        name="📋 Детали:",
                        value=f"**Новая должность:** {new_position}",
                        inline=False
                    )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    " Произошла ошибка при обработке назначения.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error("Error in position modal: %s", e)
            await interaction.followup.send(
                " Произошла ошибка при обработке запроса.",
                ephemeral=True
            )
    
    async def _process_position_change(self, interaction: discord.Interaction, new_position: str, action: str, user_data: dict) -> bool:
        """Process position change - update Personal List sheet and add audit record"""
        try:
            # Update Personal List sheet with new position
            try:
                # Update user data with new position
                user_data_updated = user_data.copy()
                user_data_updated['position'] = new_position
                
                # TODO: Update PersonnelManager database with new position
                success = True  # For now, assume success
                
                if not success:
                    logger.error(f"Failed to update Personal List sheet for user {self.target_user.id}")
                    return False
                    
            except Exception as e:
                logger.error("Error updating Personal List sheet: %s", e)
                return False
            
            # Add to audit using existing personnel system  
            from cogs.personnel_commands import PersonnelCommands
            personnel_cog = interaction.client.get_cog('PersonnelCommands')
            
            if personnel_cog:
                # Get moderator signed name
                moderator_signed_name = await personnel_cog._get_moderator_signed_name(interaction.user.id)
                if not moderator_signed_name:
                    moderator_signed_name = interaction.user.display_name
                
                # Get current rank
                current_rank = RankHierarchy.get_user_current_rank(self.target_user) or user_data.get('rank', 'Рядовой')
                
                # Prepare audit data
                full_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                if not full_name:
                    full_name = self.target_user.display_name
                
                audit_data = {
                    'discord_id': self.target_user.id,
                    'user_mention': self.target_user.mention,
                    'full_name': full_name,
                    'static': user_data.get('static', ''),
                    'action': action,
                    'department': user_data.get('department', ''),
                    'position': new_position,
                    'rank': current_rank,
                    'moderator_signed_name': moderator_signed_name
                }
                
                # Add to sheets and audit channel
                try:
                    sheets_success = await personnel_cog._add_to_audit_sheet(audit_data)
                    if sheets_success:
                        logger.info("POSITION: Added to Audit sheet successfully")
                    else:
                        logger.error("POSITION: Failed to add to Audit sheet")
                except Exception as e:
                    logger.error("POSITION: Error adding to Audit sheet: %s", e)
                
                # Send to audit channel
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        await send_audit_message(audit_channel, audit_data, "position")
            
            return True
            
        except Exception as e:
            logger.error("Error processing position change: %s", e)
            return False


class RecruitmentModal(ui.Modal, title="Принятие на службу"):
    """Modal for recruiting new personnel - Based on proven MilitaryApplicationModal"""
    
    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user
        
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Олег Дубов",
            min_length=2,
            max_length=50,
            required=True
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder="123-456 (допускается 1-6 цифр)",
            min_length=1,
            max_length=7,
            required=True
        )
        self.add_item(self.static_input)
        
        self.rank_input = ui.TextInput(
            label="Звание",
            placeholder="Обычно: Рядовой",
            min_length=1,
            max_length=30,
            required=True,
            default="Рядовой"
        )
        self.add_item(self.rank_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process recruitment submission - adapted from MilitaryApplicationModal"""
        try:
            # Check permissions first
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    " У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return
            
            # Validate and format static
            static = self.static_input.value.strip()
            formatted_static = self._format_static(static)
            if not formatted_static:
                from utils.static_validator import StaticValidator
                await interaction.response.send_message(
                    StaticValidator.get_validation_error_message(),
                    ephemeral=True
                )
                return
            
            # All validation passed, defer for processing
            await interaction.response.defer(ephemeral=True)
            
            # Process recruitment directly using PersonnelManager
            success = await self._process_recruitment_direct(
                interaction,
                self.name_input.value.strip(),
                formatted_static,
                self.rank_input.value.strip()
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Успешно",
                    description=f"Пользователь {self.target_user.mention} принят на службу!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 Детали:",
                    value=(
                        f"**ФИО:** {self.name_input.value.strip()}\n"
                        f"**Статик:** {formatted_static}\n"
                        f"**Звание:** {self.rank_input.value.strip()}"
                    ),
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ Произошла ошибка при обработке принятия на службу.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error("RECRUITMENT ERROR: %s", e)
            import traceback
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при обработке запроса.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        " Произошла ошибка при обработке запроса.",
                        ephemeral=True
                    )
            except:
                logger.error("Failed to send error response: %s", e)
    
    def _format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        from utils.static_validator import StaticValidator
        is_valid, formatted = StaticValidator.validate_and_format(static_input)
        return formatted if is_valid else ""
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    async def _process_recruitment_direct(self, interaction: discord.Interaction, full_name: str, static: str, rank: str) -> bool:
        """Process recruitment using PersonnelManager"""
        try:
            logger.info(f"RECRUITMENT: Starting recruitment via PersonnelManager for {self.target_user.id}")
            logger.info("RECRUITMENT: Data - Name: '%s', Static: '%s', Rank: '%s'", full_name, static, rank)
            
            # Prepare application data for PersonnelManager
            application_data = {
                'user_id': self.target_user.id,
                'username': self.target_user.display_name,
                'name': full_name,
                'static': static,
                'type': 'military',
                'rank': rank,
                'subdivision': 'Военная Академия',
                'position': None,
            }
            
            # Use PersonnelManager for recruitment
            from utils.database_manager import PersonnelManager
            pm = PersonnelManager()
            
            success, message = await pm.process_role_application_approval(
                application_data,
                self.target_user.id,
                interaction.user.id,
                interaction.user.display_name
            )
            
            if success:
                logger.info("RECRUITMENT: PersonnelManager processed successfully: %s", message)
            else:
                logger.error("RECRUITMENT: PersonnelManager failed: %s", message)
            
            return success
            
        except Exception as e:
            logger.error("RECRUITMENT: Error processing recruitment: %s", e)
            import traceback
            traceback.print_exc()
            return False


class PersonalDataModal(ui.Modal, title="Изменить личные данные"):
    """Modal for editing personal data (Discord ID, Name, Surname, Static)"""

    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user

        # Add input fields
        # self.discord_id = ui.TextInput(
        #    label="🆔 Discord ID",
        #    placeholder="ID пользователя в Discord",
        #    default=str(target_user.id),
        #    min_length=15,
        #    max_length=20,
        #    required=True
        #)
        #self.add_item(self.discord_id)

        self.first_name = ui.TextInput(
            label="Имя",
            placeholder="Введите имя",
            min_length=2,
            max_length=50,
            required=True
        )
        self.add_item(self.first_name)

        self.last_name = ui.TextInput(
            label="Фамилия",
            placeholder="Введите фамилию",
            min_length=2,
            max_length=50,
            required=True
        )
        self.add_item(self.last_name)

        self.static = ui.TextInput(
            label="Статик",
            placeholder="123-456 (1-6 цифр)",
            min_length=1,
            max_length=7,
            required=True
        )
        self.add_item(self.static)

        # Auto-fill data from cache
        self._auto_fill_data()

    def _auto_fill_data(self):
        """Auto-fill data from cache, fallback to database"""
        try:
            # Import here to avoid circular imports
            from utils.user_cache import get_cached_user_info_sync, _global_cache
            from utils.database_manager import personnel_manager
            
            # Get user data synchronously from cache first
            user_data = get_cached_user_info_sync(self.target_user.id)
            
            if user_data:
                # Fill first name and last name from full_name
                full_name = user_data.get('full_name', '')
                if full_name:
                    name_parts = full_name.split()
                    if len(name_parts) >= 2:
                        self.first_name.default = name_parts[0]
                        self.last_name.default = ' '.join(name_parts[1:])
                    elif len(name_parts) == 1:
                        self.first_name.default = name_parts[0]
                
                # Fill static
                static = user_data.get('static', '')
                if static:
                    self.static.default = static
                    
                logger.info(f"AUTO-FILL: Данные для {self.target_user.id} успешно загружены из кэша")
            else:
                logger.info(f"AUTO-FILL: Данные для {self.target_user.id} не найдены в кэше")
                
                # Fallback to database query
                try:
                    # Get data from personnel table synchronously
                    db_data = personnel_manager.get_personnel_by_discord_id(self.target_user.id)
                    
                    if db_data:
                        # Transform data to cache format
                        full_name = f"{db_data['first_name']} {db_data['last_name']}".strip()
                        cache_data = {
                            'full_name': full_name,
                            'static': db_data['static'] or '',
                            'discord_id': db_data['discord_id']
                        }
                        
                        # Store in cache for future use
                        _global_cache._store_in_cache(self.target_user.id, cache_data)
                        
                        # Fill form fields
                        if full_name:
                            name_parts = full_name.split()
                            if len(name_parts) >= 2:
                                self.first_name.default = name_parts[0]
                                self.last_name.default = ' '.join(name_parts[1:])
                            elif len(name_parts) == 1:
                                self.first_name.default = name_parts[0]
                        
                        # Fill static
                        static = db_data['static'] or ''
                        if static:
                            self.static.default = static
                            
                        logger.info(f"AUTO-FILL: Данные для {self.target_user.id} загружены из БД и закэшированы")
                    else:
                        logger.info(f"AUTO-FILL: Пользователь {self.target_user.id} не найден в БД или уволен")
                        
                except Exception as db_error:
                    logger.error(f"AUTO-FILL: Ошибка запроса к БД для {self.target_user.id}: %s", db_error)
                
        except Exception as e:
            logger.warning("Warning: Could not auto-fill personal data: %s", e)
            # Continue with empty defaults

    def _format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        from utils.static_validator import StaticValidator
        is_valid, formatted = StaticValidator.validate_and_format(static_input)
        return formatted if is_valid else ""

    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission with database update and history logging"""
        try:
            # Check permissions
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    " У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return

            # Get form data
            # TEMPORARILY DISABLED: Discord ID field (lines 734-742) - using target user ID directly
            discord_id = self.target_user.id  # Temporarily use target user ID since field is disabled
            first_name = self.first_name.value.strip().capitalize()
            last_name = self.last_name.value.strip().capitalize()
            static = self.static.value.strip()

            # TEMPORARILY DISABLED: Discord ID validation - field is disabled, so no ID changes possible
            # Validate Discord ID - check if user exists on server and prevent conflicts
            # if discord_id != self.target_user.id:
            #     # Discord ID was changed, verify the new user exists
            #     new_user = interaction.guild.get_member(discord_id)
            #     if not new_user:
            #         await interaction.response.send_message(
            #             f"❌ Пользователь с Discord ID {discord_id} не найден на сервере.\n"
            #             "Изменение Discord ID возможно только на существующих участников сервера.",
            #             ephemeral=True
            #         )
            #         return
            #
            #     # Check if the new Discord ID already belongs to another active user in database
            #     try:
            #         from utils.postgresql_pool import get_db_cursor
            #         with get_db_cursor() as cursor:
            #             cursor.execute("""
            #                 SELECT id, first_name, last_name FROM personnel
            #                 WHERE discord_id = %s AND is_dismissal = false
            #             """, (discord_id,))
            #             existing_user = cursor.fetchone()
            #
            #             if existing_user:
            #                 await interaction.response.send_message(
            #                     f"❌ **Конфликт данных!**\n\n"
            #                     f"Discord ID `{discord_id}` уже принадлежит активному пользователю:\n"
            #                     f"**{existing_user['first_name']} {existing_user['last_name']}**\n\n"
            #                     f"Изменение Discord ID невозможно, так как это приведет к конфликту данных.\n"
            #                     f"Если нужно исправить ошибку в данных, обратитесь к администратору.",
            #                     ephemeral=True
            #                 )
            #                 return
            #
            #     except Exception as db_error:
            #         print(f" Database error checking Discord ID conflict: {db_error}")
            #         await interaction.response.send_message(
            #             "❌ Ошибка проверки данных в базе данных.",
            #             ephemeral=True
            #         )
            #         return

            # Validate required fields
            if not first_name or not last_name or not static:
                await interaction.response.send_message(
                    "❌ Все поля обязательны для заполнения: имя, фамилия и статик.",
                    ephemeral=True
                )
                return

            # Validate and format static (required field)
            formatted_static = self._format_static(static)
            if not formatted_static:
                from utils.static_validator import StaticValidator
                await interaction.response.send_message(
                    StaticValidator.get_validation_error_message(),
                    ephemeral=True
                )
                return

            # Defer response for processing
            await interaction.response.defer(ephemeral=True)

            # Get old data for audit notification
            old_data = None
            try:
                from utils.database_manager import personnel_manager
                old_data = personnel_manager.get_personnel_by_discord_id(discord_id)
            except Exception as e:
                logger.info("Could not get old data for audit: %s", e)

            try:
                # Update personnel data with history logging
                from utils.database_manager import personnel_manager

                success, message = await personnel_manager.update_personnel_profile_with_history(
                    discord_id=discord_id,
                    first_name=first_name,
                    last_name=last_name,
                    static=formatted_static,
                    moderator_discord_id=interaction.user.id
                )

                if success:
                    # Invalidate user cache to force refresh
                    from utils.user_cache import invalidate_user_cache
                    invalidate_user_cache(discord_id)

                    # Send audit notification to audit channel
                    try:
                        from utils.audit_logger import audit_logger, AuditAction
                        
                        # Get current personnel data for audit
                        from utils.database_manager import personnel_manager
                        personnel_data = await personnel_manager.get_personnel_data_for_audit(discord_id)
                        
                        if personnel_data:
                            audit_action = await AuditAction.NAME_CHANGE()
                            
                            # Format old and new names with static for reason
                            old_name_with_static = ""
                            if old_data:
                                old_name_with_static = f"{old_data['first_name']} {old_data['last_name']} | {old_data['static']}".strip()
                            
                            new_name_with_static = f"{first_name} {last_name} | {formatted_static}".strip()
                            name_change_reason = f"{old_name_with_static} → {new_name_with_static}" if old_name_with_static else f"→ {new_name_with_static}"
                            
                            audit_data = {
                                'name': f"{personnel_data['first_name']} {personnel_data['last_name']}",
                                'static': personnel_data['static'],
                                'rank': personnel_data.get('rank_name', 'Не указано'),
                                'department': personnel_data.get('subdivision_name', 'Не указано'),
                                'position': personnel_data.get('position_name', 'Не назначено'),
                                'reason': name_change_reason
                            }
                            
                            await audit_logger.send_personnel_audit(
                                guild=interaction.guild,
                                action=audit_action,
                                target_user=self.target_user,
                                moderator=interaction.user,
                                personnel_data=audit_data
                            )
                            
                            logger.info("Audit notification sent for name change: %s %s", first_name, last_name)
                        else:
                            logger.info("Could not get personnel data for audit notification")
                            
                    except Exception as audit_error:
                        logger.error("Error sending audit notification: %s", audit_error)
                        import traceback
                        traceback.print_exc()

                    # Send success message
                    embed = discord.Embed(
                        title="✅ Личные данные обновлены",
                        description=f"Личные данные пользователя {self.target_user.mention} успешно изменены.",
                        color=discord.Color.green()
                    )

                    embed.add_field(
                        name="📋 Новые данные:",
                        value=(
                            f"**Discord ID:** {discord_id}\n"
                            f"**Имя:** {first_name}\n"
                            f"**Фамилия:** {last_name}\n"
                            f"**Статик:** {formatted_static}"
                        ),
                        inline=False
                    )

                    embed.add_field(
                        name="👮 Изменено модератором:",
                        value=interaction.user.mention,
                        inline=True
                    )

                    await interaction.followup.send(embed=embed, ephemeral=True)

                    # Log to console
                    logger.info(f"PERSONAL DATA UPDATE: {self.target_user.id} updated by {interaction.user.id}")
                    logger.info(f"New data: %s %s, static: %s", first_name, last_name, formatted_static)

                else:
                    await interaction.followup.send(
                        f"❌ Ошибка при обновлении личных данных: {message}",
                        ephemeral=True
                    )

            except Exception as db_error:
                logger.error("DATABASE ERROR in personal data update: %s", db_error)
                await interaction.followup.send(
                    " Произошла ошибка при сохранении данных в базу данных.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error("Ошибка в модале личных данных: %s", e)
            await interaction.response.send_message(
                " Произошла ошибка при обработке запроса.",
                ephemeral=True
            )


class ChangeDiscordIDModal(ui.Modal, title="Изменение Discord ID"):
    """Модал для смены Discord ID персонала с полной поддержкой аудита"""
    
    def __init__(self, target_user: discord.Member):
        super().__init__()
        self.target_user = target_user
        
        self.new_discord_id_input = ui.TextInput(
            label="Новый Discord ID",
            placeholder=f"Текущий: {target_user.id}",
            min_length=17,
            max_length=20,
            required=True
        )
        self.add_item(self.new_discord_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка формы смены Discord ID"""
        try:
            # Проверка прав доступа
            config = load_config()
            if not is_administrator(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return
            
            # Парсинг нового Discord ID
            try:
                new_discord_id = int(self.new_discord_id_input.value.strip())
            except ValueError:
                await interaction.response.send_message(
                    "❌ **Ошибка:** Discord ID должен быть числом из 17-20 цифр.",
                    ephemeral=True
                )
                return
            
            # Проверка что новый ID не совпадает со старым
            if new_discord_id == self.target_user.id:
                await interaction.response.send_message(
                    "❌ **Ошибка:** Новый Discord ID совпадает с текущим.",
                    ephemeral=True
                )
                return
            
            # Откладываем ответ для обработки
            await interaction.response.defer(ephemeral=True)
            
            # Обработка смены Discord ID через сервис
            success, message, details = await self._process_discord_id_change(
                interaction,
                self.target_user.id,
                new_discord_id
            )
            
            await interaction.followup.send(message, ephemeral=True)
                
        except Exception as e:
            logger.error("ОШИБКА_СМЕНА_DISCORD_ID: %s", e)
            import traceback
            traceback.print_exc()
            try:
                await interaction.followup.send(
                    f"❌ **Критическая ошибка:** {str(e)}",
                    ephemeral=True
                )
            except:
                pass
    
    async def _process_discord_id_change(
        self,
        interaction: discord.Interaction,
        old_discord_id: int,
        new_discord_id: int
    ) -> tuple[bool, str, dict]:
        """
        Обработка смены Discord ID с полной поддержкой транзакций и аудита
        
        Args:
            interaction: Discord взаимодействие
            old_discord_id: Старый Discord ID
            new_discord_id: Новый Discord ID
            
        Returns:
            tuple[bool, str, dict]: (успех, сообщение, детали)
        """
        from utils.postgresql_pool import get_db_cursor
        from datetime import datetime, timezone
        from utils.user_cache import invalidate_user_cache
        from utils.audit_logger import audit_logger, AuditAction
        import json
        
        details = {
            'roles_copied': 0,
            'roles_failed_copy': 0,
            'roles_removed': 0,
            'roles_failed_remove': 0,
            'failed_roles': [],
            'new_member_found': False,
            'old_member_found': False
        }
        
        try:
            logger.info(f"СМЕНА_DISCORD_ID: Начало смены {old_discord_id} → {new_discord_id}")
            
            # Проверка наличия нового члена на сервере
            new_member = interaction.guild.get_member(new_discord_id)
            new_member_exists = new_member is not None
            
            if not new_member_exists:
                logger.warning(f"СМЕНА_DISCORD_ID: Новый Discord ID {new_discord_id} не найден на сервере")
            
            with get_db_cursor() as cursor:
                try:
                    # Шаг 1: Проверка UNIQUE constraint
                    cursor.execute(
                        "SELECT id, first_name, last_name, static FROM personnel WHERE discord_id = %s",
                        (new_discord_id,)
                    )
                    
                    existing_record = cursor.fetchone()
                    if existing_record:
                        logger.error(f"СМЕНА_DISCORD_ID: Discord ID {new_discord_id} уже используется")

                        first_name = existing_record.get('first_name') if isinstance(existing_record, dict) else existing_record[1]
                        last_name = existing_record.get('last_name') if isinstance(existing_record, dict) else existing_record[2]
                        static_val = existing_record.get('static') if isinstance(existing_record, dict) else existing_record[3]

                        return (False, f"❌ **Ошибка:** Discord ID `{new_discord_id}` уже используется другим пользователем:\n\n"
                                f"**Имя:** {first_name} {last_name}\n"
                                f"**Статик:** {static_val}", details)
                    
                    # Шаг 2: Получить старую запись персонала
                    cursor.execute(
                        "SELECT id, first_name, last_name, static FROM personnel WHERE discord_id = %s",
                        (old_discord_id,)
                    )
                    
                    old_personnel = cursor.fetchone()
                    if not old_personnel:
                        logger.error(f"СМЕНА_DISCORD_ID: Запись персонала для {old_discord_id} не найдена")
                        return (False, "❌ **Ошибка:** Запись пользователя не найдена в базе данных.", details)

                    if isinstance(old_personnel, dict):
                        personnel_id = old_personnel.get('id')
                        old_first = old_personnel.get('first_name')
                        old_last = old_personnel.get('last_name')
                        static_id = old_personnel.get('static')
                    else:
                        personnel_id = old_personnel[0]
                        old_first = old_personnel[1]
                        old_last = old_personnel[2]
                        static_id = old_personnel[3]

                    old_full_name = f"{old_first} {old_last}".strip()
                    
                    # Шаг 3: Получить Discord члены и их роли
                    old_member = interaction.guild.get_member(old_discord_id)
                    if not old_member:
                        logger.warning(f"СМЕНА_DISCORD_ID: Старый участник {old_discord_id} не найден на сервере")
                        details['old_member_found'] = False
                    else:
                        details['old_member_found'] = True
                    
                    # Шаг 4: Получить все роли
                    old_roles = []
                    if old_member:
                        old_roles = [role for role in old_member.roles if role != interaction.guild.default_role]
                        logger.info(f"СМЕНА_DISCORD_ID: Найдено {len(old_roles)} ролей для копирования")
                    
                    if new_member:
                        details['new_member_found'] = True
                    
                    # Шаг 5: Обновить Discord ID в БД (в транзакции)
                    current_time = datetime.now(timezone.utc)
                    cursor.execute(
                        "UPDATE personnel SET discord_id = %s WHERE id = %s",
                        (new_discord_id, personnel_id)
                    )
                    logger.info(f"СМЕНА_DISCORD_ID: Обновлён discord_id для персонала {personnel_id}")
                    
                    # Шаг 6: Копировать роли на новый аккаунт
                    if new_member and old_roles:
                        for role in old_roles:
                            try:
                                await new_member.add_roles(role)
                                details['roles_copied'] += 1
                                logger.info(f"СМЕНА_DISCORD_ID: Скопирована роль {role.name} на {new_discord_id}")
                            except discord.Forbidden:
                                details['roles_failed_copy'] += 1
                                details['failed_roles'].append(role.name)
                                logger.warning(f"СМЕНА_DISCORD_ID: Нет прав для копирования роли {role.name}")
                            except Exception as e:
                                details['roles_failed_copy'] += 1
                                details['failed_roles'].append(role.name)
                                logger.error(f"СМЕНА_DISCORD_ID: Ошибка при копировании роли {role.name}: {e}")
                    
                    # Шаг 7: Удалить роли со старого аккаунта
                    if old_member and old_roles:
                        for role in old_roles:
                            try:
                                await old_member.remove_roles(role)
                                details['roles_removed'] += 1
                                logger.info(f"СМЕНА_DISCORD_ID: Удалена роль {role.name} со старого аккаунта")
                            except discord.Forbidden:
                                details['roles_failed_remove'] += 1
                                logger.warning(f"СМЕНА_DISCORD_ID: Нет прав для удаления роли {role.name}")
                            except Exception as e:
                                details['roles_failed_remove'] += 1
                                logger.error(f"СМЕНА_DISCORD_ID: Ошибка при удалении роли {role.name}: {e}")
                    
                    # Шаг 8: Создать запись в истории с JSON деталями
                    history_details = {
                        'action_type': 'discord_id_change',
                        'old_discord_id': old_discord_id,
                        'new_discord_id': new_discord_id,
                        'roles_copied': details['roles_copied'],
                        'roles_failed_copy': details['roles_failed_copy'],
                        'roles_removed': details['roles_removed'],
                        'roles_failed_remove': details['roles_failed_remove'],
                        'failed_roles': details['failed_roles'],
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }

                    # Получить personnel.id модератора для внешнего ключа performed_by
                    cursor.execute(
                        "SELECT id FROM personnel WHERE discord_id = %s",
                        (interaction.user.id,)
                    )
                    moderator_personnel = cursor.fetchone()
                    moderator_personnel_id = None
                    if moderator_personnel:
                        moderator_personnel_id = moderator_personnel['id'] if isinstance(moderator_personnel, dict) else moderator_personnel[0]

                    cursor.execute(
                        "INSERT INTO history (personnel_id, action_id, performed_by, details, changes, action_date) VALUES (%s, %s, %s, %s, %s, %s)",
                        (
                            personnel_id,
                            9,  # Изменение личных данных
                            moderator_personnel_id,
                            f"{old_discord_id} -> {new_discord_id}",
                            json.dumps(history_details, ensure_ascii=False),
                            current_time
                        )
                    )
                    logger.info(f"СМЕНА_DISCORD_ID: Создана запись в истории для персонала {personnel_id}")
                    
                    # Шаг 9: Инвалидировать кэш
                    try:
                        invalidate_user_cache(old_discord_id)
                        invalidate_user_cache(new_discord_id)
                        logger.info(f"СМЕНА_DISCORD_ID: Кэш инвалидирован для обоих ID")
                    except Exception as cache_error:
                        logger.warning(f"СМЕНА_DISCORD_ID: Ошибка инвалидации кэша: {cache_error}")
                    
                    # Шаг 10: Отправить кадровый аудит
                    try:
                        from utils.database_manager import personnel_manager
                        
                        personnel_data = await personnel_manager.get_personnel_data_for_audit(old_discord_id)
                        
                        if personnel_data:
                            # В БД действие называется "Изменения личных данных"
                            audit_action = await AuditAction.get("Изменения личных данных")
                            
                            old_id_str = f"<@{old_discord_id}>"
                            new_id_str = f"<@{new_discord_id}>"
                            
                            audit_data = {
                                'name': old_full_name,
                                'static': static_id,
                                'rank': personnel_data.get('rank_name', 'Не указано'),
                                'department': personnel_data.get('subdivision_name', 'Не указано'),
                                'reason': f"Смена Discord ID: {old_id_str} → {new_id_str}"
                            }
                            
                            await audit_logger.send_personnel_audit(
                                guild=interaction.guild,
                                action=audit_action,
                                target_user=self.target_user,
                                moderator=interaction.user,
                                personnel_data=audit_data
                            )
                            logger.info(f"СМЕНА_DISCORD_ID: Отправлен кадровый аудит")
                        else:
                            logger.warning(f"СМЕНА_DISCORD_ID: Не удалось получить данные персонала для аудита")
                    except Exception as audit_error:
                        logger.error(f"СМЕНА_DISCORD_ID: Ошибка отправки аудита: {audit_error}")
                    
                    # Шаг 11: Построить сообщение об успехе
                    success_message = (
                        f"✅ **Discord ID успешно изменён!**\n\n"
                        f"**Персонал:** {old_full_name} ({static_id})\n"
                        f"**Старый ID:** {old_discord_id}\n"
                        f"**Новый ID:** {new_discord_id}\n\n"
                        f"**Информация о ролях:**\n"
                        f"• Скопировано ролей: {details['roles_copied']}\n"
                        f"• Ошибок при копировании: {details['roles_failed_copy']}\n"
                        f"• Удалено ролей: {details['roles_removed']}\n"
                        f"• Ошибок при удалении: {details['roles_failed_remove']}"
                    )
                    
                    if details['failed_roles']:
                        success_message += f"\n• Проблемные роли: {', '.join(details['failed_roles'])}"
                    
                    if not details['new_member_found']:
                        success_message += (
                            f"\n\n⚠️ **Внимание:** Новый аккаунт {new_discord_id} не найден на сервере. "
                            f"Пожалуйста, проверьте, что пользователь присоединился к серверу."
                        )
                    
                    logger.info(f"СМЕНА_DISCORD_ID: Успешно завершена для {old_discord_id} → {new_discord_id}")
                    return (True, success_message, details)
                    
                except Exception as e:
                    logger.error(f"СМЕНА_DISCORD_ID: Ошибка транзакции, откат: {e}")
                    import traceback
                    traceback.print_exc()
                    return (False, f"❌ **Критическая ошибка при изменении Discord ID:**\n{str(e)}", details)
                    
        except Exception as e:
            logger.error(f"СМЕНА_DISCORD_ID: Внешняя ошибка: {e}")
            import traceback
            traceback.print_exc()
            return (False, f"❌ **Ошибка:** {str(e)}", details)