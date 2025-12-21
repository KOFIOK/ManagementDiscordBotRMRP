"""
Department Applications Module - System for department applications with moderation
"""

from .manager import DepartmentApplicationManager
from .views import DepartmentApplicationModerationView as DepartmentApplicationView, DepartmentSelectView
from .modals import DepartmentApplicationStage1Modal, DepartmentApplicationStage2Modal
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

def register_static_views(bot):
    """Регистрирует статические views для восстановления после рестарта"""
    try:
        # Создаем единый статический view для всех типов заявлений
        # Тип заявления будет определяться из embed при обработке interaction
        static_application_data = {
            'user_id': 0,  # Будет извлекаться из embed при обработке
            'department_code': '',  # Будет извлекаться из embed при обработке
            'name': '',
            'static': '',
            'application_type': 'join'  # По умолчанию, но будет переопределено
        }
        
        static_moderation_view = DepartmentApplicationView(static_application_data)
        static_moderation_view.setup_buttons()
        bot.add_view(static_moderation_view)
        logger.info("Registered static department application moderation view")
        
        return True
    except Exception as e:
        logger.warning("Error registering static views: %s", e)
        return False

__all__ = [
    'DepartmentApplicationManager',
    'DepartmentApplicationView', 
    'DepartmentSelectView',
    'DepartmentApplicationStage1Modal',
    'DepartmentApplicationStage2Modal',
    'register_static_views'
]
