"""
Views for role assignment system
"""

import discord
from discord import ui
from .modals import MilitaryApplicationModal, CivilianApplicationModal


class RoleAssignmentView(ui.View):
    """Main view with buttons for role type selection"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Призыв / Экскурсия", style=discord.ButtonStyle.green, custom_id="role_military")
    async def military_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open military service application form"""
        modal = MilitaryApplicationModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Я госслужащий", style=discord.ButtonStyle.secondary, custom_id="role_civilian")
    async def civilian_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open civilian application form"""
        modal = CivilianApplicationModal()
        await interaction.response.send_modal(modal)


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
