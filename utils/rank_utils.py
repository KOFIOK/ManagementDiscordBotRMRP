"""
Утилита для работы с рангами Discord
Извлечена из deprecated dismissal_logger.py
"""

def get_rank_from_roles_postgresql(user):
    """
    Получить ранг пользователя из его ролей Discord
    
    Args:
        user: Discord Member объект с ролями
        
    Returns:
        str: Название ранга или None если не найдено
    """
    # Иерархия рангов (чем меньше число, тем выше ранг)
    rank_hierarchy = {
        "Генерал армии": 1,
        "Генерал-полковник": 2,
        "Генерал-лейтенант": 3,
        "Генерал-майор": 4,
        
        # Старшие офицеры
        "Полковник": 5,
        "Подполковник": 6,
        "Майор": 7,
        
        # Младшие офицеры
        "Капитан": 8,
        "Старший лейтенант": 9,
        "Лейтенант": 10,
        "Младший лейтенант": 11,
        
        # Прапорщики
        "Старший прапорщик": 12,
        "Прапорщик": 13,
        
        # Сержанты
        "Старшина": 14,
        "Старший сержант": 15,
        "Сержант": 16,
        "Младший сержант": 17,
        
        # Солдаты
        "Ефрейтор": 18,
        "Рядовой": 19
    }
    
    user_roles = [role.name for role in user.roles]
    
    # Ищем самый высокий ранг среди ролей пользователя
    highest_rank = None
    highest_priority = float('inf')
    
    for role_name in user_roles:
        if role_name in rank_hierarchy:
            priority = rank_hierarchy[role_name]
            if priority < highest_priority:
                highest_priority = priority
                highest_rank = role_name
    
    return highest_rank
