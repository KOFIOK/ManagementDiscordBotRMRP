"""
Views for role assignment system
"""

import discord
from discord import ui
from .modals import MilitaryApplicationModal, CivilianApplicationModal, SupplierApplicationModal
from utils.config_manager import load_config


class RoleAssignmentView(ui.View):
    """Main view with buttons for role type selection"""
    
    def __init__(self):
        super().__init__(timeout=None)

    async def _check_existing_supplier_roles(self, interaction):
        """Check if user already has supplier roles"""
        try:
            config = load_config()
            supplier_roles = config.get('supplier_roles', [])
            
            if not supplier_roles:
                # No supplier roles configured, allow application
                return {"has_roles": False, "role_list": ""}
            
            user_roles = [role.id for role in interaction.user.roles]
            user_supplier_roles = []
            
            for role_id in supplier_roles:
                if role_id in user_roles:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        user_supplier_roles.append(f"> • {role.name}")
            
            if user_supplier_roles:
                role_list = "\n".join(user_supplier_roles)
                return {"has_roles": True, "role_list": role_list}
            else:
                return {"has_roles": False, "role_list": ""}
                
        except Exception as e:
            print(f"Error checking existing supplier roles: {e}")
            # On error, allow application to proceed
            return {"has_roles": False, "role_list": ""}

    @discord.ui.button(label="📜 Призыв / Экскурсия", style=discord.ButtonStyle.green, custom_id="role_military")
    async def military_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open military service application form"""
        modal = MilitaryApplicationModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📦 Доступ к поставкам", style=discord.ButtonStyle.primary, custom_id="role_supplier")
    async def supplier_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open supplier application form with role check"""
        # Check if user already has supplier roles
        role_check = await self._check_existing_supplier_roles(interaction)
        if role_check["has_roles"]:
            await interaction.response.send_message(
                f"❌ **У вас уже есть доступ к поставкам**\n"
                f"> - **Ваши роли:**\n{role_check['role_list']}\n\n"
                f"> *Подача дополнительной заявки не требуется.*",
                ephemeral=True
            )
            return
        
        # If no roles, show the application modal
        modal = SupplierApplicationModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👨‍⚕️ Я госслужащий", style=discord.ButtonStyle.secondary, custom_id="role_civilian")
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


class ProcessingApplicationView(ui.View):
    """View to show during application processing"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔄 Обрабатывается...", style=discord.ButtonStyle.secondary, custom_id="status_processing", disabled=True)
    async def processing_status(self, interaction: discord.Interaction, button: discord.ui.Button):
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
