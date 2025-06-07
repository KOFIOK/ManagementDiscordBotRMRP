import discord
from discord import ui
import re
from utils.config_manager import load_config

class BlacklistModal(ui.Modal, title="Добавить в чёрный список"):
    name = ui.TextInput(
        label="Имя Фамилия",
        placeholder="Введите полное имя",
        min_length=2,
        max_length=50,
        required=True
    )
    
    static = ui.TextInput(
        label="Статик (6 цифр, 123-456)",
        placeholder="Формат: 123-456",
        min_length=7,
        max_length=7,
        required=True
    )
    
    reason = ui.TextInput(
        label="Причина внесения в чёрный список",
        placeholder="Укажите причину...",
        style=discord.TextStyle.paragraph,
        min_length=5,
        max_length=1000,
        required=True
    )
    
    evidence = ui.TextInput(
        label="Доказательства/Ссылки",
        placeholder="Ссылки на доказательства, скриншоты и т.д. (необязательно)",
        style=discord.TextStyle.paragraph,
        min_length=0,
        max_length=500,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate static format
            if not re.match(r'^\d{3}-\d{3}$', self.static.value):
                await interaction.response.send_message(
                    "Ошибка: Статик должен быть в формате 123-456 (3 цифры, тире, 3 цифры).", 
                    ephemeral=True
                )
                return
            
            # Get the channel where blacklist entries should be sent
            config = load_config()
            channel_id = config.get('blacklist_channel')
            
            if not channel_id:
                await interaction.response.send_message(
                    "Ошибка: канал для чёрного списка не настроен. Обратитесь к администратору.", 
                    ephemeral=True
                )
                return
            
            channel = interaction.client.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Ошибка: не удалось найти канал для чёрного списка. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create an embed for the blacklist entry
            embed = discord.Embed(
                title="🚫 Новая запись в чёрном списке",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Имя Фамилия", value=self.name.value, inline=True)
            embed.add_field(name="Статик", value=self.static.value, inline=True)
            embed.add_field(name="Причина", value=self.reason.value, inline=False)
            
            if self.evidence.value:
                embed.add_field(name="Доказательства", value=self.evidence.value, inline=False)
            
            embed.add_field(name="Статус", value="🔴 Активно", inline=False)
            
            embed.set_footer(text=f"Добавлено: {interaction.user.name}")
            
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            
            # Send the blacklist entry to the blacklist channel
            await channel.send(embed=embed)
            
            await interaction.response.send_message(
                "Запись была успешно добавлена в чёрный список.", 
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in blacklist form submission: {e}")
            await interaction.response.send_message(
                f"Произошла ошибка при добавлении записи в чёрный список: {e}", 
                ephemeral=True
            )
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Blacklist modal error: {error}")
        await interaction.response.send_message(
            "Произошла ошибка при обработке формы. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
            ephemeral=True
        )

# Button for adding to blacklist
class BlacklistButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Добавить в чёрный список", style=discord.ButtonStyle.danger, custom_id="add_blacklist")
    async def add_blacklist(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BlacklistModal())

# Message with button for the blacklist channel
async def send_blacklist_button_message(channel):
    embed = discord.Embed(
        title="🚫 Чёрный список",
        description="Нажмите на кнопку ниже, чтобы добавить запись в чёрный список.",
        color=discord.Color.dark_red()
    )
    
    embed.add_field(
        name="Инструкция", 
        value="1. Нажмите на кнопку\n2. Заполните открывшуюся форму\n3. Нажмите 'Submit'", 
        inline=False
    )
    
    embed.add_field(
        name="Внимание", 
        value="⚠️ Добавление в чёрный список требует серьёзных оснований и доказательств.", 
        inline=False
    )
    
    view = BlacklistButton()
    await channel.send(embed=embed, view=view)
