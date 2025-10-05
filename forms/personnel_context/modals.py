"""
Modal forms for personnel context menu operations
"""

import discord
from discord import ui
from datetime import datetime, timezone, timedelta
import re

from .rank_utils import RankHierarchy
from utils.config_manager import load_config, is_moderator_or_admin


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
                    "❌ У вас нет прав для выполнения этой команды.",
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
                    "❌ Произошла ошибка при обработке повышения.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Error in promotion modal: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке запроса.",
                ephemeral=True
            )
    
    async def _process_promotion(self, interaction: discord.Interaction, new_rank: str, action: str, user_data: dict) -> bool:
        """Process the promotion - update roles and add to audit"""
        try:
            # Remove old rank role
            old_rank_role_id = RankHierarchy.get_rank_role_id(self.current_rank)
            if old_rank_role_id:
                old_role = interaction.guild.get_role(old_rank_role_id)
                if old_role and old_role in self.target_user.roles:
                    await self.target_user.remove_roles(old_role, reason=f"Rank promotion by {interaction.user}")
            
            # Add new rank role
            new_rank_role_id = RankHierarchy.get_rank_role_id(new_rank)
            if new_rank_role_id:
                new_role = interaction.guild.get_role(new_rank_role_id)
                if new_role:
                    await self.target_user.add_roles(new_role, reason=f"Rank promotion by {interaction.user}")
            
            # TODO: Update PersonnelManager database with new rank
            try:
                # For now, assume success
                sheet_update_success = True
                if sheet_update_success:
                    print(f"✅ PROMOTION: Mock database update for new rank: {new_rank}")
                else:
                    print(f"❌ PROMOTION: Mock database update failed for user {self.target_user.id}")
            except Exception as e:
                print(f"❌ PROMOTION: Error updating database: {e}")
            
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
                        print(f"✅ PROMOTION: Added to Audit sheet successfully")
                    else:
                        print(f"❌ PROMOTION: Failed to add to Audit sheet")
                except Exception as e:
                    print(f"❌ PROMOTION: Error adding to Audit sheet: {e}")
                
                # Send to audit channel
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        await send_audit_message(audit_channel, audit_data, "promotion")
            
            return True
            
        except Exception as e:
            print(f"Error processing promotion: {e}")
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
                    "❌ У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return
            
            new_rank_name = self.new_rank.value.strip()
            
            # Validate new rank exists
            rank_info = RankHierarchy.get_rank_info(new_rank_name)
            if not rank_info:
                await interaction.response.send_message(
                    f"❌ Звание '{new_rank_name}' не найдено в системе.",
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
                    "❌ Произошла ошибка при обработке разжалования.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Error in demotion modal: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке запроса.",
                ephemeral=True
            )
    
    async def _process_demotion(self, interaction: discord.Interaction, new_rank: str, user_data: dict) -> bool:
        """Process the demotion - update roles and add to audit"""
        # Same logic as promotion but with "Понижен в звании" action
        try:
            # Remove old rank role
            old_rank_role_id = RankHierarchy.get_rank_role_id(self.current_rank)
            if old_rank_role_id:
                old_role = interaction.guild.get_role(old_rank_role_id)
                if old_role and old_role in self.target_user.roles:
                    await self.target_user.remove_roles(old_role, reason=f"Rank demotion by {interaction.user}")
            
            # Add new rank role
            new_rank_role_id = RankHierarchy.get_rank_role_id(new_rank)
            if new_rank_role_id:
                new_role = interaction.guild.get_role(new_rank_role_id)
                if new_role:
                    await self.target_user.add_roles(new_role, reason=f"Rank demotion by {interaction.user}")
            
            # TODO: Update PersonnelManager database with new rank
            try:
                # For now, assume success
                sheet_update_success = True
                if sheet_update_success:
                    print(f"✅ DEMOTION: Mock database update for new rank: {new_rank}")
                else:
                    print(f"❌ DEMOTION: Mock database update failed for user {self.target_user.id}")
            except Exception as e:
                print(f"❌ DEMOTION: Error updating database: {e}")
            
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
                        print(f"✅ DEMOTION: Added to Audit sheet successfully")
                    else:
                        print(f"❌ DEMOTION: Failed to add to Audit sheet")
                except Exception as e:
                    print(f"❌ DEMOTION: Error adding to Audit sheet: {e}")
                
                # Send to audit channel
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        await send_audit_message(audit_channel, audit_data, "demotion")
            
            return True
            
        except Exception as e:
            print(f"Error processing demotion: {e}")
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
                    "❌ У вас нет прав для выполнения этой команды.",
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
                    "❌ Произошла ошибка при обработке назначения.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"Error in position modal: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке запроса.",
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
                    print(f"Failed to update Personal List sheet for user {self.target_user.id}")
                    return False
                    
            except Exception as e:
                print(f"Error updating Personal List sheet: {e}")
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
                        print(f"✅ POSITION: Added to Audit sheet successfully")
                    else:
                        print(f"❌ POSITION: Failed to add to Audit sheet")
                except Exception as e:
                    print(f"❌ POSITION: Error adding to Audit sheet: {e}")
                
                # Send to audit channel
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        await send_audit_message(audit_channel, audit_data, "position")
            
            return True
            
        except Exception as e:
            print(f"Error processing position change: {e}")
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
            placeholder="123-456 (допускается 5-6 цифр)",
            min_length=5,
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
        
        self.recruitment_type_input = ui.TextInput(
            label="Порядок набора",
            placeholder="Экскурсия или Призыв",
            min_length=1,
            max_length=20,
            required=True
        )
        self.add_item(self.recruitment_type_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process recruitment submission - adapted from MilitaryApplicationModal"""
        try:
            # Check permissions first
            config = load_config()
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.response.send_message(
                    "❌ У вас нет прав для выполнения этой команды.",
                    ephemeral=True
                )
                return
            
            # Validate and format static
            static = self.static_input.value.strip()
            formatted_static = self._format_static(static)
            if not formatted_static:
                await interaction.response.send_message(
                    "❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.\n"
                    "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
                    ephemeral=True
                )
                return
            
            # Validate recruitment type
            recruitment_type = self.recruitment_type_input.value.strip().lower()
            if recruitment_type not in ["экскурсия", "призыв"]:
                await interaction.response.send_message(
                    "❌ Порядок набора должен быть: 'Экскурсия' или 'Призыв'.",
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
                self.rank_input.value.strip(),
                recruitment_type
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
                        f"**Звание:** {self.rank_input.value.strip()}\n"
                        f"**Порядок набора:** {recruitment_type}"
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
            print(f"❌ RECRUITMENT ERROR: {e}")
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
                        "❌ Произошла ошибка при обработке запроса.",
                        ephemeral=True
                    )
            except:
                print(f"Failed to send error response: {e}")
    
    def _format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format - copied from MilitaryApplicationModal"""
        import re
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    async def _process_recruitment_direct(self, interaction: discord.Interaction, full_name: str, static: str, rank: str, recruitment_type: str) -> bool:
        """Process recruitment using PersonnelManager"""
        try:
            print(f"🔄 RECRUITMENT: Starting recruitment via PersonnelManager for {self.target_user.id}")
            print(f"🔄 RECRUITMENT: Data - Name: '{full_name}', Static: '{static}', Rank: '{rank}', Type: '{recruitment_type}'")
            
            # Prepare application data for PersonnelManager
            application_data = {
                'user_id': self.target_user.id,
                'username': self.target_user.display_name,
                'name': full_name,
                'static': static,
                'type': 'military',
                'recruitment_type': recruitment_type.lower(),
                'rank': rank,
                'subdivision': 'Военная Академия',
                'position': None,
                'reason': f"Набор: {recruitment_type}"
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
                print(f"✅ RECRUITMENT: PersonnelManager processed successfully: {message}")
            else:
                print(f"❌ RECRUITMENT: PersonnelManager failed: {message}")
            
            return success
            
        except Exception as e:
            print(f"❌ RECRUITMENT: Error processing recruitment: {e}")
            import traceback
            traceback.print_exc()
            return False
