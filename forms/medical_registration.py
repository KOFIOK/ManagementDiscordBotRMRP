"""
Medical Registration Forms for Discord bot
Handles medical appointments and registration forms
"""

import discord
from discord.ui import Button, View, Modal, TextInput
from datetime import datetime, timezone, timedelta
from utils.config_manager import load_config
from utils.user_cache import get_cached_user_info


class BaseMedicalView(View):
    """Base view with common autofill functionality"""
    
    async def get_autofill_data(self, user_id: str) -> str:
        """Get autofill data for user"""
        try:
            user_info = await get_cached_user_info(user_id)
            if user_info and user_info.get('full_name') and user_info.get('static'):
                return f"{user_info['full_name']} | {user_info['static']}"
        except Exception as e:
            print(f"Error getting autofill data: {e}")
        return ""


class MedicalRegistrationView(BaseMedicalView):
    """View with buttons for medical services"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Прохождение ВВК", style=discord.ButtonStyle.primary, custom_id="vvk_button", emoji="🩺")
    async def vvk_button(self, interaction: discord.Interaction, button: Button):
        """ВВК - только для настраиваемой роли"""
        config = load_config()
        allowed_roles = config.get('medical_vvk_allowed_roles', [])
        
        if allowed_roles and not any(role.id in allowed_roles for role in interaction.user.roles):
            embed = discord.Embed(
                title="❌ Недостаточно прав",
                description="Запись на ВВК доступна только определенным ролям.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        autofill_data = await self.get_autofill_data(str(interaction.user.id))
        await interaction.response.send_modal(VVKModal(autofill_data))
    
    @discord.ui.button(label="Обновление документов", style=discord.ButtonStyle.success, custom_id="docs_button", emoji="📄")
    async def docs_button(self, interaction: discord.Interaction, button: Button):
        """Документы - доступно всем"""
        autofill_data = await self.get_autofill_data(str(interaction.user.id))
        await interaction.response.send_modal(DocumentsModal(autofill_data))
    
    @discord.ui.button(label="Приём психолога", style=discord.ButtonStyle.danger, custom_id="psych_button", emoji="🧠")
    async def psych_button(self, interaction: discord.Interaction, button: Button):
        """Психолог - доступно всем"""
        autofill_data = await self.get_autofill_data(str(interaction.user.id))
        await interaction.response.send_modal(PsychologistModal(autofill_data))


class BaseMedicalModal(Modal):
    """Base class for medical modals with common functionality"""
    
    def __init__(self, title: str):
        super().__init__(title=title)
    
    async def send_to_channel(self, interaction: discord.Interaction, embed: discord.Embed):
        """Send medical request to configured channel"""
        try:
            config = load_config()
            channel_id = config.get('medical_registration_channel')
            medic_role_id = config.get('medical_role_id')
            
            if not channel_id:
                embed_error = discord.Embed(
                    title="❌ Ошибка конфигурации",
                    description="Канал записи к врачу не настроен. Обратитесь к администратору.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed_error, ephemeral=True)
                return
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                embed_error = discord.Embed(
                    title="❌ Ошибка",
                    description="Канал записи к врачу не найден. Обратитесь к администратору.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed_error, ephemeral=True)
                return
            
            # Prepare mention text
            mention_text = f"{interaction.user.mention} отправил заявку"
            if medic_role_id:
                role = interaction.guild.get_role(medic_role_id)
                if role:
                    mention_text += f" {role.mention}"
            
            # Send to channel
            await channel.send(content=mention_text, embed=embed)
            
            # Confirm to user
            await interaction.response.send_message("✅ Ваша заявка отправлена!", ephemeral=True)
            
        except Exception as e:
            print(f"Error sending medical request: {e}")
            embed_error = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при отправке заявки. Попробуйте позже или обратитесь к администратору.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed_error, ephemeral=True)


class VVKModal(BaseMedicalModal):
    """Modal for VVK (Military Medical Commission) registration"""
    
    def __init__(self, autofill_data=""):
        super().__init__(title="Запись на ВВК")
        
        self.name = TextInput(
            label="Имя Фамилия | Статик",
            placeholder="Пример: Иван Иванов | 000-000",
            default=autofill_data,
            max_length=100,
            required=True
        )
        self.time = TextInput(
            label="Удобное время",
            placeholder="Примеры: 18:00, после поверки, в любое удобное время",
            max_length=200,
            required=True
        )
        
        self.add_item(self.name)
        self.add_item(self.time)

    async def on_submit(self, interaction: discord.Interaction):
        # Moscow timezone
        moscow_tz = timezone(timedelta(hours=3))
        now = datetime.now(moscow_tz)
        
        embed = discord.Embed(
            title="🩺 Новая заявка на ВВК",
            description="Запись на прохождение Военно-врачебной комиссии",
            color=discord.Color.blue(),
            timestamp=now
        )
        
        embed.add_field(name="👤 Заявитель", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Имя и статик", value=self.name.value, inline=True)
        embed.add_field(name="⏰ Удобное время", value=self.time.value, inline=False)
        
        embed.set_footer(
            text=f"Заявка отправлена • {now.strftime('%d.%m.%Y %H:%M:%S')} МСК",
            icon_url=interaction.user.display_avatar.url
        )
        
        await self.send_to_channel(interaction, embed)

class DocumentsModal(BaseMedicalModal):
    """Modal for medical documents update"""
    def __init__(self, autofill_data=""):
        super().__init__(title="Обновление документов")
        
        self.name = TextInput(
            label="Имя Фамилия | Статик",
            placeholder="Пример: Иван Иванов | 000-000",
            default=autofill_data,
            max_length=100,
            required=True
        )
        self.docs = TextInput(
            label="Какие документы нужно обновить?",
            placeholder="Пример: Военный билет, справка о состоянии здоровья",
            style=discord.TextStyle.long,
            max_length=500,
            required=True
        )
        self.time = TextInput(
            label="Удобное время",
            placeholder="Примеры: 18:00, после поверки, в любое удобное время",
            max_length=200,
            required=True
        )
        
        self.add_item(self.name)
        self.add_item(self.docs)
        self.add_item(self.time)

    async def on_submit(self, interaction: discord.Interaction):
        # Moscow timezone
        moscow_tz = timezone(timedelta(hours=3))
        now = datetime.now(moscow_tz)
        
        embed = discord.Embed(
            title="📄 Заявка на обновление документов",
            description="Запрос на обновление медицинской документации",
            color=discord.Color.orange(),
            timestamp=now
        )
        
        embed.add_field(name="👤 Заявитель", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Имя и статик", value=self.name.value, inline=True)
        embed.add_field(name="📋 Документы для обновления", value=self.docs.value, inline=False)
        embed.add_field(name="⏰ Удобное время", value=self.time.value, inline=False)
        
        embed.set_footer(
            text=f"Заявка отправлена • {now.strftime('%d.%m.%Y %H:%M:%S')} МСК",
            icon_url=interaction.user.display_avatar.url
        )
        
        await self.send_to_channel(interaction, embed)


class PsychologistModal(BaseMedicalModal):
    """Modal for psychologist appointment"""
    def __init__(self, autofill_data=""):
        super().__init__(title="Запись к психологу")
        
        self.name = TextInput(
            label="Имя Фамилия | Статик",
            placeholder="Пример: Иван Иванов | 000-000",
            default=autofill_data,
            max_length=100,
            required=True
        )
        self.reason = TextInput(
            label="Причина обращения (подробно)",
            style=discord.TextStyle.long,
            placeholder="Опишите причину обращения максимально подробно",
            max_length=1000,
            required=True
        )
        self.time = TextInput(
            label="Удобное время",
            placeholder="Примеры: 18:00, после поверки, в любое удобное время",
            max_length=200,
            required=True
        )
        
        self.add_item(self.name)
        self.add_item(self.reason)
        self.add_item(self.time)

    async def on_submit(self, interaction: discord.Interaction):
        # Moscow timezone
        moscow_tz = timezone(timedelta(hours=3))
        now = datetime.now(moscow_tz)
        
        embed = discord.Embed(
            title="🧠 Заявка к психологу",
            description="Запись на приём к психологу",
            color=discord.Color.purple(),
            timestamp=now
        )
        
        embed.add_field(name="👤 Заявитель", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Имя и статик", value=self.name.value, inline=True)
        embed.add_field(name="📄 Причина обращения", value=self.reason.value, inline=False)
        embed.add_field(name="⏰ Удобное время", value=self.time.value, inline=False)
        
        embed.set_footer(
            text=f"Заявка отправлена • {now.strftime('%d.%m.%Y %H:%M:%S')} МСК",
            icon_url=interaction.user.display_avatar.url
        )
        
        await self.send_to_channel(interaction, embed)


async def send_medical_registration_message(channel):
    """Send medical registration message with buttons to channel (called from settings)"""
    try:
        print(f"[DEBUG] Attempting to send medical registration message to channel: {channel.name} (ID: {channel.id})")
          # Check if pinned message already exists
        pinned_messages = await channel.pins()
        existing_message = None
        
        print(f"[DEBUG] Found {len(pinned_messages)} pinned messages")
        
        for message in pinned_messages:
            if (message.author == channel.guild.me and 
                message.embeds and 
                len(message.embeds) > 0 and
                "Медицинская рота | Регистратура" in message.embeds[0].title):
                existing_message = message
                print(f"[DEBUG] Found existing medical registration message (ID: {message.id})")
                break
        
        if existing_message:
            print(f"[DEBUG] Medical registration message already exists (ID: {existing_message.id}), skipping creation")
            return  # Message already exists and is pinned
        
        print(f"[DEBUG] Creating new medical registration message")
        
        # Create and send new message
        embed = discord.Embed(
            title="🏥 Медицинская рота | Регистратура",
            description="Выберите тип медицинской услуги для записи:",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="📋 Доступные услуги:",
            value=(
                "**Прохождение ВВК** - Военно-врачебная комиссия\n"
                "**Лекция по медподготовке** - Образовательные мероприятия\n"
                "**Обновление документов** - Медицинская документация\n"
                "**Приём психолога** - Психологическая помощь"
            ),
            inline=False
        )
        
        embed.set_footer(text="Нажмите на кнопку для записи")
        
        view = MedicalRegistrationView()
        message = await channel.send(embed=embed, view=view)
        
        print(f"[DEBUG] Medical registration message sent (ID: {message.id})")
        
        # Pin the message
        try:
            await message.pin()
            print(f"[DEBUG] Medical registration message pinned successfully")
        except Exception as pin_error:
            print(f"[DEBUG] Failed to pin medical registration message: {pin_error}")
            pass  # Ignore pin errors
            
    except Exception as e:
        print(f"Error sending medical registration message: {e}")
        import traceback
        traceback.print_exc()
