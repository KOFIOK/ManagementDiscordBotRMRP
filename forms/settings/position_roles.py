"""
Simple Position Settings Form
Just add positions and assign Discord roles
"""

import discord
from discord import ui
from utils.database_manager.position_manager import position_manager

class PositionSettingsView(ui.View):
    """Simple position settings view"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @ui.select(
        placeholder="Выберите должность для настройки...",
        min_values=1,
        max_values=1,
        options=[]
    )
    async def position_select(self, interaction: discord.Interaction, select: ui.Select):
        """Handle position selection"""
        position_id = int(select.values[0])
        
        # Get position data
        positions = position_manager.get_all_positions()
        position_data = next((p for p in positions if p['id'] == position_id), None)
        
        if not position_data:
            await interaction.response.send_message("❌ Должность не найдена.", ephemeral=True)
            return
        
        # Show management view
        view = PositionManagementView(position_id, position_data)
        
        current_role = "Не назначена"
        if position_data.get('role_id'):
            role = interaction.guild.get_role(int(position_data['role_id']))
            current_role = role.mention if role else "❌ Роль не найдена"
        
        embed = discord.Embed(
            title=f"⚙️ Настройка: {position_data.get('name')}",
            description=f"**Роль Discord:** {current_role}",
            color=discord.Color.blue()
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @ui.button(label="Добавить должность", style=discord.ButtonStyle.success, emoji="➕")
    async def add_position(self, interaction: discord.Interaction, button: ui.Button):
        """Add new position"""
        modal = AddPositionModal()
        await interaction.response.send_modal(modal)
    
    @ui.button(label="Обновить", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, button: ui.Button):
        """Refresh list"""
        await self.update_position_options(interaction.guild)
        embed = await create_position_settings_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def update_position_options(self, guild: discord.Guild):
        """Update position options"""
        positions = position_manager.get_all_positions()
        options = []
        
        for position in positions:
            name = position.get('name', f'Position {position["id"]}')
            
            # Check role status
            role_status = "❌"
            if position.get('role_id'):
                role = guild.get_role(int(position['role_id']))
                role_status = "✅" if role else "⚠️"
            
            options.append(discord.SelectOption(
                label=name[:95],  # Discord limit
                value=str(position['id']),
                description=f"{role_status} ID: {position['id']}",
                emoji="📋"
            ))
        
        if not options:
            options.append(discord.SelectOption(
                label="Нет должностей",
                value="none",
                description="Добавьте должности",
                emoji="❌"
            ))
        
        self.position_select.options = options[:25]

class PositionManagementView(ui.View):
    """Manage individual position"""
    
    def __init__(self, position_id: int, position_data: dict):
        super().__init__(timeout=300)
        self.position_id = position_id
        self.position_data = position_data
    
    @ui.button(label="Назначить роль", style=discord.ButtonStyle.primary, emoji="🎭")
    async def assign_role(self, interaction: discord.Interaction, button: ui.Button):
        """Assign Discord role"""
        modal = AssignRoleModal(self.position_id, self.position_data)
        await interaction.response.send_modal(modal)
    
    @ui.button(label="Удалить роль", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def remove_role(self, interaction: discord.Interaction, button: ui.Button):
        """Remove Discord role"""
        success, message = position_manager.update_position_role(self.position_id, None)
        
        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"
        
        embed = discord.Embed(
            title=f"{emoji} {'Роль удалена' if success else 'Ошибка'}",
            description=message,
            color=color
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @ui.button(label="Удалить должность", style=discord.ButtonStyle.danger, emoji="❌")
    async def delete_position(self, interaction: discord.Interaction, button: ui.Button):
        """Delete position"""
        modal = DeletePositionModal(self.position_id, self.position_data)
        await interaction.response.send_modal(modal)
    
    @ui.button(label="Назад", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        """Go back"""
        view = PositionSettingsView()
        await view.update_position_options(interaction.guild)
        embed = await create_position_settings_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class AddPositionModal(ui.Modal):
    """Add new position modal"""
    
    def __init__(self):
        super().__init__(title="Добавить должность")
        
        self.role_input = ui.TextInput(
            label="Роль или название должности",
            placeholder="ID роли, @роль или название должности...",
            required=True,
            max_length=200
        )
        
        self.add_item(self.role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle submission"""
        # Extract role info
        role_name, role_id = position_manager.extract_role_name_from_mention(
            self.role_input.value, 
            interaction.guild
        )
        
        if not role_name:
            await interaction.response.send_message("❌ Не удалось определить название.", ephemeral=True)
            return
        
        # Add to database
        success, message = position_manager.add_position_to_database(role_name, role_id)
        
        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"
        
        embed = discord.Embed(
            title=f"{emoji} {'Должность добавлена' if success else 'Ошибка'}",
            description=message,
            color=color
        )
        
        if success and role_id:
            role = interaction.guild.get_role(role_id)
            if role:
                embed.add_field(name="Discord роль", value=role.mention, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AssignRoleModal(ui.Modal):
    """Assign role modal"""
    
    def __init__(self, position_id: int, position_data: dict):
        super().__init__(title=f"Назначить роль: {position_data.get('name')}")
        self.position_id = position_id
        
        self.role_input = ui.TextInput(
            label="Discord роль",
            placeholder="ID роли или @роль...",
            required=True,
            max_length=50
        )
        
        self.add_item(self.role_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle assignment"""
        _, role_id = position_manager.extract_role_name_from_mention(
            self.role_input.value, 
            interaction.guild
        )
        
        if not role_id:
            await interaction.response.send_message("❌ Не удалось определить ID роли.", ephemeral=True)
            return
        
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Роль не найдена на сервере.", ephemeral=True)
            return
        
        success, message = position_manager.update_position_role(self.position_id, role_id)
        
        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"
        
        embed = discord.Embed(
            title=f"{emoji} {'Роль назначена' if success else 'Ошибка'}",
            description=message,
            color=color
        )
        
        if success:
            embed.add_field(name="Роль", value=role.mention, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class DeletePositionModal(ui.Modal):
    """Delete position modal"""
    
    def __init__(self, position_id: int, position_data: dict):
        super().__init__(title=f"Удалить: {position_data.get('name')}")
        self.position_id = position_id
        
        self.confirmation = ui.TextInput(
            label="Подтверждение",
            placeholder="Введите 'УДАЛИТЬ'...",
            required=True,
            max_length=10
        )
        
        self.add_item(self.confirmation)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle deletion"""
        if self.confirmation.value.upper() != "УДАЛИТЬ":
            await interaction.response.send_message("❌ Неверное подтверждение.", ephemeral=True)
            return
        
        success, message = position_manager.remove_position_from_database(self.position_id)
        
        color = discord.Color.green() if success else discord.Color.red()
        emoji = "✅" if success else "❌"
        
        embed = discord.Embed(
            title=f"{emoji} {'Должность удалена' if success else 'Ошибка'}",
            description=message,
            color=color
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def create_position_settings_embed() -> discord.Embed:
    """Create settings embed"""
    positions_count = len(position_manager.get_all_positions())
    
    embed = discord.Embed(
        title="⚙️ Настройки должностей",
        description=(
            "**Простая система должностей:**\n"
            "• Добавляете должность\n"
            "• Назначаете Discord роль\n"
            "• Роль автоматически выдается при назначении на должность\n\n"
            f"**Всего должностей:** {positions_count}\n\n"
            "Выберите должность или добавьте новую."
        ),
        color=discord.Color.blue()
    )
    
    return embed