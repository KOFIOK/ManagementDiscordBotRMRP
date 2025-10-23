"""
Views for role assignment system
"""

import discord
from discord import ui
from .modals import MilitaryApplicationModal, CivilianApplicationModal, SupplierApplicationModal
from utils.config_manager import load_config, can_user_access_module


class RoleAssignmentView(ui.View):
    """Main view with buttons for role type selection"""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    async def _check_existing_supplier_roles(self, interaction):
        """Check if user already has ALL supplier roles"""
        try:
            config = load_config()
            supplier_roles = config.get('supplier_roles', [])
            
            if not supplier_roles:
                # No supplier roles configured, allow application
                return {"has_roles": False, "role_list": ""}
            
            user_roles = [role.id for role in interaction.user.roles]
            user_supplier_roles = []
            missing_supplier_roles = []
            
            # Check each supplier role
            for role_id in supplier_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    if role_id in user_roles:
                        user_supplier_roles.append(f"> • {role.name} ✅")
                    else:
                        missing_supplier_roles.append(f"> • {role.name} ❌")
            
            # User has ALL supplier roles only if missing_supplier_roles is empty
            if not missing_supplier_roles:
                # User has all roles
                role_list = "\n".join(user_supplier_roles)
                return {"has_roles": True, "role_list": role_list}
            else:
                # User is missing some roles, allow application
                return {"has_roles": False, "role_list": ""}
                
        except Exception as e:
            print(f"Error checking existing supplier roles: {e}")
            # On error, allow application to proceed
            return {"has_roles": False, "role_list": ""}

    @discord.ui.button(label="📜 Эта фракция", style=discord.ButtonStyle.green, custom_id="role_military")
    async def military_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open military service application form"""
        # Check if user is already an active employee (CACHE first, then DB)
        from forms.personnel_context.commands_clean import get_user_status
        
        user_status = await get_user_status(interaction.user.id)
        
        if user_status['is_active']:
            # User is already active, show information
            full_name = user_status['full_name'] or interaction.user.display_name
            rank = user_status['rank'] or "Не указано"
            department = user_status['department'] or "Не указано"
            position = user_status['position'] or "Не назначено"
            
            await interaction.response.send_message(
                f"❌ **Вы уже состоите в нашей фракции**\n\n"
                f"📋 **Ваша текущая информация:**\n"
                f"> • **Имя, Фамилия:** `{full_name}`\n"
                f"> • **Звание:** `{rank}`\n"
                f"> • **Подразделение:** `{department}`\n"
                f"> • **Должность:** `{position}`\n\n"
                f"💡 **Если вам нужно изменить данные, используйте:**\n"
                f"• **Общее редактирование** - для изменения личных данных\n"
                f"• **Изменить ранг** - для изменения звания",
                ephemeral=True
            )
            return
        
        # Check if user has active blacklist entry (CACHED - should be fast)
        from utils.database_manager import personnel_manager
        
        blacklist_info = await personnel_manager.check_active_blacklist(interaction.user.id)
        
        if blacklist_info:
            # User is blacklisted, deny application
            start_date_str = blacklist_info['start_date'].strftime('%d.%m.%Y')
            end_date_str = blacklist_info['end_date'].strftime('%d.%m.%Y') if blacklist_info['end_date'] else 'Бессрочно'
            
            await interaction.response.send_message(
                f"❌ **Вам запрещен приём на службу**\n\n"
                f"📋 **Вы находитесь в Чёрном списке ВС РФ**\n"
                f"> **Причина:** {blacklist_info['reason']}\n"
                f"> **Период:** {start_date_str} - {end_date_str}\n\n"
                f"*Обратитесь к руководству бригады для снятия с чёрного списка.*",
                ephemeral=True
            )
            return
        
        # No issues, proceed with application
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
    
    @discord.ui.button(label="👨‍⚕️ Другая фракция", style=discord.ButtonStyle.secondary, custom_id="role_civilian")
    async def civilian_application(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open civilian application form"""
        modal = CivilianApplicationModal()
        await interaction.response.send_modal(modal)

class ApprovedApplicationView(ui.View):
    """View to show after application is approved"""
    
    def __init__(self, application_data: dict = None):
        super().__init__(timeout=None)
        self.application_data = application_data or {}

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
    
    def __init__(self, application_data: dict = None):
        super().__init__(timeout=None)
        self.application_data = application_data or {}

    @discord.ui.button(label="❌ Отказано", style=discord.ButtonStyle.red, custom_id="status_rejected", disabled=True)
    async def rejected_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This button is disabled and just for visual indication
        pass
