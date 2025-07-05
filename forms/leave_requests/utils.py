"""
Utilities for leave request validation and processing
"""
import re
from datetime import datetime, time, timedelta
import pytz
from utils.config_manager import load_config


class LeaveRequestValidator:
    """Handles validation of leave requests"""
    
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    WORK_START = time(9, 0)  # 09:00
    WORK_END = time(22, 0)   # 22:00
    MAX_DURATION_MINUTES = 60  # 1 hour
    
    @classmethod
    def validate_time_format(cls, time_str: str) -> bool:
        """Validate time format HH:MM"""
        try:
            time.fromisoformat(time_str)
            return True
        except ValueError:
            return False
    
    @classmethod
    def parse_time(cls, time_str: str) -> time:
        """Parse time string to time object"""
        return time.fromisoformat(time_str)
    
    @classmethod
    def calculate_duration_minutes(cls, start_time: str, end_time: str) -> int:
        """Calculate duration in minutes between start and end time"""
        start = cls.parse_time(start_time)
        end = cls.parse_time(end_time)
        
        # Create datetime objects for today
        today = datetime.now(cls.MOSCOW_TZ).date()
        start_dt = datetime.combine(today, start)
        end_dt = datetime.combine(today, end)
        
        # If end time is before start time, it means next day (not allowed)
        if end_dt <= start_dt:
            return -1  # Invalid duration
        
        duration = end_dt - start_dt
        return int(duration.total_seconds() / 60)
    
    @classmethod
    def is_work_hours(cls, start_time: str, end_time: str) -> bool:
        """Check if requested time is within work hours"""
        start = cls.parse_time(start_time)
        end = cls.parse_time(end_time)
        
        return (cls.WORK_START <= start <= cls.WORK_END and 
                cls.WORK_START <= end <= cls.WORK_END)
    
    @classmethod
    def is_future_time(cls, time_str: str) -> bool:
        """Check if requested time is in the future (today only)"""
        now = datetime.now(cls.MOSCOW_TZ)
        today = now.date()
        request_time = cls.parse_time(time_str)
        request_datetime = datetime.combine(today, request_time)
        request_datetime = cls.MOSCOW_TZ.localize(request_datetime)
        
        return request_datetime > now
    
    @classmethod
    def format_static(cls, static_input: str) -> str:
        """Format static ID to XXX-XXX format"""
        # Remove all non-digits
        digits = re.sub(r'\D', '', static_input)
        
        if len(digits) != 6:
            return static_input  # Return as-is if not 6 digits
        
        # Format as XXX-XXX
        return f"{digits[:3]}-{digits[3:]}"
    
    @classmethod
    def validate_request(cls, user_id: int, start_time: str, end_time: str) -> dict:
        """
        Comprehensive validation of leave request
        Returns: {"valid": bool, "error": str, "duration_minutes": int}
        """
        # Check time format
        if not cls.validate_time_format(start_time):
            return {"valid": False, "error": "Неверный формат времени начала (используйте HH:MM)", "duration_minutes": 0}
        
        if not cls.validate_time_format(end_time):
            return {"valid": False, "error": "Неверный формат времени конца (используйте HH:MM)", "duration_minutes": 0}
        
        # Check if start time is in the future
        if not cls.is_future_time(start_time):
            return {"valid": False, "error": "Время начала отгула должно быть в будущем", "duration_minutes": 0}
        
        # Check work hours
        if not cls.is_work_hours(start_time, end_time):
            return {"valid": False, "error": "Отгул можно взять только в рабочее время ()", "duration_minutes": 0}
        
        # Calculate duration
        duration = cls.calculate_duration_minutes(start_time, end_time)
        if duration <= 0:
            return {"valid": False, "error": "Время окончания должно быть позже времени начала", "duration_minutes": 0}
        
        if duration > cls.MAX_DURATION_MINUTES:
            hours = duration // 60
            minutes = duration % 60
            duration_str = f"{hours} ч {minutes} мин" if hours > 0 else f"{minutes} мин"
            return {"valid": False, "error": f"Максимальная длительность отгула: 1 час. Указанная длительность: {duration_str}", "duration_minutes": duration}
        
        # Check daily limit
        daily_check = cls.check_daily_limit(user_id)
        if not daily_check["can_request"]:
            return {"valid": False, "error": daily_check["reason"], "duration_minutes": duration}
        
        return {"valid": True, "error": "", "duration_minutes": duration}
    
    @classmethod
    def validate_request_form_only(cls, start_time: str, end_time: str) -> dict:
        """
        Validate leave request data without checking daily limit
        (daily limit is checked in button handler)
        Returns: {"valid": bool, "error": str, "duration_minutes": int}
        """
        # Validate time format
        if not cls.validate_time_format(start_time):
            return {"valid": False, "error": "Неверный формат времени начала (используйте HH:MM)", "duration_minutes": 0}
        
        if not cls.validate_time_format(end_time):
            return {"valid": False, "error": "Неверный формат времени конца (используйте HH:MM)", "duration_minutes": 0}
        
        # Check if start time is in the future
        if not cls.is_future_time(start_time):
            return {"valid": False, "error": "Время начала отгула должно быть в будущем", "duration_minutes": 0}
        
        # Check work hours
        if not cls.is_work_hours(start_time, end_time):
            return {"valid": False, "error": "Отгул можно взять только в рабочее время ()", "duration_minutes": 0}
        
        # Calculate duration
        duration = cls.calculate_duration_minutes(start_time, end_time)
        if duration <= 0:
            return {"valid": False, "error": "Время окончания должно быть позже времени начала", "duration_minutes": 0}
        
        if duration > cls.MAX_DURATION_MINUTES:
            hours = duration // 60
            minutes = duration % 60
            duration_str = f"{hours} ч {minutes} мин" if hours > 0 else f"{minutes} мин"
            return {"valid": False, "error": f"Максимальная длительность отгула: 1 час. Указанная длительность: {duration_str}", "duration_minutes": duration}
        
        return {"valid": True, "error": "", "duration_minutes": duration}

    @classmethod
    def check_daily_limit(cls, user_id: int) -> dict:
        """
        Check if user can make a leave request today
        Returns: {"can_request": bool, "reason": str, "existing_requests": list}
        """
        from utils.leave_request_storage import LeaveRequestStorage
        
        today = datetime.now(cls.MOSCOW_TZ).date().isoformat()
        user_requests = LeaveRequestStorage.get_user_requests_today(user_id)
        
        # Check for pending or approved requests
        active_requests = [req for req in user_requests if req["status"] in ["pending", "approved"]]
        
        if active_requests:
            req = active_requests[0]
            status_text = "ожидает рассмотрения" if req["status"] == "pending" else "одобрена"
            return {
                "can_request": False,
                "reason": f"У вас уже есть заявка на отгул на сегодня ({req['start_time']}-{req['end_time']}, статус: {status_text})",
                "existing_requests": user_requests
            }
        
        return {
            "can_request": True,
            "reason": "",
            "existing_requests": user_requests
        }


class LeaveRequestDepartmentDetector:
    """Detects user department for leave requests (similar to dismissal)"""
    
    # Department role patterns (same as dismissal system)
    DEPARTMENT_PATTERNS = {
        'ва': ['военная академия', 'вa', 'академ'],
        'вк': ['военный комиссариат', 'вк', 'комиссариат'],
        'увп': ['управление военной полиции', 'увп', 'военная полиция', 'полиция'],
        'ссо': ['силы специальных операций', 'ссо', 'спецназ', 'специальные операции'],
        'мр': ['медицинская рота', 'мр', 'медицинская', 'медики'],
        'роио': ['рота охраны и обеспечения', 'роио', 'охрана', 'обеспечение']
    }
    
    @classmethod
    def detect_department(cls, user_roles: list) -> str:
        """
        Detect user department based on roles
        Returns department code or 'unknown'
        """
        role_names = [role.name.lower() for role in user_roles]
        
        for dept_code, patterns in cls.DEPARTMENT_PATTERNS.items():
            for pattern in patterns:
                for role_name in role_names:
                    if pattern in role_name:
                        return dept_code
        return 'unknown'
    
    @classmethod
    def get_ping_roles(cls, department: str, guild) -> list:
        """Get ping roles for department from config - updated for new ping system"""
        from utils.ping_manager import ping_manager
        
        # Используем новый ping_manager с контекстом leave_requests (множественное число)
        return ping_manager.get_ping_roles_for_context(department, 'leave_requests', guild)
    
    @classmethod
    def get_ping_roles_from_user(cls, user_roles: list, guild) -> list:
        """
        Get ping roles based on user's roles using new ping system
        Returns list of roles to ping
        """
        from utils.ping_manager import ping_manager
        from utils.department_manager import DepartmentManager
        
        # Определяем подразделение пользователя по его ролям
        dept_manager = DepartmentManager()
        departments = dept_manager.get_all_departments()
        user_department = None
        
        user_role_ids = [role.id for role in user_roles]
        
        for dept_id, dept_data in departments.items():
            key_role_id = dept_data.get('key_role_id')
            if key_role_id and key_role_id in user_role_ids:
                user_department = dept_id
                break
        
        if user_department:
            return ping_manager.get_ping_roles_for_context(user_department, 'leave_requests', guild)
        
        return []
