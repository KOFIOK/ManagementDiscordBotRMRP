# Пустой файл для обозначения директории как пакет Python

from typing import Optional, Dict, Any

def get_safe_personnel_name(personnel_data_summary: Optional[Dict], discord_user_display_name: str) -> str:
    """
    Get safe personnel name for audit, avoiding Discord display names that look like personnel data.
    
    Args:
        personnel_data_summary: Personnel summary from database
        discord_user_display_name: Discord display name as fallback
        
    Returns:
        str: Safe name to use in audit
    """
    # Try to get full_name from database first
    if personnel_data_summary:
        full_name = personnel_data_summary.get('full_name', '').strip()
        if full_name:
            return full_name
    
    # Check if Discord display name looks like personnel data (contains | or numbers)
    # If it does, use a generic fallback instead
    if '|' in discord_user_display_name or any(char.isdigit() for char in discord_user_display_name):
        return "Неизвестно"
    
    # Otherwise, use Discord display name as fallback
    return discord_user_display_name
