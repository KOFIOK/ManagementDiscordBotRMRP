"""
Automatic dismissal system
Handles creation of automatic dismissal reports when members leave the server
"""

import discord
from utils.config_manager import load_config
from utils.google_sheets import sheets_manager


async def create_automatic_dismissal_report(guild, member, target_role_name="Военнослужащий ВС РФ"):
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
            print(f"Dismissal channel not configured, skipping automatic report for {member.name}")
            return False
            
        channel = guild.get_channel(dismissal_channel_id)
        if not channel:
            print(f"Dismissal channel {dismissal_channel_id} not found, skipping automatic report for {member.name}")
            return False
        
        # Extract name from last 2 words of display name
        display_name = getattr(member, 'display_name', member.name)
        name_words = display_name.split()
        
        if len(name_words) >= 2:
            extracted_name = f"{name_words[-2]} {name_words[-1]}"
        else:
            extracted_name = display_name
        
        # Get ping settings for department determination
        ping_settings = config.get('ping_settings', {})
        
        # Get department and rank from roles BEFORE member left
        user_department = sheets_manager.get_department_from_roles(member, ping_settings)
        user_rank = sheets_manager.get_rank_from_roles(member)
        
        # Create embed for automatic dismissal report
        embed = discord.Embed(
            description=f"## 🚨 Автоматический рапорт на увольнение\n**{member.mention} покинул сервер!**",
            color=discord.Color.orange(),  # Orange to distinguish from manual reports
            timestamp=discord.utils.utcnow()
        )
        
        # Add fields - note: static requires moderator input
        embed.add_field(name="Имя Фамилия", value=extracted_name, inline=True)
        embed.add_field(name="Статик", value="**Требуется ввод**", inline=True)
        embed.add_field(name="Подразделение", value=user_department, inline=True)
        embed.add_field(name="Воинское звание", value=user_rank, inline=True)
        embed.add_field(name="Причина увольнения", value="Потеря спец. связи", inline=False)
        
        # Note: No "Тип рапорта" field for automatic reports as requested
        
        embed.set_footer(text=f"Автоматически создан: {member.name} (ID: {member.id})")
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        # Import here to avoid circular imports
        from .views import DismissalApprovalView
        
        # Create special approval view for automatic dismissals
        approval_view = DismissalApprovalView(member.id, is_automatic=True)
        
        # Create ping content based on departed member's department (we have role info)
        ping_content = ""
        if ping_settings:
            # Find user's highest department role that has ping settings
            user_department_role = None
            highest_position = -1
            
            for department_role_id in ping_settings.keys():
                dept_role = guild.get_role(int(department_role_id))
                if dept_role and dept_role in member.roles:
                    # Check if this role is higher in hierarchy than current highest
                    if dept_role.position > highest_position:
                        highest_position = dept_role.position
                        user_department_role = dept_role
            
            # Get ping roles for this department
            if user_department_role:
                ping_role_ids = ping_settings.get(str(user_department_role.id), [])
                ping_roles = []
                for role_id in ping_role_ids:
                    role = guild.get_role(role_id)
                    if role:
                        ping_roles.append(role.mention)
                
                if ping_roles:
                    ping_content = f"-# {' '.join(ping_roles)}\n\n"
        
        # Send the automatic report with department pings
        message = await channel.send(content=ping_content, embed=embed, view=approval_view)
        
        print(f"✅ Created automatic dismissal report for {member.name} (ID: {member.id})")
        return True
        
    except Exception as e:
        print(f"❌ Error creating automatic dismissal report for {member.name}: {e}")
        return False


async def should_create_automatic_dismissal(member, target_role_name="Военнослужащий ВС РФ"):
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
        print(f"Error checking if {member.name} should get automatic dismissal: {e}")
        return False
