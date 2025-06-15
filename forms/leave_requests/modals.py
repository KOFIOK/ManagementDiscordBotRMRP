"""
Modals for leave request system
"""
import discord
from discord import ui
from discord.ext import commands
from utils.moderator_auth import is_moderator, is_administrator
from utils.leave_request_storage import LeaveRequestStorage
from utils.user_database import UserDatabase
from .utils import LeaveRequestValidator, LeaveRequestDepartmentDetector


class LeaveRequestModal(ui.Modal):
    """Modal for submitting leave requests"""
    
    def __init__(self, user_id=None, user_data=None):
        super().__init__(title="🏖️ Заявка на отгул")
        
        # Pre-fill name and static if user data is available
        name_value = ""
        static_value = ""
        name_placeholder = "Например: Олег Дубов"
        static_placeholder = "Например: 123-456"
        
        if user_data:
            name_value = user_data.get('full_name', '')
            static_value = user_data.get('static', '')
            if name_value:
                name_placeholder = f"Данные из реестра: {name_value}"
            if static_value:
                static_placeholder = f"Данные из реестра: {static_value}"
        
        self.name_input = ui.TextInput(
          label="Имя Фамилия",
          placeholder=name_placeholder,
          default=name_value,
          max_length=100,
          required=True
        )
        self.add_item(self.name_input)
        
        self.static_input = ui.TextInput(
          label="Статик",
          placeholder=static_placeholder,
          default=static_value,
          max_length=20,
          required=True
        )
        self.add_item(self.static_input)
        
        self.start_time_input = ui.TextInput(
          label="Время начала отгула (HH:MM)",
          placeholder="Например: 14:00",
          max_length=5,
          required=True
        )
        self.add_item(self.start_time_input)
        
        self.end_time_input = ui.TextInput(
          label="Время конца отгула (HH:MM)",
          placeholder="Например: 15:00",
          max_length=5,
          required=True
        )
        self.add_item(self.end_time_input)
        
        self.reason_input = ui.TextInput(
          label="Причина взятия отгула",
          placeholder="Укажите IC причину, не пишите OOC информацию (\"в целях выполнения БП\" писать не стоит)",
          style=discord.TextStyle.paragraph,
          max_length=500,
          required=True
        )
        self.add_item(self.reason_input)
    
    @classmethod
    async def create_with_user_data(cls, user_id):
        """
        Create LeaveRequestModal with auto-filled user data from database
        
        Args:
            user_id: Discord user ID
            
        Returns:
            LeaveRequestModal: Modal instance with pre-filled data
        """
        try:
            # Try to get user data from personnel database
            user_data = await UserDatabase.get_user_info(user_id)
            return cls(user_id=user_id, user_data=user_data)
        except Exception as e:
            print(f"❌ Error loading user data for modal: {e}")
            # Return modal without pre-filled data if error occurs
            return cls(user_id=user_id, user_data=None)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
          # Get input values
          name = self.name_input.value.strip()
          static_raw = self.static_input.value.strip()
          start_time = self.start_time_input.value.strip()
          end_time = self.end_time_input.value.strip()
          reason = self.reason_input.value.strip()
          
          # Format static
          static = LeaveRequestValidator.format_static(static_raw)
            # Validate request (without daily limit check as it's done in button handler)
          validation = LeaveRequestValidator.validate_request_form_only(start_time, end_time)
          
          if not validation["valid"]:
              embed = discord.Embed(
                  title="❌ Ошибка при подаче заявки",
                  description=validation["error"],
                  color=discord.Color.red(),
                  timestamp=discord.utils.utcnow()
              )
              await interaction.response.send_message(embed=embed, ephemeral=True)
              return
          
          # Detect department
          department = LeaveRequestDepartmentDetector.detect_department(interaction.user.roles)
          
          # Save request
          request_id = LeaveRequestStorage.add_request(
              user_id=interaction.user.id,
              name=name,
              static=static,
              start_time=start_time,
              end_time=end_time,
              reason=reason,
              department=department,
              guild_id=interaction.guild.id
          )
            # Send confirmation to user
          duration_text = f"{validation['duration_minutes']} мин"
          if validation['duration_minutes'] >= 60:
              hours = validation['duration_minutes'] // 60
              minutes = validation['duration_minutes'] % 60
              duration_text = f"{hours} ч" + (f" {minutes} мин" if minutes > 0 else "")
          
          # Send request to channel without user notification
          await interaction.response.defer(ephemeral=True)
          
          # Send request to channel
          await self._send_request_to_channel(interaction, request_id, name, static,
                                            start_time, end_time, reason, department, 
                                            duration_text)
          
        except Exception as e:
          embed = discord.Embed(
              title="❌ Произошла ошибка",
              description=f"Не удалось подать заявку: {str(e)}",
              color=discord.Color.red()
          )
          await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _send_request_to_channel(self, interaction, request_id, name, static, 
                                   start_time, end_time, reason, department, duration_text):
        """Send request message to leave requests channel"""
        from utils.config_manager import load_config
        
        config = load_config()
        channel_id = config.get('leave_requests_channel')
        
        if not channel_id:
          return
        
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
          return
          # Get ping roles based on user's roles
        ping_roles = LeaveRequestDepartmentDetector.get_ping_roles_from_user(
            interaction.user.roles, interaction.guild
        )
        ping_text = " ".join([role.mention for role in ping_roles]) if ping_roles else ""
        
        # Department names
        dept_names = {
          'ва': 'ВА (Военная Академия)',
          'вк': 'ВК (Военный Комиссариат)',
          'увп': 'УВП (Управление Военной Полиции)',
          'ссо': 'ССО (Силы Специальных Операций)',
          'мр': 'МР (Медицинская Рота)',
          'роио': 'РОиО (Рота Охраны и Обеспечения)',
          'unknown': 'Неопределено'
        }
        
        dept_display = dept_names.get(department, department.upper())
        
        embed = discord.Embed(
          title="🏖️ Заявка на отгул",
          color=discord.Color.blue(),
          timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
          name="👤 Заявитель:",
          value=f"{name} ({interaction.user.mention})",
          inline=True
        )
        
        embed.add_field(
          name="🏷️ Статик:",
          value=static,
          inline=True
        )
        
        embed.add_field(
          name="📅 Дата:",
          value=discord.utils.format_dt(discord.utils.utcnow(), 'd'),
          inline=True
        )
        
        embed.add_field(
          name="⏰ Время:",
          value=f"{start_time} - {end_time} ({duration_text})",
          inline=False
        )
        embed.add_field(
          name="📝 Причина:",
          value=reason,
          inline=False
        )
        
        embed.add_field(
          name="🏢 Подразделение:",
          value=dept_display,
          inline=True
        )
        
        embed.add_field(
          name="📢 Статус:",
          value="⏳ Ожидает рассмотрения",
          inline=True
        )
        
        # Create view with approval buttons
        from .views import LeaveRequestApprovalView
        view = LeaveRequestApprovalView(request_id)
        
        # Send message with pings
        content = ping_text if ping_text else None
        await channel.send(content=content, embed=embed, view=view)


class RejectReasonModal(ui.Modal):
    """Modal for entering rejection reason"""
    
    def __init__(self, request_id: str):
        super().__init__(title="❌ Причина отклонения")
        self.request_id = request_id
        
        self.reason_input = ui.TextInput(
          label="Причина отклонения заявки",
          placeholder="Укажите причину отклонения...",
          style=discord.TextStyle.paragraph,
          max_length=500,
          required=True
        )
        self.add_item(self.reason_input)
    
    @classmethod
    async def create_with_user_data(cls, user_id):
        """
        Create LeaveRequestModal with auto-filled user data from database
        
        Args:
            user_id: Discord user ID
            
        Returns:
            LeaveRequestModal: Modal instance with pre-filled data
        """
        try:
            # Try to get user data from personnel database
            user_data = await UserDatabase.get_user_info(user_id)
            return cls(user_id=user_id, user_data=user_data)
        except Exception as e:
            print(f"❌ Error loading user data for modal: {e}")
            # Return modal without pre-filled data if error occurs
            return cls(user_id=user_id, user_data=None)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
          reason = self.reason_input.value.strip()
            # Check permissions
          is_admin = interaction.user.guild_permissions.administrator
          is_mod = await is_moderator(interaction.user.id)
          
          if not (is_admin or is_mod):
              embed = discord.Embed(
                  title="❌ Недостаточно прав",
                  description="У вас нет прав для рассмотрения заявок.",
                  color=discord.Color.red()
              )
              await interaction.response.send_message(embed=embed, ephemeral=True)
              return
          
          # Get request
          request = LeaveRequestStorage.get_request_by_id(self.request_id)
          if not request:
              embed = discord.Embed(
                  title="❌ Заявка не найдена",
                  description="Заявка не существует или уже была обработана.",
                  color=discord.Color.red()
              )
              await interaction.response.send_message(embed=embed, ephemeral=True)
              return
          
          if request["status"] != "pending":
              embed = discord.Embed(
                  title="❌ Заявка уже обработана",
                  description="Эта заявка уже была рассмотрена.",
                  color=discord.Color.red()
              )
              await interaction.response.send_message(embed=embed, ephemeral=True)
              return
            # Check if trying to reject own request (moderators can't, but admins can)
          if (request["user_id"] == interaction.user.id and 
              is_mod and not is_admin):
              embed = discord.Embed(
                  title="❌ Нельзя рассматривать свою заявку",
                  description="Модераторы не могут рассматривать собственные заявки.",
                  color=discord.Color.red()
              )
              await interaction.response.send_message(embed=embed, ephemeral=True)
              return
          
          # Update request status
          success = LeaveRequestStorage.update_request_status(
              self.request_id, "rejected", interaction.user.id, 
              str(interaction.user), reason
          )
          
          if success:
              # Update embed
              await self._update_request_embed(interaction, request, reason)
              
              # Send DM to user
              await self._send_dm_notification(interaction, request, reason)
              
              embed = discord.Embed(
                  title="✅ Заявка отклонена",
                  description=f"Заявка пользователя {request['name']} была отклонена.",
                  color=discord.Color.red()
              )
              await interaction.response.send_message(embed=embed, ephemeral=True)
          else:
              embed = discord.Embed(
                  title="❌ Ошибка",
                  description="Не удалось отклонить заявку.",
                  color=discord.Color.red()
              )
              await interaction.response.send_message(embed=embed, ephemeral=True)
              
        except Exception as e:
          embed = discord.Embed(
              title="❌ Произошла ошибка",
              description=f"Ошибка при отклонении заявки: {str(e)}",
              color=discord.Color.red()
          )
          await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _update_request_embed(self, interaction, request, reason):
        """Update the original request embed with rejection info"""
        try:
          # Get updated request
          updated_request = LeaveRequestStorage.get_request_by_id(self.request_id)
          
          # Update embed
          embed = interaction.message.embeds[0]
          
          # Update status field
          for i, field in enumerate(embed.fields):
              if field.name == "📢 Статус:":
                  embed.set_field_at(
                      i, 
                      name="📢 Статус:",
                      value=f"❌ ОТКЛОНЕНА пользователем {interaction.user.mention}\n⏰ {discord.utils.format_dt(discord.utils.utcnow(), 'f')}",
                      inline=True
                  )
                  break
          
          # Add rejection reason field
          embed.add_field(
              name="📝 Причина отклонения:",
              value=reason,
              inline=False
          )
          
          embed.color = discord.Color.red()
          
          # Remove buttons
          await interaction.message.edit(embed=embed, view=None)
          
        except Exception as e:
          print(f"Error updating request embed: {e}")
    
    async def _send_dm_notification(self, interaction, request, reason):
        """Send DM notification to user about rejection"""
        try:
          user = interaction.guild.get_member(request["user_id"])
          if not user:
              return
          
          embed = discord.Embed(
              title="❌ Ваша заявка на отгул была отклонена",
              color=discord.Color.red(),
              timestamp=discord.utils.utcnow()
          )
          
          embed.add_field(
              name="📋 Детали заявки:",
              value=(
                  f"**Время:** {request['start_time']} - {request['end_time']}\n"
                  f"**Дата:** {discord.utils.format_dt(discord.utils.utcnow(), 'd')}\n"
                  f"**Причина отгула:** {request['reason']}"
              ),
              inline=False
          )
          
          embed.add_field(
              name="👤 Отклонил:",
              value=interaction.user.mention,
              inline=True
          )
          
          embed.add_field(
              name="📝 Причина отклонения:",
              value=reason,
              inline=False
          )
          
          embed.add_field(
              name="ℹ️ Информация:",
              value="Вы можете подать новую заявку на отгул в том же дне, так как предыдущая была отклонена.",
              inline=False
          )
          
          await user.send(embed=embed)
          
        except Exception as e:
          print(f"Error sending DM notification: {e}")
