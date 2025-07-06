"""
Department Applications Module - System for department applications with moderation
"""

from .manager import DepartmentApplicationManager
from .views import DepartmentApplicationView, DepartmentSelectView
from .modals import DepartmentApplicationStage1Modal, DepartmentApplicationStage2Modal

def register_static_views(bot):
    """Регистрирует статические views для восстановления после рестарта"""
    try:
        # Создаем пустой application_data для статической регистрации
        static_application_data = {
            'user_id': 0,  # Будет извлекаться из embed при обработке
            'department_code': '',  # Будет извлекаться из embed при обработке
            'name': '',
            'static': ''
        }
        
        static_moderation_view = DepartmentApplicationView(static_application_data)
        bot.add_view(static_moderation_view)
        print("✅ Registered static department application moderation view")
        return True
    except Exception as e:
        print(f"❌ Error registering static views: {e}")
        return False

__all__ = [
    'DepartmentApplicationManager',
    'DepartmentApplicationView', 
    'DepartmentSelectView',
    'DepartmentApplicationStage1Modal',
    'DepartmentApplicationStage2Modal',
    'register_static_views'
]
