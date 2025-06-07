import discord
from discord import ui
import re
from utils.config_manager import load_config

class PersonnelAuditModal(ui.Modal, title="Кадровый аудит"):
    name = ui.TextInput(
        label="Имя Фамилия сотрудника",
        placeholder="Введите полное имя сотрудника",
        min_length=2,
        max_length=50,
        required=True
    )
    
    position = ui.TextInput(
        label="Должность",
        placeholder="Укажите должность сотрудника",
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
    
    department = ui.TextInput(
        label="Отдел/Подразделение",
        placeholder="Укажите отдел или подразделение",
        min_length=2,
        max_length=50,
        required=True
    )
    
    notes = ui.TextInput(
        label="Примечания",
        placeholder="Дополнительная информация (необязательно)",
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
            
            # Get the channel where audit reports should be sent
            config = load_config()
            channel_id = config.get('audit_channel')
            
            if not channel_id:
                await interaction.response.send_message(
                    "Ошибка: канал для кадрового аудита не настроен. Обратитесь к администратору.", 
                    ephemeral=True
                )
                return
            
            channel = interaction.client.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Ошибка: не удалось найти канал для кадрового аудита. Обратитесь к администратору.",
                    ephemeral=True
                )
                return
            
            # Create an embed for the audit report
            embed = discord.Embed(
                title="Новая запись кадрового аудита",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Имя Фамилия", value=self.name.value, inline=True)
            embed.add_field(name="Должность", value=self.position.value, inline=True)
            embed.add_field(name="Статик", value=self.static.value, inline=True)
            embed.add_field(name="Отдел/Подразделение", value=self.department.value, inline=False)
            
            if self.notes.value:
                embed.add_field(name="Примечания", value=self.notes.value, inline=False)
            
            embed.add_field(name="Статус", value="📋 Зарегистрировано", inline=False)
            
            embed.set_footer(text=f"Добавлено: {interaction.user.name}")
            
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            
            # Send the audit report to the audit channel
            await channel.send(embed=embed)
            
            await interaction.response.send_message(
                "Запись кадрового аудита была успешно добавлена.", 
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Error in audit form submission: {e}")
            await interaction.response.send_message(
                f"Произошла ошибка при отправке записи аудита: {e}", 
                ephemeral=True
            )
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"Audit modal error: {error}")
        await interaction.response.send_message(
            "Произошла ошибка при обработке формы. Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
            ephemeral=True
        )

class PersonnelAuditButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Добавить запись аудита", style=discord.ButtonStyle.primary, custom_id="personnel_audit")
    async def personnel_audit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PersonnelAuditModal())

async def send_audit_button_message(channel):
    embed = discord.Embed(
        title="Кадровый аудит",
        description="Нажмите на кнопку ниже, чтобы добавить запись в кадровый аудит.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Инструкция", 
        value="1. Нажмите на кнопку\n2. Заполните открывшуюся форму\n3. Нажмите 'Submit'", 
        inline=False
    )
    
    view = PersonnelAuditButton()
    await channel.send(embed=embed, view=view)
