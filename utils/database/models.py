"""
SQLAlchemy models for PostgreSQL database
Corresponds to the ER diagram structure
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, BigInteger, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .connection import Base

class Personnel(Base):
    """Main personnel table - corresponds to personnel in ER diagram"""
    __tablename__ = 'personnel'
    
    discord_id = Column(BigInteger, primary_key=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    static = Column(String(50))
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_dismissal = Column(Boolean, default=False)
    join_date = Column(Date)
    dismissal_date = Column(Date)
    dismissal_reason = Column(Text)
    
    # Relationship to employees
    employees = relationship("Employee", back_populates="personnel")

class Rank(Base):
    """Ranks reference table"""
    __tablename__ = 'ranks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    role_id = Column(BigInteger, nullable=True)  # Discord role ID
    rank_level = Column(Integer, nullable=False)  # Hierarchy level
    abbreviation = Column(String(50), nullable=True)  # Rank abbreviation
    
    # Relationship to employees
    employees = relationship("Employee", back_populates="rank")

class Subdivision(Base):
    """Subdivisions reference table"""
    __tablename__ = 'subdivisions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)
    
    # Relationships
    employees = relationship("Employee", back_populates="subdivision")
    position_subdivisions = relationship("PositionSubdivision", back_populates="subdivision")

class Position(Base):
    """Positions reference table"""
    __tablename__ = 'positions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False)
    
    # Relationship to position_subdivision
    position_subdivisions = relationship("PositionSubdivision", back_populates="position")

class PositionSubdivision(Base):
    """Junction table for positions and subdivisions"""
    __tablename__ = 'position_subdivision'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey('positions.id'))
    subdivision_id = Column(Integer, ForeignKey('subdivisions.id'))
    
    # Relationships
    position = relationship("Position", back_populates="position_subdivisions")
    subdivision = relationship("Subdivision", back_populates="position_subdivisions")
    employees = relationship("Employee", back_populates="position_subdivision")

class Employee(Base):
    """Employee assignments - links personnel to ranks, subdivisions, and positions"""
    __tablename__ = 'employees'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rank_id = Column(Integer, ForeignKey('ranks.id'))
    subdivision_id = Column(Integer, ForeignKey('subdivisions.id'))
    position_subdivision_id = Column(Integer, ForeignKey('position_subdivision.id'))
    personnel_id = Column(BigInteger, ForeignKey('personnel.discord_id'))
    
    # Relationships
    rank = relationship("Rank", back_populates="employees")
    subdivision = relationship("Subdivision", back_populates="employees")
    position_subdivision = relationship("PositionSubdivision", back_populates="employees")
    personnel = relationship("Personnel", back_populates="employees")

class Action(Base):
    """Actions reference table for history"""
    __tablename__ = 'actions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    
    # Relationship to history
    history_records = relationship("History", back_populates="action")

class History(Base):
    """History/audit table for tracking all changes"""
    __tablename__ = 'history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    action_date = Column(DateTime(timezone=True), server_default=func.now())
    details = Column(Text)
    performed_by = Column(String(200))
    action_id = Column(Integer, ForeignKey('actions.id'))
    personnel_id = Column(BigInteger, ForeignKey('personnel.discord_id'))
    changes = Column(Text)  # JSON string of changes
    
    # Relationships
    action = relationship("Action", back_populates="history_records")
    personnel = relationship("Personnel")

class Blacklist(Base):
    """Blacklist/penalties table"""
    __tablename__ = 'blacklist'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reason = Column(String(500))
    start_date = Column(Date)
    end_date = Column(Date)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    personnel_id = Column(BigInteger, ForeignKey('personnel.discord_id'))
    added_by = Column(String(200))
    
    # Relationship to personnel
    personnel = relationship("Personnel")