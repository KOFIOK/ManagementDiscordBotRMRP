from discord import ui
import discord
import re
from datetime import datetime, timezone
from utils.config_manager import load_config, save_config, is_moderator_or_admin
from utils.google_sheets import sheets_manager

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
            placeholder="Экскурсия или Призыв",
            min_length=1,
            max_length=20,
            required=True
        )
        self.add_item(self.recruitment_type_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Auto-format and validate static
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
          # Create application data
        application_data = {
            "type": "military",
            "name": self.name_input.value.strip(),
            "static": formatted_static,
            "rank": self.rank_input.value.strip(),
            "recruitment_type": recruitment_type,
            "user_id": interaction.user.id,
            "user_mention": interaction.user.mention
        }
          # Send application for moderation
        await self._send_application_for_approval(interaction, application_data)
    
    def _format_static(self, static_input: str) -> str:
        """
        Auto-format static number to standard format (XXX-XXX or XX-XXX).
        Accepts various input formats: 123456, 123 456, 123-456, etc.
        Returns formatted static or empty string if invalid.
        """
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        # Check if we have exactly 5 or 6 digits
        if len(digits_only) == 5:
            # Format as XX-XXX (2-3)
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            # Format as XXX-XXX (3-3)
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            # Invalid length
            return ""
    
    def _validate_static(self, static):
        """Validate static format (123-456 or 12345)"""
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
            
            # Get ping roles for notifications (military applications)
            ping_role_ids = config.get('military_role_assignment_ping_roles', [])
            ping_content = ""
            if ping_role_ids:
                ping_mentions = []
                for ping_role_id in ping_role_ids:
                    ping_role = moderation_channel.guild.get_role(ping_role_id)
                    if ping_role:
                        ping_mentions.append(ping_role.mention)
                if ping_mentions:
                    ping_content = f"-# {' '.join(ping_mentions)}"
            
            # Send to moderation channel
            await moderation_channel.send(content=ping_content, embed=embed, view=approval_view)
            
            await interaction.response.send_message(
                "✅ Ваша заявка отправлена на рассмотрение военнослужащим. Ожидайте решения.",
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
        # Auto-format and validate static
        static = self.static_input.value.strip()
        formatted_static = self._format_static(static)
        if not formatted_static:
            await interaction.response.send_message(
                "❌ Неверный формат статика. Статик должен содержать 5 или 6 цифр.\n"
                "Примеры: 123456, 123-456, 12345, 12-345, 123 456",
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
            "static": formatted_static,
            "faction": self.faction_input.value.strip(),
            "purpose": self.purpose_input.value.strip(),
            "proof": proof,
            "user_id": interaction.user.id,
            "user_mention": interaction.user.mention
        }
        
        # Send application for moderation        await self._send_application_for_approval(interaction, application_data)
    
    def _format_static(self, static_input: str) -> str:
        """
        Auto-format static number to standard format (XXX-XXX or XX-XXX).
        Accepts various input formats: 123456, 123 456, 123-456, etc.
        Returns formatted static or empty string if invalid.
        """
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        # Check if we have exactly 5 or 6 digits
        if len(digits_only) == 5:
            # Format as XX-XXX (2-3)
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            # Format as XXX-XXX (3-3)
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            # Invalid length
            return ""
    
    def _validate_static(self, static):
        """Validate static format (123-456 or 12345)"""
        pattern = r'^\d{2,3}-?\d{3}$'
        return bool(re.match(pattern, static))
    
    def _validate_url(self, url):
        """Basic URL validation"""
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
            
            # Get ping roles for notifications (civilian applications)
            ping_role_ids = config.get('civilian_role_assignment_ping_roles', [])
            ping_content = ""
            if ping_role_ids:
                ping_mentions = []
                for ping_role_id in ping_role_ids:
                    ping_role = moderation_channel.guild.get_role(ping_role_id)
                    if ping_role:
                        ping_mentions.append(ping_role.mention)
                if ping_mentions:
                    ping_content = f"-# {' '.join(ping_mentions)}"
            
            # Send to moderation channel
            await moderation_channel.send(content=ping_content, embed=embed, view=approval_view)
            
            await interaction.response.send_message(
                "✅ Ваша заявка отправлена на рассмотрение военнослужащим. Ожидайте решения.",
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
                # Get appropriate roles based on application type
            if self.application_data["type"] == "military":
                role_ids = config.get('military_roles', [])
                role_type = "военнослужащего"
                
                # Check if this is "Рядовой" rank for automatic processing
                is_private_rank = self.application_data.get("rank", "").lower() == "рядовой"
                
                if is_private_rank:
                    # Change nickname only for automatic processing (Рядовой)
                    new_nickname = f"ВА | {self.application_data['name']}"
                    try:
                        await user.edit(nick=new_nickname, reason="Одобрение заявки на роль военнослужащего")
                    except discord.Forbidden:
                        pass  # Bot might not have permission to change this user's nickname
                        
            else:  # civilian
                role_ids = config.get('civilian_roles', [])
                role_type = "гражданского"
                is_private_rank = True  # Civilians always get automatic processing
            
            # For military non-Рядовой applications, skip role assignment
            assigned_roles = []
            if self.application_data["type"] == "military" and not is_private_rank:
                # Skip role assignment for non-Рядовой ranks
                print(f"Skipping role assignment for military rank: {self.application_data.get('rank', 'Unknown')}")
            else:
                # Remove opposite roles if they exist
                opposite_role_ids = config.get('civilian_roles' if self.application_data["type"] == "military" else 'military_roles', [])
                for opposite_role_id in opposite_role_ids:
                    opposite_role = guild.get_role(opposite_role_id)
                    if opposite_role and opposite_role in user.roles:
                        try:
                            await user.remove_roles(opposite_role, reason=f"Получение роли {role_type}")
                        except discord.Forbidden:
                            print(f"No permission to remove role {opposite_role.name} from {user}")
                        except Exception as e:
                            print(f"Error removing role {opposite_role.name}: {e}")
                
                # Add configured roles if any exist
                if role_ids:
                    # Get roles from guild
                    roles_to_assign = []
                    for role_id in role_ids:
                        role = guild.get_role(role_id)
                        if role:
                            roles_to_assign.append(role)
                        else:
                            print(f"Warning: Role {role_id} not found in guild")
                      # Add all found roles
                    for role in roles_to_assign:
                        try:
                            await user.add_roles(role, reason=f"Одобрение заявки на роль {role_type}")
                            assigned_roles.append(role.mention)
                        except discord.Forbidden:
                            print(f"No permission to assign role {role.name} to {user}")
                        except Exception as e:
                            print(f"Error assigning role {role.name}: {e}")
                else:
                    print(f"Warning: No roles configured for {role_type}")
              # Update embed to show approval
            original_embed = interaction.message.embeds[0]
            original_embed.color = discord.Color.green()
            
            if self.application_data["type"] == "military":
                if is_private_rank:
                    status_message = f"Одобрено инструктором ВК {interaction.user.mention}"
                else:
                    status_message = f"Одобрено инструктором ВК {interaction.user.mention}\n⚠️ Требуется ручная обработка для звания {self.application_data.get('rank', 'Неизвестно')}"
            elif self.application_data["type"] == "civilian":
                status_message = f"Одобрено руководством бригады ( {interaction.user.mention} )"

            if self.application_data["type"] == "military" and not is_private_rank:
                status_message += "\n🔄 Роли и логирование пропущены - требуется ручная обработка"
            elif not role_ids:
                status_message += "\n⚠️ Роли не настроены - выдача ролей пропущена"
            elif self.application_data["type"] != "military" or is_private_rank:
                if not assigned_roles:
                    status_message += "\n⚠️ Роли не найдены на сервере"
            
            original_embed.add_field(
                name="✅ Статус",
                value=status_message,
                inline=False
            )
            
            # Clear ping role content
            await interaction.message.edit(content="")
            
            # Create new view with only archive button
            approved_view = ApprovedApplicationView()
            
            # Respond to interaction first to avoid timeout
            await interaction.response.edit_message(embed=original_embed, view=approved_view)              # Add hiring record to Google Sheets for military applications with rank "Рядовой" (after responding)
            if self.application_data["type"] == "military" and is_private_rank:
                try:
                    hiring_time = datetime.now(timezone.utc)
                    sheets_success = await sheets_manager.add_hiring_record(
                        self.application_data,
                        user,
                        interaction.user,
                        hiring_time
                    )
                    if sheets_success:
                        print(f"✅ Successfully added hiring record for {self.application_data.get('name', 'Unknown')}")
                    else:
                        print(f"⚠️ Failed to add hiring record for {self.application_data.get('name', 'Unknown')}")
                except Exception as e:
                    print(f"❌ Error adding hiring record to Google Sheets: {e}")
            
            # Send notification to audit channel for military applications with rank "Рядовой"
            if self.application_data["type"] == "military" and is_private_rank:
                try:
                    config = load_config()
                    audit_channel_id = config.get('audit_channel')
                    if audit_channel_id:
                        audit_channel = guild.get_channel(audit_channel_id)
                        if audit_channel:
                            # Get approving user info from Google Sheets
                            signed_by_name = interaction.user.display_name  # Default fallback
                            try:
                                # Extract clean name from approving user's nickname
                                approved_by_clean_name = sheets_manager.extract_name_from_nickname(interaction.user.display_name)
                                if approved_by_clean_name:
                                    # Extract surname (last word)
                                    name_parts = approved_by_clean_name.strip().split()
                                    if len(name_parts) >= 2:
                                        surname = name_parts[-1]  # Last word as surname
                                        # Search in 'Пользователи' sheet
                                        full_user_info = await sheets_manager.get_user_info_from_users_sheet(surname)
                                        if full_user_info:
                                            signed_by_name = full_user_info
                                        else:
                                            signed_by_name = approved_by_clean_name
                            except Exception as e:
                                print(f"Error getting approving user info from Google Sheets: {e}")
                            
                            # Create audit notification embed with correct template
                            audit_embed = discord.Embed(
                                title="Кадровый аудит ВС РФ",
                                color=0x055000,  # Green color as in template
                                timestamp=discord.utils.utcnow()
                            )
                            
                            # Format date as dd-MM-yyyy
                            action_date = discord.utils.utcnow().strftime('%d-%m-%Y')
                            
                            # Combine name and static for "Имя Фамилия | Статик" field
                            name_with_static = f"{self.application_data.get('name', 'Неизвестно')} | {self.application_data.get('static', '')}"
                              # Set fields according to template
                            audit_embed.add_field(name="Кадровую отписал", value=signed_by_name, inline=False)
                            audit_embed.add_field(name="Имя Фамилия | 6 цифр статика", value=name_with_static, inline=False)
                            audit_embed.add_field(name="Действие", value="Принят на службу", inline=False)
                            
                            # Add recruitment type if available (right after "Действие")
                            recruitment_type = self.application_data.get("recruitment_type", "")
                            if recruitment_type:
                                audit_embed.add_field(name="Причина принятия", value=recruitment_type.capitalize(), inline=False)
                            
                            audit_embed.add_field(name="Дата Действия", value=action_date, inline=False)
                            audit_embed.add_field(name="Подразделение", value="Военная Академия", inline=False)
                            audit_embed.add_field(name="Воинское звание", value=self.application_data.get("rank", "Рядовой"), inline=False)
                            
                            # Set thumbnail to default image as in template
                            audit_embed.set_thumbnail(url="https://i.imgur.com/07MRSyl.png")
                            
                            # Send notification with user mention (the user who was hired)
                            audit_message = await audit_channel.send(content=f"<@{user.id}>", embed=audit_embed)
                            print(f"Sent audit notification for hiring of {user.display_name}")
                        else:
                            print(f"Audit channel not found: {audit_channel_id}")
                    else:                        print("Audit channel ID not configured")
                except Exception as e:
                    print(f"Error sending audit notification for hiring: {e}")

            try:
                if self.application_data["type"] == "military":
                    # Military instructions for automatic processing (Рядовой)
                    instructions = (
                        "## ✅ **Ваша заявка на получение роли военнослужащего была одобрена!**\n\n"
                        "📋 **Полезная информация:**\n"
                        "> • Канал общения:\n> <#1246126422251278597>\n"
                        "> • Расписание занятий (необходимых для повышения):\n> <#1336337899309895722>\n"
                        "> • Следите за оповещениями обучения:\n> <#1337434149274779738>\n"
                        "> • Ознакомьтесь с сайтом Вооружённых Сил РФ:\n> <#1326022450307137659>\n"
                        "> • Следите за последними приказами:\n> <#1251166871064019015>\n"
                        "> • Уже были в ВС РФ? Попробуйте восстановиться:\n> <#1317830537724952626>\n"
                        "> • Решили, что служба не для вас? Напишите рапорт на увольнение:\n> <#1246119825487564981>"
                    )
                else:
                    # Civilian instructions
                    instructions = (
                        "## ✅ **Ваша заявка на получение роли гражданского была одобрена!**\n\n"
                        "📋 **Полезная информация:**\n> "
                        "> • Канал общения:\n> <#1246125346152251393>\n"
                        "> • Запросить поставку:\n> <#1246119051726553099>\n"
                        "> • Запросить допуск на территорию ВС РФ:\n> <#1246119269784354888>"
                    )
                
                await user.send(instructions)
            except discord.Forbidden:
                pass  # User has DMs disabled
                    
        except Exception as e:
            print(f"Error approving role application: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при одобрении заявки.",
                ephemeral=True
            )
    
    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.red, custom_id="reject_role_app")
    async def reject_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has moderator permissions
        if not await self._check_moderator_permissions(interaction):
            await interaction.response.send_message(
                "❌ У вас нет прав для модерации заявок.",
                ephemeral=True
            )
            return
          # Reject immediately without reason modal
        await self._process_rejection(interaction)
    
    async def _check_moderator_permissions(self, interaction):
        """Check if user has moderator permissions"""
        config = load_config()
        return is_moderator_or_admin(interaction.user, config)

    async def _process_rejection(self, interaction):
        """Process application rejection"""
        try:
            guild = interaction.guild
            user = guild.get_member(self.application_data["user_id"])
              
            # Update embed to show rejection
            original_embed = interaction.message.embeds[0]
            original_embed.color = discord.Color.red()
            original_embed.add_field(
                name="❌ Статус",
                value=f"Отклонено сотрудником {interaction.user.mention}",
                inline=False
            )
            
            # Clear ping role content
            await interaction.message.edit(content="")
            
            # Create new view with rejection status button
            rejected_view = RejectedApplicationView()
            
            await interaction.response.edit_message(embed=original_embed, view=rejected_view)
            
            # Send notification to user
            if user:
                try:
                    role_type = "военнослужащего" if self.application_data["type"] == "military" else "гражданского"
                    await user.send(
                        f"❌ Ваша заявка на получение роли {role_type} была отклонена.\n\n"
                        f"Вы можете подать новую заявку позже."
                    )
                except discord.Forbidden:
                    pass  # User has DMs disabled
                    
        except Exception as e:
            print(f"Error rejecting role application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка при отклонении заявки.",
                ephemeral=True
            )

class ApprovedApplicationView(ui.View):
    """View to show after application is approved"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ Одобрено", style=discord.ButtonStyle.green, custom_id="status_approved", disabled=True)
    async def approved_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This button is disabled and just for visual indication
        pass

class RejectedApplicationView(ui.View):
    """View to show after application is rejected"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="❌ Отказано", style=discord.ButtonStyle.red, custom_id="status_rejected", disabled=True)
    async def rejected_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This button is disabled and just for visual indication
        pass

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

# Function to restore approval views for existing application messages
async def restore_approval_views(bot, channel):
    """Restore approval views for existing application messages."""
    try:
        async for message in channel.history(limit=100):
            # Check if message is from bot and has application embed
            if (message.author == bot.user and 
                message.embeds and
                len(message.embeds) > 0):
                
                embed = message.embeds[0]
                if not embed.title:
                    continue
                    
                # Only restore views for PENDING applications (no status field)
                if ("Заявка на получение роли" in embed.title and 
                    not any(field.name in ["✅ Статус", "❌ Статус"] for field in embed.fields)):
                    
                    # Extract application data from embed
                    try:
                        application_data = {}
                        
                        # Determine type from title
                        if "военнослужащего" in embed.title:
                            application_data["type"] = "military"
                        elif "гражданского" in embed.title:
                            application_data["type"] = "civilian"
                        else:
                            continue
                        
                        # Extract all required fields from embed
                        for field in embed.fields:
                            if field.name == "👤 Заявитель":
                                user_mention = field.value
                                # Extract user ID from mention format <@!123456789> or <@123456789>
                                import re
                                match = re.search(r'<@!?(\d+)>', user_mention)
                                if match:
                                    application_data["user_id"] = int(match.group(1))
                                    application_data["user_mention"] = user_mention
                            elif field.name == "📝 Имя Фамилия":
                                application_data["name"] = field.value
                            elif field.name == "🔢 Статик":
                                application_data["static"] = field.value
                            elif field.name == "🎖️ Звание":
                                application_data["rank"] = field.value
                            elif field.name == "📋 Порядок набора":
                                application_data["recruitment_type"] = field.value.lower()
                            elif field.name == "🏛️ Фракция, звание, должность":
                                application_data["faction"] = field.value
                            elif field.name == "🎯 Цель получения роли":
                                application_data["purpose"] = field.value
                            elif field.name == "🔗 Доказательства":
                                # Extract URL from markdown link [Ссылка](url)
                                import re
                                url_match = re.search(r'\[.*?\]\((.*?)\)', field.value)
                                if url_match:
                                    application_data["proof"] = url_match.group(1)
                                else:
                                    application_data["proof"] = field.value
                        
                        # Verify we have minimum required data
                        if "user_id" in application_data and "name" in application_data and "type" in application_data:
                            # Create and add the approval view
                            view = RoleApplicationApprovalView(application_data)
                            await message.edit(view=view)
                            print(f"Restored approval view for {application_data['type']} application message {message.id}")
                        else:
                            print(f"Missing required data for application message {message.id}: {application_data}")
                        
                    except Exception as e:
                        print(f"Error parsing application data from message {message.id}: {e}")
                        continue
                        
                # For already processed applications, just skip them (don't restore views)
                elif ("Заявка на получение роли" in embed.title and 
                      any(field.name in ["✅ Статус", "❌ Статус"] for field in embed.fields)):
                    continue
                    
    except Exception as e:
        print(f"Error restoring approval views: {e}")