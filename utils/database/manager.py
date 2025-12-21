"""
Database Manager - Main interface for database operations
Replacement for GoogleSheetsManager
"""
from typing import Optional, Dict
from datetime import datetime, date, timedelta
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import json

from .connection import db_connection
from .models import Personnel, Employee, Rank, Subdivision, Position, PositionSubdivision, Action, History, Blacklist
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class DatabaseManager:
    """Main database manager - replacement for GoogleSheetsManager"""
    
    def __init__(self):
        self.connection = db_connection
    
    async def initialize(self) -> bool:
        """Initialize database connection"""
        return await self.connection.initialize()
    
    async def close(self):
        """Close database connections"""
        await self.connection.close()
    
    # =============================================================================
    # PERSONNEL OPERATIONS (replacing Google Sheets "Личный Состав")
    # =============================================================================
    
    async def get_user_info_from_personal_list(self, discord_id: int) -> Optional[Dict[str, str]]:
        """
        Get user information by Discord ID
        Replacement for GoogleSheetsManager.get_user_info_from_personal_list
        """
        try:
            logger.info("DB SEARCH: Looking for Discord ID '%s' in personnel table", discord_id)
            
            async with self.connection.get_session() as session:
                # Join with employee data to get current assignment
                stmt = select(Personnel).options(
                    selectinload(Personnel.employees).selectinload(Employee.rank),
                    selectinload(Personnel.employees).selectinload(Employee.subdivision),
                    selectinload(Personnel.employees).selectinload(Employee.position_subdivision).selectinload(PositionSubdivision.position)
                ).where(Personnel.discord_id == discord_id)
                
                result = await session.execute(stmt)
                person = result.scalar_one_or_none()
                
                if not person:
                    logger.info("DB SEARCH: No match found for Discord ID '%s'", discord_id)
                    return None
                
                # Get current employee record (assume latest one)
                current_employee = person.employees[-1] if person.employees else None
                
                user_data = {
                    'first_name': person.first_name or '',
                    'last_name': person.last_name or '',
                    'static': person.static or '',
                    'rank': current_employee.rank.name if current_employee and current_employee.rank else '',
                    'department': current_employee.subdivision.name if current_employee and current_employee.subdivision else '',
                    'position': current_employee.position_subdivision.position.name if current_employee and current_employee.position_subdivision and current_employee.position_subdivision.position else '',
                    'discord_id': str(person.discord_id)
                }
                
                logger.info("DB SEARCH: Found user data: %s", user_data)
                return user_data
                
        except Exception as e:
            logger.warning("DB SEARCH: Error searching for user: %s", e)
            return None
    
    async def add_user_to_personal_list(self, discord_id: int, first_name: str, last_name: str, 
                                      static: str, rank: str, department: str = "Военная Академия - ВА", 
                                      position: str = "") -> bool:
        """
        Add new user to personnel database
        Replacement for GoogleSheetsManager.add_user_to_personal_list
        """
        try:
            logger.info("DB ADD: Adding Discord ID '%s' to personnel table", discord_id)
            
            async with self.connection.get_session() as session:
                # Check if user already exists
                existing_person = await session.get(Personnel, discord_id)
                if existing_person:
                    logger.info("DB ADD: User already exists, updating instead")
                    return await self.update_user_basic_info(discord_id, first_name, last_name, static)
                
                # Create new personnel record
                new_person = Personnel(
                    discord_id=discord_id,
                    first_name=first_name,
                    last_name=last_name,
                    static=static,
                    join_date=date.today(),
                    is_dismissal=False
                )
                session.add(new_person)
                
                # Get or create rank
                rank_obj = await self._get_or_create_rank(session, rank)
                
                # Get or create subdivision
                subdivision_obj = await self._get_or_create_subdivision(session, department)
                
                # Get or create position (if provided)
                position_subdivision_obj = None
                if position:
                    position_obj = await self._get_or_create_position(session, position)
                    position_subdivision_obj = await self._get_or_create_position_subdivision(
                        session, position_obj.id, subdivision_obj.id
                    )
                
                # Create employee assignment
                new_employee = Employee(
                    rank_id=rank_obj.id,
                    subdivision_id=subdivision_obj.id,
                    position_subdivision_id=position_subdivision_obj.id if position_subdivision_obj else None,
                    personnel_id=discord_id
                )
                session.add(new_employee)
                
                await session.commit()
                logger.info("DB ADD: Successfully added user %s %s", first_name, last_name)
                
                # Log the action
                await self._log_action(discord_id, "Принят на службу", f"Добавлен в систему", "Система")
                
                return True
                
        except Exception as e:
            logger.warning("DB ADD: Error adding user: %s", e)
            return False
    
    async def delete_user_from_personal_list(self, discord_id: int) -> bool:
        """
        Delete user from personnel database (soft delete - mark as dismissed)
        Replacement for GoogleSheetsManager.delete_user_from_personal_list
        """
        try:
            logger.info("DB DELETE: Marking Discord ID '%s' as dismissed", discord_id)
            
            async with self.connection.get_session() as session:
                person = await session.get(Personnel, discord_id)
                if not person:
                    logger.info("DB DELETE: User not found")
                    return False
                
                # Soft delete - mark as dismissed
                person.is_dismissal = True
                person.dismissal_date = date.today()
                
                await session.commit()
                logger.info("DB DELETE: Successfully marked user as dismissed")
                
                # Log the action
                await self._log_action(discord_id, "Уволен со службы", "Помечен как уволенный", "Система")
                
                return True
                
        except Exception as e:
            logger.warning("DB DELETE: Error deleting user: %s", e)
            return False
    
    async def update_user_rank(self, discord_id: int, new_rank: str) -> bool:
        """
        Update user's rank
        Replacement for GoogleSheetsManager.update_user_rank
        """
        try:
            logger.info("DB RANK UPDATE: Updating rank for Discord ID '%s' to '%s'", discord_id, new_rank)
            
            async with self.connection.get_session() as session:
                person = await session.get(Personnel, discord_id)
                if not person:
                    logger.info("DB RANK UPDATE: User not found")
                    return False
                
                # Get or create new rank
                rank_obj = await self._get_or_create_rank(session, new_rank)
                
                # Get current employee record
                current_employee = person.employees[-1] if person.employees else None
                if current_employee:
                    old_rank_name = current_employee.rank.name if current_employee.rank else "Неизвестно"
                    current_employee.rank_id = rank_obj.id
                else:
                    # Create new employee record if none exists
                    default_subdivision = await self._get_or_create_subdivision(session, "Военная Академия - ВА")
                    current_employee = Employee(
                        rank_id=rank_obj.id,
                        subdivision_id=default_subdivision.id,
                        personnel_id=discord_id
                    )
                    session.add(current_employee)
                    old_rank_name = "Неизвестно"
                
                await session.commit()
                logger.info("DB RANK UPDATE: Successfully updated rank to '%s'", new_rank)
                
                # Log the action
                await self._log_action(
                    discord_id, "Изменение звания", 
                    f"Звание изменено с '{old_rank_name}' на '{new_rank}'", 
                    "Система"
                )
                
                return True
                
        except Exception as e:
            logger.warning("DB RANK UPDATE: Error updating rank: %s", e)
            return False
    
    async def update_user_position(self, discord_id: int, new_position: str) -> bool:
        """
        Update user's position
        Replacement for GoogleSheetsManager.update_user_position
        """
        try:
            logger.info("DB POSITION UPDATE: Updating position for Discord ID '%s' to '%s'", discord_id, new_position)
            
            async with self.connection.get_session() as session:
                person = await session.get(Personnel, discord_id)
                if not person:
                    logger.info("DB POSITION UPDATE: User not found")
                    return False
                
                # Get current employee record
                current_employee = person.employees[-1] if person.employees else None
                if not current_employee:
                    logger.info("DB POSITION UPDATE: No employee record found")
                    return False
                
                # Get or create new position
                position_obj = await self._get_or_create_position(session, new_position)
                position_subdivision_obj = await self._get_or_create_position_subdivision(
                    session, position_obj.id, current_employee.subdivision_id
                )
                
                old_position_name = "Неизвестно"
                if current_employee.position_subdivision and current_employee.position_subdivision.position:
                    old_position_name = current_employee.position_subdivision.position.name
                
                current_employee.position_subdivision_id = position_subdivision_obj.id
                
                await session.commit()
                logger.info("DB POSITION UPDATE: Successfully updated position to '%s'", new_position)
                
                # Log the action
                await self._log_action(
                    discord_id, "Изменение должности", 
                    f"Должность изменена с '{old_position_name}' на '{new_position}'", 
                    "Система"
                )
                
                return True
                
        except Exception as e:
            logger.warning("DB POSITION UPDATE: Error updating position: %s", e)
            return False
    
    # =============================================================================
    # AUDIT OPERATIONS (replacing Google Sheets "Общий Кадровый")
    # =============================================================================
    
    async def add_dismissal_record(self, form_data: Dict, dismissed_user, approving_user, 
                                 dismissal_time: datetime, override_moderator_info: str = None) -> bool:
        """
        Add dismissal record to database
        Replacement for GoogleSheetsManager.add_dismissal_record
        """
        try:
            logger.info("DB DISMISSAL: Adding dismissal record")
            
            discord_id = dismissed_user.id
            name_from_form = form_data.get('name', '')
            static_from_form = form_data.get('static', '')
            reason = form_data.get('reason', '')
            
            # Get approving user info
            approved_by_info = override_moderator_info or approving_user.display_name
            
            async with self.connection.get_session() as session:
                # Update personnel record
                person = await session.get(Personnel, discord_id)
                if person:
                    person.is_dismissal = True
                    person.dismissal_date = dismissal_time.date()
                    person.dismissal_reason = reason
                
                # Log the dismissal action
                await self._log_action(
                    discord_id, "Уволен со службы",
                    json.dumps({
                        'name': name_from_form,
                        'static': static_from_form,
                        'reason': reason,
                        'dismissed_by': approved_by_info
                    }, ensure_ascii=False),
                    approved_by_info
                )
                
                await session.commit()
                logger.info("DB DISMISSAL: Successfully added dismissal record")
                return True
                
        except Exception as e:
            logger.warning("DB DISMISSAL: Error adding dismissal record: %s", e)
            return False
    
    async def add_hiring_record(self, application_data: Dict, approved_user, approving_user, 
                              hiring_time: datetime, override_moderator_info: str = None) -> bool:
        """
        Add hiring record to database
        Replacement for GoogleSheetsManager.add_hiring_record
        """
        try:
            logger.info("DB HIRING: Adding hiring record")
            
            discord_id = approved_user.id
            name_from_form = application_data.get('name', '')
            static_from_form = application_data.get('static', '')
            rank = application_data.get('rank', 'Рядовой')
            
            # Only create record for "Рядовой" rank
            if rank.lower() != 'рядовой':
                logger.info("Skipping hiring record - rank is '%s', not 'Рядовой'", rank)
                return True
            
            approved_by_info = override_moderator_info or approving_user.display_name
            
            await self._log_action(
                discord_id, "Принят на службу",
                json.dumps({
                    'name': name_from_form,
                    'static': static_from_form,
                    'rank': rank,
                    'approved_by': approved_by_info
                }, ensure_ascii=False),
                approved_by_info
            )
            
            logger.info("DB HIRING: Successfully added hiring record")
            return True
            
        except Exception as e:
            logger.warning("DB HIRING: Error adding hiring record: %s", e)
            return False
    
    # =============================================================================
    # BLACKLIST OPERATIONS
    # =============================================================================
    
    async def add_blacklist_record(self, form_data: Dict, dismissed_user, approving_user, 
                                 dismissal_time: datetime, days_difference: int, 
                                 override_moderator_info: str = None) -> bool:
        """
        Add blacklist penalty record
        Replacement for GoogleSheetsManager.add_blacklist_record
        """
        try:
            logger.info("DB BLACKLIST: Adding blacklist record")
            
            discord_id = dismissed_user.id
            name_from_form = form_data.get('name', '')
            static_from_form = form_data.get('static', '')
            
            approved_by_info = override_moderator_info or approving_user.display_name
            
            async with self.connection.get_session() as session:
                blacklist_entry = Blacklist(
                    reason="Неустойка",
                    start_date=dismissal_time.date(),
                    end_date=(dismissal_time + timedelta(days=14)).date(),
                    personnel_id=discord_id,
                    added_by=approved_by_info
                )
                session.add(blacklist_entry)
                
                await session.commit()
                logger.info("DB BLACKLIST: Successfully added blacklist record")
                return True
                
        except Exception as e:
            logger.warning("DB BLACKLIST: Error adding blacklist record: %s", e)
            return False
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    async def _get_or_create_rank(self, session, rank_name: str) -> Rank:
        """Get existing rank or create new one"""
        stmt = select(Rank).where(Rank.name == rank_name)
        result = await session.execute(stmt)
        rank = result.scalar_one_or_none()
        
        if not rank:
            rank = Rank(name=rank_name)
            session.add(rank)
            await session.flush()  # To get the ID
        
        return rank
    
    async def _get_or_create_subdivision(self, session, subdivision_name: str) -> Subdivision:
        """Get existing subdivision or create new one"""
        stmt = select(Subdivision).where(Subdivision.name == subdivision_name)
        result = await session.execute(stmt)
        subdivision = result.scalar_one_or_none()
        
        if not subdivision:
            subdivision = Subdivision(name=subdivision_name)
            session.add(subdivision)
            await session.flush()
        
        return subdivision
    
    async def _get_or_create_position(self, session, position_name: str) -> Position:
        """Get existing position or create new one"""
        stmt = select(Position).where(Position.name == position_name)
        result = await session.execute(stmt)
        position = result.scalar_one_or_none()
        
        if not position:
            position = Position(name=position_name)
            session.add(position)
            await session.flush()
        
        return position
    
    async def _get_or_create_position_subdivision(self, session, position_id: int, subdivision_id: int) -> PositionSubdivision:
        """Get existing position-subdivision link or create new one"""
        stmt = select(PositionSubdivision).where(
            and_(PositionSubdivision.position_id == position_id,
                 PositionSubdivision.subdivision_id == subdivision_id)
        )
        result = await session.execute(stmt)
        pos_sub = result.scalar_one_or_none()
        
        if not pos_sub:
            pos_sub = PositionSubdivision(position_id=position_id, subdivision_id=subdivision_id)
            session.add(pos_sub)
            await session.flush()
        
        return pos_sub
    
    async def _log_action(self, personnel_id: int, action_name: str, details: str, performed_by: str):
        """Log an action to history table"""
        try:
            async with self.connection.get_session() as session:
                # Get or create action type
                action_obj = await self._get_or_create_action(session, action_name)
                
                history_record = History(
                    personnel_id=personnel_id,
                    action_id=action_obj.id,
                    details=details,
                    performed_by=performed_by,
                    changes=details  # Store detailed changes as JSON
                )
                session.add(history_record)
                await session.commit()
                
        except Exception as e:
            logger.warning("Error logging action: %s", e)
    
    async def _get_or_create_action(self, session, action_name: str) -> Action:
        """Get existing action or create new one"""
        stmt = select(Action).where(Action.name == action_name)
        result = await session.execute(stmt)
        action = result.scalar_one_or_none()
        
        if not action:
            action = Action(name=action_name)
            session.add(action)
            await session.flush()
        
        return action

# Global database manager instance
database_manager = DatabaseManager()