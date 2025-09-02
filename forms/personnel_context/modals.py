"""
Modal forms for personnel context menu operations
"""

import discord
from discord import ui
from typing import Optional, Dict
from datetime import datetime, timezone, timedelta

from .rank_utils import RankHierarchy
from utils.config_manager import load_config, is_moderator_or_admin
from utils.google_sheets import sheets_manager


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
            
            # Get user data from sheets
            user_data = await sheets_manager.get_user_info_from_personal_list(self.target_user.id)
            if not user_data:
                await interaction.followup.send(
                    f"❌ Пользователь {self.target_user.mention} не найден в личном составе.\n"
                    "Только зарегистрированные сотрудники могут быть повышены.",
                    ephemeral=True
                )
                return
            
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
                
                # Add to sheets and audit channel
                sheets_success = await personnel_cog._add_to_audit_sheet(audit_data)
                personnel_success = await personnel_cog._update_personnel_sheet(audit_data)
                
                # Send to audit channel
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        await self._send_audit_message(audit_channel, audit_data)
            
            return True
            
        except Exception as e:
            print(f"Error processing promotion: {e}")
            return False
    
    async def _send_audit_message(self, channel: discord.TextChannel, audit_data: dict):
        """Send audit message to channel"""
        moscow_tz = timezone(timedelta(hours=3))
        current_time = datetime.now(moscow_tz)
        
        embed = discord.Embed(
            title="📊 Кадровый аудит",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        # Format name with static
        name_with_static = audit_data['full_name']
        if audit_data.get('static'):
            name_with_static = f"{audit_data['full_name']} | {audit_data['static']}"
        
        embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
        embed.add_field(name="Действие", value=audit_data['action'], inline=False)
        embed.add_field(name="Причина", value=audit_data.get('reason', ''), inline=False)
        embed.add_field(name="Дата Действия", value=current_time.strftime('%d.%m.%Y'), inline=False)
        embed.add_field(name="Подразделение", value=audit_data.get('department', 'Не указано'), inline=False)
        embed.add_field(name="Воинское звание", value=audit_data['rank'], inline=False)
        embed.add_field(name="Кадровую отписал", value=audit_data['moderator_signed_name'], inline=False)
        
        embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
        
        await channel.send(content=f"<@{audit_data['discord_id']}>", embed=embed)


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
            
            # Get user data from sheets
            user_data = await sheets_manager.get_user_info_from_personal_list(self.target_user.id)
            if not user_data:
                await interaction.followup.send(
                    f"❌ Пользователь {self.target_user.mention} не найден в личном составе.\n"
                    "Только зарегистрированные сотрудники могут быть разжалованы.",
                    ephemeral=True
                )
                return
            
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
                    'action': "Разжалован в звании",
                    'department': user_data.get('department', ''),
                    'position': user_data.get('position', ''),
                    'rank': new_rank,
                    'reason': "",
                    'moderator_signed_name': moderator_signed_name
                }
                
                # Add to sheets and audit channel
                sheets_success = await personnel_cog._add_to_audit_sheet(audit_data)
                personnel_success = await personnel_cog._update_personnel_sheet(audit_data)
                
                # Send to audit channel
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        await self._send_audit_message(audit_channel, audit_data)
            
            return True
            
        except Exception as e:
            print(f"Error processing demotion: {e}")
            return False
    
    async def _send_audit_message(self, channel: discord.TextChannel, audit_data: dict):
        """Send audit message to channel"""
        moscow_tz = timezone(timedelta(hours=3))
        current_time = datetime.now(moscow_tz)
        
        embed = discord.Embed(
            title="📊 Кадровый аудит",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        # Format name with static
        name_with_static = audit_data['full_name']
        if audit_data.get('static'):
            name_with_static = f"{audit_data['full_name']} | {audit_data['static']}"
        
        embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
        embed.add_field(name="Действие", value=audit_data['action'], inline=False)
        embed.add_field(name="Причина", value=audit_data.get('reason', ''), inline=False)
        embed.add_field(name="Дата Действия", value=current_time.strftime('%d.%m.%Y'), inline=False)
        embed.add_field(name="Подразделение", value=audit_data.get('department', 'Не указано'), inline=False)
        embed.add_field(name="Воинское звание", value=audit_data['rank'], inline=False)
        embed.add_field(name="Кадровую отписал", value=audit_data['moderator_signed_name'], inline=False)
        
        embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
        
        await channel.send(content=f"<@{audit_data['discord_id']}>", embed=embed)


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
            
            # Get user data from sheets
            user_data = await sheets_manager.get_user_info_from_personal_list(self.target_user.id)
            if not user_data:
                await interaction.followup.send(
                    f"❌ Пользователь {self.target_user.mention} не найден в личном составе.\n"
                    "Только зарегистрированные сотрудники могут получать должности.",
                    ephemeral=True
                )
                return
            
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
                
                # Update the sheet
                success = await sheets_manager.update_user_position(
                    self.target_user.id, 
                    new_position
                )
                
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
                sheets_success = await personnel_cog._add_to_audit_sheet(audit_data)
                
                # Send to audit channel
                config = load_config()
                audit_channel_id = config.get('audit_channel')
                if audit_channel_id:
                    audit_channel = interaction.guild.get_channel(audit_channel_id)
                    if audit_channel:
                        await self._send_audit_message(audit_channel, audit_data)
            
            return True
            
        except Exception as e:
            print(f"Error processing position change: {e}")
            return False
    
    async def _send_audit_message(self, channel: discord.TextChannel, audit_data: dict):
        """Send audit message to channel"""
        moscow_tz = timezone(timedelta(hours=3))
        current_time = datetime.now(moscow_tz)
        
        embed = discord.Embed(
            title="📊 Кадровый аудит",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Format name with static
        name_with_static = audit_data['full_name']
        if audit_data.get('static'):
            name_with_static = f"{audit_data['full_name']} | {audit_data['static']}"
        
        embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
        embed.add_field(name="Действие", value=audit_data['action'], inline=False)
        # Removed reason field for position changes
        embed.add_field(name="Дата Действия", value=current_time.strftime('%d.%m.%Y'), inline=False)
        embed.add_field(name="Подразделение", value=audit_data.get('department', 'Не указано'), inline=False)
        if audit_data.get('position'):
            embed.add_field(name="Должность", value=audit_data['position'], inline=False)
        embed.add_field(name="Воинское звание", value=audit_data['rank'], inline=False)
        embed.add_field(name="Кадровую отписал", value=audit_data['moderator_signed_name'], inline=False)
        
        embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
        
        await channel.send(content=f"<@{audit_data['discord_id']}>", embed=embed)


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
            
            # Check if user is already in personnel database (do this after defer to avoid timeout)
            personnel_data = await sheets_manager.get_user_info_from_personal_list(self.target_user.id)
            if personnel_data:
                await interaction.followup.send(
                    f"❌ Пользователь {self.target_user.display_name} уже состоит на службе.\n"
                    f"**Текущие данные:**\n"
                    f"• ФИО: {personnel_data.get('first_name', '')} {personnel_data.get('last_name', '')}\n"
                    f"• Статик: {personnel_data.get('static', 'Не указан')}\n"
                    f"• Звание: {personnel_data.get('rank', 'Не указано')}\n"
                    f"• Подразделение: {personnel_data.get('department', 'Не указано')}",
                    ephemeral=True
                )
                return
            
            # Process recruitment directly
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
        """Process recruitment directly - simplified version"""
        try:
            print(f"🔄 RECRUITMENT: Starting direct recruitment for {self.target_user.id}")
            print(f"🔄 RECRUITMENT: Data - Name: '{full_name}', Static: '{static}', Rank: '{rank}', Type: '{recruitment_type}'")
            
            # Split full name into first and last name
            name_parts = full_name.split()
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            print(f"🔄 RECRUITMENT: Name split - First: '{first_name}', Last: '{last_name}'")
            
            # Assign military role
            config = load_config()
            military_roles = config.get('military_roles', [])
            print(f"🔄 RECRUITMENT: Military roles from config: {military_roles}")
            
            if military_roles:
                for role_id in military_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        print(f"🔄 RECRUITMENT: Assigning military role: {role.name}")
                        await self.target_user.add_roles(role, reason=f"Recruitment by {interaction.user}")
                    else:
                        print(f"❌ RECRUITMENT: Military role {role_id} not found")
            
            # Assign rank role
            print(f"🔄 RECRUITMENT: Assigning rank: {rank}")
            try:
                rank_role_id = RankHierarchy.get_rank_role_id(rank)
                print(f"🔄 RECRUITMENT: Rank role ID for '{rank}': {rank_role_id}")
                
                if rank_role_id:
                    rank_role = interaction.guild.get_role(rank_role_id)
                    if rank_role:
                        print(f"🔄 RECRUITMENT: Assigning rank role: {rank_role.name}")
                        await self.target_user.add_roles(rank_role, reason=f"Rank assignment by {interaction.user}")
                    else:
                        print(f"❌ RECRUITMENT: Rank role {rank_role_id} not found in guild")
                else:
                    print(f"❌ RECRUITMENT: No role ID found for rank '{rank}'")
            except Exception as e:
                print(f"❌ RECRUITMENT: Error with rank assignment: {e}")
            
            # Add user to Personal List sheet
            print(f"🔄 RECRUITMENT: Adding user to Personal List sheet...")
            try:
                personal_list_success = await sheets_manager.add_user_to_personal_list(
                    discord_id=self.target_user.id,
                    first_name=first_name,
                    last_name=last_name,
                    static=static,
                    rank=rank,
                    department="Военная Академия - ВА",
                    position=""
                )
                
                if personal_list_success:
                    print(f"✅ RECRUITMENT: Successfully added user to Personal List")
                else:
                    print(f"❌ RECRUITMENT: Failed to add user to Personal List")
                    return False
            except Exception as e:
                print(f"❌ RECRUITMENT: Exception adding to Personal List: {e}")
                return False
            
            # Add to audit using existing personnel system
            print(f"🔄 RECRUITMENT: Adding to audit...")
            try:
                from cogs.personnel_commands import PersonnelCommands
                personnel_cog = interaction.client.get_cog('PersonnelCommands')
                
                if personnel_cog:
                    print(f"✅ RECRUITMENT: Found PersonnelCommands cog")
                    
                    # Get moderator signed name
                    moderator_signed_name = await personnel_cog._get_moderator_signed_name(interaction.user.id)
                    if not moderator_signed_name:
                        moderator_signed_name = interaction.user.display_name
                    print(f"🔄 RECRUITMENT: Moderator signed name: {moderator_signed_name}")
                    
                    # Prepare audit data
                    audit_data = {
                        'discord_id': self.target_user.id,
                        'user_mention': self.target_user.mention,
                        'full_name': full_name,
                        'static': static,
                        'action': "Принят на службу",
                        'department': 'Военная Академия - ВА',
                        'position': '',
                        'rank': rank,
                        'reason': f"{recruitment_type}",
                        'moderator_signed_name': moderator_signed_name
                    }
                    print(f"🔄 RECRUITMENT: Prepared audit data")
                    
                    # Add to audit sheet
                    try:
                        sheets_success = await personnel_cog._add_to_audit_sheet(audit_data)
                        print(f"🔄 RECRUITMENT: Audit sheet success: {sheets_success}")
                    except Exception as e:
                        print(f"❌ RECRUITMENT: Error adding to audit sheet: {e}")
                    
                    # Send to audit channel
                    audit_channel_id = config.get('audit_channel')
                    print(f"🔄 RECRUITMENT: Audit channel ID: {audit_channel_id}")
                    
                    if audit_channel_id:
                        audit_channel = interaction.guild.get_channel(audit_channel_id)
                        if audit_channel:
                            print(f"🔄 RECRUITMENT: Sending audit message to channel")
                            await self._send_recruitment_audit_message(audit_channel, audit_data)
                            print(f"✅ RECRUITMENT: Sent audit message")
                        else:
                            print(f"❌ RECRUITMENT: Audit channel {audit_channel_id} not found")
                    else:
                        print(f"❌ RECRUITMENT: No audit channel configured")
                else:
                    print(f"❌ RECRUITMENT: PersonnelCommands cog not found")
            except Exception as e:
                print(f"❌ RECRUITMENT: Error in audit section: {e}")
            
            print(f"✅ RECRUITMENT: Process completed successfully for {self.target_user.id}")
            return True
            
        except Exception as e:
            print(f"❌ RECRUITMENT: Error processing recruitment: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _send_recruitment_audit_message(self, channel: discord.TextChannel, audit_data: dict):
        """Send recruitment audit message to channel"""
        moscow_tz = timezone(timedelta(hours=3))
        current_time = datetime.now(moscow_tz)
        
        embed = discord.Embed(
            title="📊 Кадровый аудит - Принятие на службу",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        # Format name with static
        name_with_static = f"{audit_data['full_name']} | {audit_data['static']}"
        
        embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
        embed.add_field(name="Действие", value=audit_data['action'], inline=False)
        embed.add_field(name="Причина принятия", value=audit_data.get('reason', ''), inline=False)
        embed.add_field(name="Дата Действия", value=current_time.strftime('%d.%m.%Y'), inline=False)
        embed.add_field(name="Подразделение", value=audit_data.get('department', 'Не указано'), inline=False)
        embed.add_field(name="Воинское звание", value=audit_data['rank'], inline=False)
        embed.add_field(name="Кадровую отписал", value=audit_data['moderator_signed_name'], inline=False)
        
        embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
        
        await channel.send(content=f"<@{audit_data['discord_id']}>", embed=embed)

class DismissalModal(ui.Modal, title="Увольнение"):
    """Modal for dismissing personnel"""
    
    def __init__(self, user: discord.Member):
        super().__init__()
        self.user = user
    
    reason = ui.TextInput(
        label="Причина увольнения",
        placeholder="Укажите причину увольнения...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Load config for permission checking
            config = load_config()
            
            # Check moderator permissions
            if not is_moderator_or_admin(interaction.user, config):
                await interaction.followup.send(
                    "❌ У вас нет прав для выполнения этой операции.", 
                    ephemeral=True
                )
                return
            
            # Check if user exists in personnel database
            personnel_data = await sheets_manager.get_user_info_from_personal_list(self.user.id)
            if not personnel_data:
                await interaction.followup.send(
                    f"❌ Пользователь {self.user.display_name} не найден в базе данных персонала.",
                    ephemeral=True
                )
                return
            
            # Process dismissal directly - no approval workflow
            success = await self._process_dismissal_directly(
                interaction, 
                personnel_data, 
                self.reason.value
            )
            
            if success:
                await interaction.followup.send(
                    f"✅ Пользователь {self.user.display_name} успешно уволен.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Произошла ошибка при увольнении.",
                    ephemeral=True
                )
            
        except Exception as e:
            print(f"Error in DismissalModal: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при обработке увольнения.",
                ephemeral=True
            )

    async def _process_dismissal_directly(self, interaction: discord.Interaction, personnel_data: dict, reason: str) -> bool:
        """Process dismissal directly: remove roles, delete from sheet, add audit record"""
        try:
            # Step 1: Remove all roles except @everyone
            try:
                roles_to_remove = [role for role in self.user.roles if role != interaction.guild.default_role]
                if roles_to_remove:
                    await self.user.remove_roles(*roles_to_remove, reason=f"Увольнение: {reason}")
                    print(f"✅ DISMISSAL: Removed {len(roles_to_remove)} roles from user {self.user.id}")
                else:
                    print(f"✅ DISMISSAL: User {self.user.id} has no roles to remove")
            except Exception as e:
                print(f"❌ DISMISSAL: Error removing roles: {e}")
                # Continue with dismissal even if role removal fails
            
            # Step 2: Delete user from 'Личный Состав' sheet
            try:
                delete_success = await sheets_manager.delete_user_from_personal_list(self.user.id)
                if delete_success:
                    print(f"✅ DISMISSAL: Successfully deleted user {self.user.id} from Personal List")
                else:
                    print(f"❌ DISMISSAL: Failed to delete user {self.user.id} from Personal List")
            except Exception as e:
                print(f"❌ DISMISSAL: Error deleting from sheet: {e}")
            
            # Step 3: Add audit record
            try:
                from cogs.personnel_commands import PersonnelCommands
                personnel_cog = interaction.client.get_cog('PersonnelCommands')
                
                if personnel_cog:
                    # Get moderator signed name
                    moderator_signed_name = await personnel_cog._get_moderator_signed_name(interaction.user.id)
                    if not moderator_signed_name:
                        moderator_signed_name = interaction.user.display_name
                    
                    # Prepare audit data
                    full_name = f"{personnel_data.get('first_name', '')} {personnel_data.get('last_name', '')}".strip()
                    if not full_name:
                        full_name = self.user.display_name
                    
                    audit_data = {
                        'discord_id': self.user.id,
                        'user_mention': self.user.mention,
                        'full_name': full_name,
                        'static': personnel_data.get('static', ''),
                        'action': "Уволен со службы",
                        'department': personnel_data.get('department', ''),
                        'position': personnel_data.get('position', ''),
                        'rank': personnel_data.get('rank', ''),
                        'reason': reason,
                        'moderator_signed_name': moderator_signed_name
                    }
                    
                    # Add to audit sheet
                    await personnel_cog._add_to_audit_sheet(audit_data)
                    
                    # Send to audit channel
                    config = load_config()
                    audit_channel_id = config.get('audit_channel')
                    if audit_channel_id:
                        audit_channel = interaction.guild.get_channel(audit_channel_id)
                        if audit_channel:
                            await self._send_dismissal_audit_message(audit_channel, audit_data)
                            
                    print(f"✅ DISMISSAL: Successfully added audit record for user {self.user.id}")
            except Exception as e:
                print(f"❌ DISMISSAL: Error adding audit record: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ DISMISSAL: Error processing dismissal: {e}")
            return False

    async def _send_dismissal_audit_message(self, channel: discord.TextChannel, audit_data: dict):
        """Send dismissal audit message to channel"""
        from datetime import timezone, timedelta
        moscow_tz = timezone(timedelta(hours=3))
        current_time = datetime.now(moscow_tz)
        
        embed = discord.Embed(
            title="� Кадровый аудит - Увольнение",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        # Format name with static
        name_with_static = audit_data['full_name']
        if audit_data.get('static'):
            name_with_static = f"{audit_data['full_name']} | {audit_data['static']}"
        
        embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
        embed.add_field(name="Действие", value=audit_data['action'], inline=False)
        embed.add_field(name="Причина", value=audit_data.get('reason', ''), inline=False)
        embed.add_field(name="Дата Действия", value=current_time.strftime('%d.%m.%Y'), inline=False)
        embed.add_field(name="Подразделение", value=audit_data.get('department', 'Не указано'), inline=False)
        embed.add_field(name="Должность", value=audit_data.get('position', 'Не указана'), inline=False)
        embed.add_field(name="Воинское звание", value=audit_data['rank'], inline=False)
        embed.add_field(name="Кадровую отписал", value=audit_data['moderator_signed_name'], inline=False)
        
        embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
        
        await channel.send(content=f"<@{audit_data['discord_id']}>", embed=embed)

