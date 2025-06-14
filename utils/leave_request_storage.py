"""
Storage system for leave requests
Handles daily data with automatic cleanup at midnight MSK
"""
import json
import os
from datetime import datetime, timedelta
import pytz
from typing import List, Optional
import asyncio


class LeaveRequestStorage:
    """Manages leave request data storage with daily cleanup"""
    
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    DATA_FILE = "data/leave_requests.json"
    
    @classmethod
    def _ensure_data_file(cls):
        """Ensure data file exists"""
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(cls.DATA_FILE):
            cls._save_data({})
    
    @classmethod
    def _load_data(cls) -> dict:
        """Load data from file"""
        cls._ensure_data_file()
        try:
            with open(cls.DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    @classmethod
    def _save_data(cls, data: dict):
        """Save data to file"""
        with open(cls.DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def _get_today_key(cls) -> str:
        """Get today's date key in MSK"""
        return datetime.now(cls.MOSCOW_TZ).date().isoformat()
    
    @classmethod
    def _generate_request_id(cls) -> str:
        """Generate unique request ID"""
        now = datetime.now(cls.MOSCOW_TZ)
        return f"LR_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond}"
    
    @classmethod
    def add_request(cls, user_id: int, name: str, static: str, start_time: str, 
                   end_time: str, reason: str, department: str, guild_id: int) -> str:
        """
        Add new leave request
        Returns: request_id
        """
        data = cls._load_data()
        today = cls._get_today_key()
        request_id = cls._generate_request_id()
        
        if today not in data:
            data[today] = {}
        
        user_key = str(user_id)
        if user_key not in data[today]:
            data[today][user_key] = []
          # Calculate duration
        from forms.leave_requests.utils import LeaveRequestValidator
        duration = LeaveRequestValidator.calculate_duration_minutes(start_time, end_time)
        
        request = {
            "id": request_id,
            "user_id": user_id,
            "guild_id": guild_id,
            "name": name,
            "static": static,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration,
            "reason": reason,
            "department": department,
            "status": "pending",
            "timestamp": datetime.now(cls.MOSCOW_TZ).isoformat(),
            "reviewer_id": None,
            "reviewer_name": None,
            "review_timestamp": None,
            "rejection_reason": None
        }
        
        data[today][user_key].append(request)
        cls._save_data(data)
        
        return request_id
    
    @classmethod
    def get_user_requests_today(cls, user_id: int) -> List[dict]:
        """Get all user's requests for today"""
        data = cls._load_data()
        today = cls._get_today_key()
        user_key = str(user_id)
        
        if today not in data or user_key not in data[today]:
            return []
        
        return data[today][user_key]
    
    @classmethod
    def get_request_by_id(cls, request_id: str) -> Optional[dict]:
        """Get request by ID"""
        data = cls._load_data()
        
        for date_data in data.values():
            for user_requests in date_data.values():
                for request in user_requests:
                    if request["id"] == request_id:
                        return request
        
        return None
    
    @classmethod
    def update_request_status(cls, request_id: str, status: str, reviewer_id: int, 
                            reviewer_name: str, rejection_reason: str = None) -> bool:
        """
        Update request status
        Returns: True if updated successfully
        """
        data = cls._load_data()
        
        for date_data in data.values():
            for user_requests in date_data.values():
                for request in user_requests:
                    if request["id"] == request_id:
                        request["status"] = status
                        request["reviewer_id"] = reviewer_id
                        request["reviewer_name"] = reviewer_name
                        request["review_timestamp"] = datetime.now(cls.MOSCOW_TZ).isoformat()
                        if rejection_reason:
                            request["rejection_reason"] = rejection_reason
                        
                        cls._save_data(data)
                        return True
        
        return False    
    @classmethod
    def delete_request(cls, request_id: str, user_id: int, is_admin: bool = False) -> bool:
        """
        Delete request completely from storage
        Args:
            request_id: ID of request to delete
            user_id: ID of user requesting deletion
            is_admin: True if user is admin (can delete any request)
        Returns: True if deleted successfully
        """
        data = cls._load_data()
        
        for date_data in data.values():
            for user_key, user_requests in date_data.items():
                for i, request in enumerate(user_requests):
                    if request["id"] == request_id:
                        # Check permissions
                        if not is_admin and request["user_id"] != user_id:
                            return False  # Not owner and not admin
                        
                        if not is_admin and request["status"] != "pending":
                            return False  # Only pending requests can be deleted by user
                        
                        # Admin can delete any request, user can only delete pending own requests
                        del user_requests[i]
                        
                        # Clean up empty user data
                        if not user_requests:
                            del date_data[user_key]
                        
                        cls._save_data(data)
                        return True
        
        return False
    
    @classmethod
    def get_all_requests_today(cls) -> List[dict]:
        """Get all requests for today (for moderation)"""
        data = cls._load_data()
        today = cls._get_today_key()
        
        if today not in data:
            return []
        
        all_requests = []
        for user_requests in data[today].values():
            all_requests.extend(user_requests)
        
        # Sort by timestamp
        all_requests.sort(key=lambda x: x["timestamp"])
        return all_requests
    
    @classmethod
    def cleanup_old_data(cls):
        """Remove data from previous days (called at midnight)"""
        data = cls._load_data()
        today = cls._get_today_key()
        
        # Keep only today's data
        cleaned_data = {today: data.get(today, {})}
        cls._save_data(cleaned_data)
        
        print(f"🧹 Leave requests data cleaned up. Kept data for {today}")
    
    @classmethod
    async def start_daily_cleanup_task(cls):
        """Start background task for daily cleanup at midnight MSK"""
        while True:
            try:
                now = datetime.now(cls.MOSCOW_TZ)
                # Calculate time until next midnight
                tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + \
                          timedelta(days=1)
                seconds_until_midnight = (tomorrow - now).total_seconds()
                
                print(f"⏰ Leave requests cleanup scheduled in {int(seconds_until_midnight/3600)}h {int((seconds_until_midnight%3600)/60)}m")
                
                # Wait until midnight
                await asyncio.sleep(seconds_until_midnight)
                
                # Cleanup old data
                cls.cleanup_old_data()
                
                # Wait a bit to avoid running multiple times
                await asyncio.sleep(60)
                
            except Exception as e:
                print(f"❌ Error in leave requests cleanup task: {e}")
                # Wait 1 hour before retrying
                await asyncio.sleep(3600)
