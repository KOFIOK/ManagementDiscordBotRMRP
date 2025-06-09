import discord
from discord import ui
from utils.config_manager import load_config, save_config

class RoleAssignmentView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Я военнослужащий", style=discord.ButtonStyle.green, custom_id="role_military")
    async def military_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open military service application form"""
        modal = MilitaryApplicationModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Я не во фракции ВС РФ", style=discord.ButtonStyle.secondary, custom_id="role_civilian")
    async def civilian_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open civilian application form"""
        modal = CivilianApplicationModal()
        await interaction.response.send_modal(modal)

class MilitaryApplicationModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Заявка на получение роли военнослужащего")
        
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Иван Иванов",
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
            placeholder="экскурсия или призыв",
            min_length=1,
            max_length=20,
            required=True
        )
        self.add_item(self.recruitment_type_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Validate static format
        static = self.static_input.value.strip()
        if not self._validate_static(static):
            await interaction.response.send_message(
                "❌ Неверный формат статика. Используйте формат 123-456 (5-6 цифр).",
                ephemeral=True
            )
            return
        
        # Validate recruitment type
        recruitment_type = self.recruitment_type_input.value.strip().lower()
        if recruitment_type not in ["экскурсия", "призыв"]:
            await interaction.response.send_message(
                "❌ Порядок набора должен быть: 'экскурсия' или 'призыв'.",
                ephemeral=True
            )
            return
        
        # Create application data
        application_data = {
            "type": "military",
            "name": self.name_input.value.strip(),
            "static": static,
            "rank": self.rank_input.value.strip(),
            "recruitment_type": recruitment_type,
            "user_id": interaction.user.id,
            "user_mention": interaction.user.mention
        }
        
        # Send application for moderation
        await self._send_application_for_approval(interaction, application_data)
    
    def _validate_static(self, static):
        """Validate static format (123-456 or 12345)"""
        import re
        # Allow 5-6 digits with optional dash
        pattern = r'^\d{2,3}-?\d{3}$'
        return bool(re.match(pattern, static))
    
    async def _send_application_for_approval(self, interaction, application_data):
        """Send application to moderation channel"""
        try:
            config = load_config()
            moderation_channel_id = config.get('role_assignment_channel')
            
            if not moderation_channel_id:
                await interaction.response.send_message(
                    "❌ Канал модерации не настроен. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            moderation_channel = interaction.guild.get_channel(moderation_channel_id)
            if not moderation_channel:
                await interaction.response.send_message(
                    "❌ Канал модерации не найден. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create application embed
            embed = discord.Embed(
                title="📋 Заявка на получение роли военнослужащего",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="👤 Заявитель", value=application_data["user_mention"], inline=False)
            embed.add_field(name="📝 Имя Фамилия", value=application_data["name"], inline=True)
            embed.add_field(name="🔢 Статик", value=application_data["static"], inline=True)
            embed.add_field(name="🎖️ Звание", value=application_data["rank"], inline=True)
            embed.add_field(name="📋 Порядок набора", value=application_data["recruitment_type"].title(), inline=True)
            
            # Create approval view
            approval_view = RoleApplicationApprovalView(application_data)
            
            # Get ping role for notifications
            ping_role_id = config.get('role_assignment_ping_role')
            ping_content = ""
            if ping_role_id:
                ping_role = moderation_channel.guild.get_role(ping_role_id)
                if ping_role:
                    ping_content = f"{ping_role.mention} Новая заявка на роль!"
            
            # Send to moderation channel
            await moderation_channel.send(content=ping_content, embed=embed, view=approval_view)
            
            await interaction.response.send_message(
                "✅ Ваша заявка отправлена на рассмотрение модераторам. Ожидайте решения.",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error sending military application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отправке заявки. Попробуйте позже.",
                ephemeral=True
            )

class CivilianApplicationModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Заявка на получение роли гражданского")
        
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder="Например: Иван Иванов",
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
        
        self.faction_input = ui.TextInput(
            label="Фракция, звание, должность",
            placeholder="Например: МВД, Старший лейтенант, Следователь",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.faction_input)
        
        self.purpose_input = ui.TextInput(
            label="Цель получения роли",
            placeholder="Например: доступ к поставкам",
            min_length=1,
            max_length=100,
            required=True
        )
        self.add_item(self.purpose_input)
        
        self.proof_input = ui.TextInput(
            label="Доказательства (ссылка)",
            placeholder="Ссылка на доказательства",
            min_length=5,
            max_length=200,
            required=True
        )
        self.add_item(self.proof_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Validate static format
        static = self.static_input.value.strip()
        if not self._validate_static(static):
            await interaction.response.send_message(
                "❌ Неверный формат статика. Используйте формат 123-456 (5-6 цифр).",
                ephemeral=True
            )
            return
        
        # Validate proof URL
        proof = self.proof_input.value.strip()
        if not self._validate_url(proof):
            await interaction.response.send_message(
                "❌ Пожалуйста, укажите корректную ссылку в поле доказательств.",
                ephemeral=True
            )
            return
        
        # Create application data
        application_data = {
            "type": "civilian",
            "name": self.name_input.value.strip(),
            "static": static,
            "faction": self.faction_input.value.strip(),
            "purpose": self.purpose_input.value.strip(),
            "proof": proof,
            "user_id": interaction.user.id,
            "user_mention": interaction.user.mention
        }
        
        # Send application for moderation
        await self._send_application_for_approval(interaction, application_data)
    
    def _validate_static(self, static):
        """Validate static format (123-456 or 12345)"""
        import re
        pattern = r'^\d{2,3}-?\d{3}$'
        return bool(re.match(pattern, static))
    
    def _validate_url(self, url):
        """Basic URL validation"""
        import re
        url_pattern = r'https?://[^\s/$.?#].[^\s]*'
        return bool(re.match(url_pattern, url))
    
    async def _send_application_for_approval(self, interaction, application_data):
        """Send application to moderation channel"""
        try:
            config = load_config()
            moderation_channel_id = config.get('role_assignment_channel')
            
            if not moderation_channel_id:
                await interaction.response.send_message(
                    "❌ Канал модерации не настроен. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            moderation_channel = interaction.guild.get_channel(moderation_channel_id)
            if not moderation_channel:
                await interaction.response.send_message(
                    "❌ Канал модерации не найден. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create application embed
            embed = discord.Embed(
                title="📋 Заявка на получение роли гражданского",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="👤 Заявитель", value=application_data["user_mention"], inline=False)
            embed.add_field(name="📝 Имя Фамилия", value=application_data["name"], inline=True)
            embed.add_field(name="🔢 Статик", value=application_data["static"], inline=True)
            embed.add_field(name="🏛️ Фракция, звание, должность", value=application_data["faction"], inline=False)
            embed.add_field(name="🎯 Цель получения роли", value=application_data["purpose"], inline=False)
            embed.add_field(name="🔗 Доказательства", value=f"[Ссылка]({application_data['proof']})", inline=False)
              # Create approval view
            approval_view = RoleApplicationApprovalView(application_data)
            
            # Get ping role for notifications
            ping_role_id = config.get('role_assignment_ping_role')
            ping_content = ""
            if ping_role_id:
                ping_role = moderation_channel.guild.get_role(ping_role_id)
                if ping_role:
                    ping_content = f"{ping_role.mention} Новая заявка на роль!"
            
            # Send to moderation channel
            await moderation_channel.send(content=ping_content, embed=embed, view=approval_view)
            
            await interaction.response.send_message(
                "✅ Ваша заявка отправлена на рассмотрение модераторам. Ожидайте решения.",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error sending civilian application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при отправке заявки. Попробуйте позже.",
                ephemeral=True
            )

class RoleApplicationApprovalView(ui.View):
    def __init__(self, application_data):
        super().__init__(timeout=None)
        self.application_data = application_data
    
    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.green, custom_id="approve_role_app")
    async def approve_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has moderator permissions
        if not await self._check_moderator_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав для модерации заявок.",
                ephemeral=True
            )
            return
        
        try:
            config = load_config()
            guild = interaction.guild
            user = guild.get_member(self.application_data["user_id"])
            
            if not user:
                await interaction.response.send_message(
                    "❌ Пользователь не найден на сервере.",
                    ephemeral=True
                )
                return
              # Get appropriate role based on application type
            if self.application_data["type"] == "military":
                role_id = config.get('military_role')
                additional_roles_ids = config.get('additional_military_roles', [])
                role_type = "военнослужащего"
                
                # Change nickname for military personnel
                new_nickname = f"ВА | {self.application_data['name']}"
                try:
                    await user.edit(nick=new_nickname, reason="Одобрение заявки на роль военнослужащего")
                except discord.Forbidden:
                    pass  # Bot might not have permission to change this user's nickname
                    
            else:  # civilian
                role_id = config.get('civilian_role')
                additional_roles_ids = []
                role_type = "гражданского"
            
            if not role_id:
                await interaction.response.send_message(
                    f"❌ Роль {role_type} не настроена в конфигурации.",
                    ephemeral=True
                )
                return
            
            role = guild.get_role(role_id)
            if not role:
                await interaction.response.send_message(
                    f"❌ Роль {role_type} не найдена на сервере.",
                    ephemeral=True
                )
                return
            
            # Remove opposite role if exists
            opposite_role_id = config.get('civilian_role' if self.application_data["type"] == "military" else 'military_role')
            if opposite_role_id:
                opposite_role = guild.get_role(opposite_role_id)
                if opposite_role and opposite_role in user.roles:
                    await user.remove_roles(opposite_role, reason=f"Получение роли {role_type}")
            
            # Add primary role
            await user.add_roles(role, reason=f"Одобрение заявки на роль {role_type}")
            
            # Add additional military roles if applicable
            assigned_roles = [role.mention]
            if self.application_data["type"] == "military" and additional_roles_ids:
                for additional_role_id in additional_roles_ids:
                    additional_role = guild.get_role(additional_role_id)
                    if additional_role:
                        try:
                            await user.add_roles(additional_role, reason="Дополнительная роль военнослужащего")
                            assigned_roles.append(additional_role.mention)
                        except discord.Forbidden:
                            print(f"No permission to assign role {additional_role.name} to {user}")
                        except Exception as e:
                            print(f"Error assigning additional role {additional_role.name}: {e}")
            
            # Update embed to show approval
            original_embed = interaction.message.embeds[0]
            original_embed.color = discord.Color.green()
            original_embed.add_field(
                name="✅ Статус",
                value=f"Одобрено модератором {interaction.user.mention}",
                inline=False
            )
            
            # Clear ping role content by editing the message
            ping_role_id = config.get('role_assignment_ping_role')
            if ping_role_id:
                ping_role = guild.get_role(ping_role_id)
                if ping_role and ping_role.mention in interaction.message.content:
                    await interaction.message.edit(content="")
            
            # Create new view with only one button showing
            approved_view = ApprovedApplicationView()
            
            await interaction.response.edit_message(embed=original_embed, view=approved_view)
            
            # Send notification to user
            try:
                roles_text = ", ".join(assigned_roles) if len(assigned_roles) > 1 else assigned_roles[0]
                await user.send(
                    f"✅ Ваша заявка на получение роли {role_type} была одобрена!\n"
                    f"Вы получили {'роли' if len(assigned_roles) > 1 else 'роль'}: {roles_text}"
                )
            except discord.Forbidden:
                pass  # User has DMs disabled
                
        except Exception as e:
            print(f"Error approving role application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при одобрении заявки.",
                ephemeral=True            )

class ApprovedApplicationView(ui.View):
    """View to show after application is approved - shows only archive button"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🗃️ Архивировать", style=discord.ButtonStyle.secondary, custom_id="archive_approved", disabled=True)
    async def archive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This button is disabled and just for visual indication
        pass

class RejectedApplicationView(ui.View):
    """View to show after application is rejected - shows only archive button"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🗃️ Архивировать", style=discord.ButtonStyle.secondary, custom_id="archive_rejected", disabled=True)
    async def archive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This button is disabled and just for visual indication
        pass

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, custom_id="reject_role_app")
    async def reject_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has moderator permissions
        if not await self._check_moderator_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав для модерации заявок.",
                ephemeral=True
            )
            return
        
        modal = RejectionReasonModal(self.application_data)
        await interaction.response.send_modal(modal)
    
    async def _check_moderator_permissions(self, interaction):
        """Check if user has moderator permissions"""
        # Check if user is admin
        if interaction.user.guild_permissions.administrator:
            return True
        
        # Check moderator settings from config
        config = load_config()
        moderators = config.get('moderators', {})
        
        # Check if user is in moderator users list
        if interaction.user.id in moderators.get('users', []):
            return True
        
        # Check if user has any moderator roles
        user_role_ids = [role.id for role in interaction.user.roles]
        moderator_role_ids = moderators.get('roles', [])
        if any(role_id in user_role_ids for role_id in moderator_role_ids):
            return True
        
        return False

class RejectionReasonModal(ui.Modal):
    def __init__(self, application_data):
        super().__init__(title="Причина отклонения заявки")
        self.application_data = application_data
        
        self.reason_input = ui.TextInput(
            label="Причина отклонения",
            placeholder="Укажите причину отклонения заявки...",
            style=discord.TextStyle.paragraph,
            min_length=10,
            max_length=500,
            required=True
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            user = guild.get_member(self.application_data["user_id"])
              # Update embed to show rejection
            original_embed = interaction.message.embeds[0]
            original_embed.color = discord.Color.red()
            original_embed.add_field(
                name="❌ Статус",
                value=f"Отклонено модератором {interaction.user.mention}",
                inline=False
            )
            original_embed.add_field(
                name="📝 Причина отклонения",
                value=self.reason_input.value,
                inline=False
            )
            
            # Clear ping role content by editing the message
            config = load_config()
            guild = interaction.guild
            ping_role_id = config.get('role_assignment_ping_role')
            if ping_role_id:
                ping_role = guild.get_role(ping_role_id)
                if ping_role and ping_role.mention in interaction.message.content:
                    await interaction.message.edit(content="")
            
            # Create new view with only one button showing
            rejected_view = RejectedApplicationView()
            
            await interaction.response.edit_message(embed=original_embed, view=rejected_view)
            
            # Send notification to user
            if user:
                try:
                    role_type = "военнослужащего" if self.application_data["type"] == "military" else "гражданского"
                    await user.send(
                        f"❌ Ваша заявка на получение роли {role_type} была отклонена.\n\n"
                        f"**Причина:** {self.reason_input.value}\n\n"
                        f"Вы можете подать новую заявку, исправив указанные недостатки."
                    )
                except discord.Forbidden:
                    pass  # User has DMs disabled
                    
        except Exception as e:
            print(f"Error rejecting role application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при отклонении заявки.",
                ephemeral=True
            )

# Message with buttons for role assignment
async def send_role_assignment_message(channel):
    """Send role assignment message with buttons, avoiding duplicates."""
    
    # Check if there's already a role assignment message in the channel
    try:
        async for message in channel.history(limit=20):
            if (message.author == channel.guild.me and 
                message.embeds and
                message.embeds[0].title and
                "Получение ролей" in message.embeds[0].title):
                
                # Message already exists, just restore the view
                view = RoleAssignmentView()
                try:
                    await message.edit(view=view)
                    print(f"Updated existing role assignment message {message.id}")
                    return
                except Exception as e:
                    print(f"Error updating existing message: {e}")
                    # If update fails, delete old message and create new one
                    try:
                        await message.delete()
                    except:
                        pass
                    break
    except Exception as e:
        print(f"Error checking for existing messages: {e}")
    
    # Create new message if none exists or old one couldn't be updated
    embed = discord.Embed(
        title="🎖️ Получение ролей",
        description=(
            "Выберите вашу принадлежность к Вооружённым Силам Российской Федерации.\n\n"
            "# ⚠️ ВАЖНО:\nЕсли вы после набора (экскурсии/призыва), то нажимайте на кнопку `\"Я военнослужащий\"`!"
        ),
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🪖 Я военнослужащий", 
        value="Выберите эту опцию, если:\n• Вы прошли набор/призыв\n• Участвуете в экскурсии\n• Являетесь действующим военнослужащим ВС РФ", 
        inline=True
    )
    
    embed.add_field(
        name="👤 Я не во фракции ВС РФ", 
        value="Выберите эту опцию, если:\n• Вы просто наблюдатель\n• Вы поставщик\n• Вы другой гос. служащий", 
        inline=True
    )
    
    embed.add_field(
        name="ℹ️ Инструкция", 
        value="1. Нажмите на соответствующую кнопку\n2. Заполните форму\n3. При необходимости можете изменить выбор, нажав другую кнопку", 
        inline=False
    )
    
    view = RoleAssignmentView()
    await channel.send(embed=embed, view=view)

# Function to restore role assignment views for existing messages
async def restore_role_assignment_views(bot, channel):
    """Restore role assignment views for existing role assignment messages."""
    try:
        async for message in channel.history(limit=50):
            # Check if message is from bot and has role assignment embed
            if (message.author == bot.user and 
                message.embeds and
                message.embeds[0].title and
                "Получение ролей" in message.embeds[0].title):
                
                # Add the view back to the message
                view = RoleAssignmentView()
                try:
                    await message.edit(view=view)
                    print(f"Restored role assignment view for message {message.id}")
                except discord.NotFound:
                    continue
                except Exception as e:
                    print(f"Error restoring view for message {message.id}: {e}")
                    
    except Exception as e:
        print(f"Error restoring role assignment views: {e}")
