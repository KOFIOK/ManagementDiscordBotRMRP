"""
Automatic dismissal system
Handles creation of automatic dismissal reports when members leave the server
"""

import discord
from utils.config_manager import load_config
from utils.user_cache import get_cached_user_info
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


async def create_automatic_dismissal_report(guild, member, target_role_name="Сотрудник"):
    """
    Create automatic dismissal report for member who left the server.
    
    Args:
        guild: Discord guild object
        member: Discord member object who left (contains role information before leaving)
        target_role_name: Name of the role that triggers automatic dismissal
    """
    try:
        config = load_config()
        dismissal_channel_id = config.get('dismissal_channel')
        
        if not dismissal_channel_id:
            logger.info(f"Dismissal channel not configured, skipping automatic report for {member.name}")
            return False
            
        channel = guild.get_channel(dismissal_channel_id)
        if not channel:
            logger.info(f"Dismissal channel %s not found, skipping automatic report for {member.name}", dismissal_channel_id)
            return False
        
        # Try to get user data from personnel database first using PersonnelManager
        from utils.database_manager import PersonnelManager
        pm = PersonnelManager()
        user_data = await pm.get_personnel_summary(member.id)
        
        if user_data:
            # Use data from personnel database
            extracted_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
            if not extracted_name:
                extracted_name = user_data.get('full_name', '')
            static_value = user_data.get('static', 'Не найден в реестре')
            user_department = user_data.get('department', 'Неизвестно')
            user_rank = user_data.get('rank', 'Неизвестно')
            logger.info(f"Auto-filled data from personnel database for {member.name}")
        else:
            # Fallback to extracting from roles and nickname
            logger.info(f"User {member.name} not found in personnel database, using fallback")
            
            # Extract name from last 2 words of display name
            display_name = getattr(member, 'display_name', member.name)
            name_words = display_name.split()
            
            if len(name_words) >= 2:
                extracted_name = f"{name_words[-2]} {name_words[-1]}"
            else:
                extracted_name = display_name
            
            static_value = "Не найден в реестре"
            
            # Get department and rank from roles BEFORE member left
            # First, try to determine department from ping roles (which roles will be pinged)
            from utils.ping_manager import ping_manager
            ping_roles_list = ping_manager.get_ping_roles_for_user(member, 'dismissals')
            
            # Extract department name from ping roles if available
            user_department = "Неизвестно"
            if ping_roles_list:
                # Use the name of the first ping role as department indicator
                # This matches what we show in pings
                from utils.ping_manager import ping_manager
                dept_code = ping_manager.get_user_department_code(member)
                if dept_code:
                    # Try to get readable department name
                    from utils.department_manager import DepartmentManager
                    departments = DepartmentManager.get_all_departments()
                    dept_data = departments.get(dept_code, {})
                    user_department = dept_data.get('name', dept_code.upper())
                    logger.info("Determined department from ping roles: %s (code: %s)", user_department, dept_code)
                else:
                    # Fallback: use first ping role name as department
                    user_department = ping_roles_list[0].name
                    logger.info("Using first ping role as department: %s", user_department)
            else:
                logger.info("No ping roles found for user, department remains unknown")
            
            # Get rank from database cache
            user_data = await get_cached_user_info(member.id)
            user_rank = user_data.get('rank', 'Не указано') if user_data else 'Не указано'
          # Create embed for automatic dismissal report
        embed = discord.Embed(
            description=f"## 🚨 Автоматический рапорт на увольнение\n**{member.mention} покинул сервер!**",
            color=discord.Color.orange(),  # Orange to distinguish from manual reports
            timestamp=discord.utils.utcnow()
        )
        
        # Add fields with auto-filled data
        embed.add_field(name="Имя Фамилия", value=extracted_name, inline=True)
        embed.add_field(name="Статик", value=static_value, inline=True)
        embed.add_field(name="Подразделение", value=user_department, inline=True)
        embed.add_field(name="Воинское звание", value=user_rank, inline=True)
        embed.add_field(name="Причина увольнения", value="Потеря спец. связи", inline=False)
        
        embed.set_footer(text=f"Автоматически создан: {member.name} (ID: {member.id})")
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        # Add dismissal footer with link to submit new applications (temporarily disabled)
        from .views import add_dismissal_footer_to_embed
        embed = add_dismissal_footer_to_embed(embed, guild.id)
        
        # Import here to avoid circular imports
        from .views import AutomaticDismissalApprovalView
        
        # Create special approval view for automatic dismissals with three buttons
        approval_view = AutomaticDismissalApprovalView(member.id)

        # Create ping content using ping_manager
        ping_content = ""
        from utils.ping_manager import ping_manager
        ping_roles_list = ping_manager.get_ping_roles_for_user(member, 'dismissals')

        if ping_roles_list:
            ping_roles = [role.mention for role in ping_roles_list]
            ping_content = f"-# {' '.join(ping_roles)}\n\n"

        # Send the automatic report with department pings
        message = await channel.send(content=ping_content, embed=embed, view=approval_view)
        
        logger.info(f"Created automatic dismissal report for {member.name} (ID: {member.id})")
        return True
        
    except Exception as e:
        logger.warning(f"Error creating automatic dismissal report for {member.name}: %s", e)
        return False


async def should_create_automatic_dismissal(member, target_role_name="Сотрудник"):
    """
    Check if member who left should get automatic dismissal report.
    
    Args:
        member: Discord member object (before they left)
        target_role_name: Name of the role that triggers automatic dismissal
    
    Returns:
        bool: True if automatic dismissal should be created
    """
    try:
        # Check if member had the target role
        if member.roles:
            for role in member.roles:
                if role.name == target_role_name:
                    return True
        return False
    except Exception as e:
        logger.error(f"Error checking if {member.name} should get automatic dismissal: %s", e)
        return False