"""
Database Models for Flask API
SQLAlchemy ORM models based on PostgreSQL schema
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, DateTime, Text, JSON, ForeignKey,
    CheckConstraint, Index, func, event, text
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from pydantic import BaseModel, validator
from . import db
from .types import EncryptedText

Base = declarative_base()

# Pydantic schemas for validation
class UserBase(BaseModel):
    username: str
    global_name: Optional[str] = None
    avatar_hash: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    user_id: int
    is_bot_admin: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EmbedTemplateBase(BaseModel):
    template_name: str
    embed_json: Dict[str, Any]
    description: Optional[str] = None

class EmbedTemplateCreate(EmbedTemplateBase):
    pass

class EmbedTemplateResponse(EmbedTemplateBase):
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    version: int

    class Config:
        from_attributes = True

class GiveawayBase(BaseModel):
    prize: str
    winner_count: int = 1
    channel_id: int
    start_at: datetime
    end_at: datetime
    description: Optional[str] = None
    required_role_id: Optional[int] = None
    max_entries_per_user: Optional[int] = 1

class GiveawayCreate(GiveawayBase):
    pass

class GiveawayResponse(GiveawayBase):
    id: int
    message_id: Optional[int]
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    entries_count: int = 0

    class Config:
        from_attributes = True


# Database Models
class User(Base, UserBase):
    """User model for authentication and RBAC"""
    __tablename__ = 'Users'
    
    # Primary key
    user_id = Column(BigInteger, primary_key=True, index=True)
    
    # User profile data
    username = Column(String(32), nullable=False, index=True)
    global_name = Column(String(32))
    avatar_hash = Column(String(255))
    is_bot_admin = Column(Boolean, default=False)
    last_login = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    embed_templates = relationship("EmbedTemplate", backref="creator", lazy='dynamic')
    posted_messages = relationship("PostedMessage", backref="poster", lazy='dynamic')
    giveaways_created = relationship("Giveaway", backref="creator", lazy='dynamic')
    conversation_history = relationship("ConversationHistory", backref="user", lazy='dynamic')
    giveaway_entries = relationship("GiveawayEntry", backref="entrant", lazy='dynamic')
    tracked_shows = relationship("TrackShow", backref="tracker", lazy='dynamic')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return UserResponse(
            user_id=self.user_id,
            username=self.username,
            global_name=self.global_name,
            avatar_hash=self.avatar_hash,
            is_bot_admin=self.is_bot_admin,
            last_login=self.last_login,
            created_at=self.created_at,
            updated_at=self.updated_at
        ).model_dump()
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission based on roles"""
        # This would integrate with RBAC system
        if self.is_bot_admin:
            return True
        
        # Fetch roles from Discord and check permissions
        # Implementation in auth service
        return False


class AppConfig(Base):
    """Application configuration settings"""
    __tablename__ = 'AppConfig'
    
    key = Column(String(50), primary_key=True)
    value = Column(String(255), nullable=False)
    description = Column(Text)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    @classmethod
    def get(cls, key: str) -> Optional[str]:
        """Get configuration value by key"""
        config = cls.query.filter_by(key=key).first()
        return config.value if config else None
    
    @classmethod
    def set(cls, key: str, value: str, description: str = None) -> 'AppConfig':
        """Set or update configuration value"""
        config = cls.query.filter_by(key=key).first()
        if config:
            config.value = value
            config.description = description
            db.session.commit()
            return config
        else:
            new_config = cls(key=key, value=value, description=description)
            db.session.add(new_config)
            db.session.commit()
            return new_config


class MessageStats(Base):
    """Raw message statistics for aggregation"""
    __tablename__ = 'MessageStats'
    
    message_id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=False, index=True)
    content_length = Column(Integer, default=0)
    has_attachments = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", backref="messages")


class VoiceStats(Base):
    """Voice session statistics"""
    __tablename__ = 'VoiceStats'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    session_start = Column(DateTime(timezone=True), nullable=False, index=True)
    session_end = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Computed property for duration
    @property
    def duration_seconds(self) -> Optional[int]:
        if self.session_end:
            return int((self.session_end - self.session_start).total_seconds())
        return None
    
    user = relationship("User", backref="voice_sessions")


class InviteStats(Base):
    """Invite tracking statistics"""
    __tablename__ = 'InviteStats'
    
    invite_code = Column(String(20), primary_key=True)
    creator_id = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    uses = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), index=True)
    max_uses = Column(Integer)
    is_temporary = Column(Boolean, default=False)
    channel_id = Column(BigInteger)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    creator = relationship("User", backref="created_invites")


class EmbedTemplate(Base, EmbedTemplateBase):
    """Discord embed templates for management"""
    __tablename__ = 'EmbedTemplates'
    
    id = Column(Integer, primary_key=True)
    template_name = Column(String(100), unique=True, nullable=False, index=True)
    embed_json = Column(JSON, nullable=False)
    created_by = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    description = Column(Text)
    
    # Validation
    @validator('embed_json')
    def validate_embed_json(cls, v):
        """Validate Discord embed JSON structure"""
        from .utils import validate_discord_embed
        return validate_discord_embed(v)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return EmbedTemplateResponse(
            id=self.id,
            template_name=self.template_name,
            embed_json=self.embed_json,
            created_by=self.created_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
            is_active=self.is_active,
            version=self.version,
            description=self.description
        ).model_dump()
    
    def increment_version(self):
        """Increment template version for updates"""
        self.version += 1
        self.updated_at = func.now()


class PostedMessage(Base):
    """Posted Discord messages from templates"""
    __tablename__ = 'PostedMessages'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(BigInteger, unique=True, nullable=False)
    channel_id = Column(BigInteger, nullable=False, index=True)
    template_id = Column(Integer, ForeignKey('EmbedTemplates.id'), index=True)
    posted_by = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    posted_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_edited_at = Column(DateTime(timezone=True))
    edit_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))
    
    template = relationship("EmbedTemplate", backref="posted_messages")
    poster = relationship("User", backref="posted_messages")


class ConversationHistory(Base):
    """LLM chatbot conversation memory"""
    __tablename__ = 'ConversationHistory'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    role = Column(String(10), nullable=False, index=True)  # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    message_tokens = Column(Integer, default=0)
    response_tokens = Column(Integer, default=0)
    model_used = Column(String(100))
    conversation_thread = Column(String(255), index=True)
    
    user = relationship("User", backref="conversation_history")
    
    @classmethod
    def get_recent_conversation(cls, user_id: int, limit: int = 20) -> List['ConversationHistory']:
        """Get recent conversation history for a user"""
        return cls.query.filter_by(user_id=user_id)\
                       .order_by(cls.created_at.desc())\
                       .limit(limit)\
                       .all()
    
    @classmethod
    def cleanup_old_conversations(cls, user_id: int, days: int = 30):
        """Clean up old conversation history"""
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = cls.query.filter(
            cls.user_id == user_id,
            cls.role == 'user',
            cls.created_at < cutoff_date
        ).delete()
        db.session.commit()
        return deleted_count


from datetime import timedelta
class Giveaway(Base, GiveawayBase):
    """Giveaway management system"""
    __tablename__ = 'Giveaways'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(BigInteger, unique=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    prize = Column(Text, nullable=False)
    winner_count = Column(Integer, default=1, nullable=False)
    status = Column(String(20), nullable=False, index=True)  # scheduled, active, ended, cancelled
    start_at = Column(DateTime(timezone=True), nullable=False, index=True)
    end_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_by = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    required_role_id = Column(BigInteger)
    max_entries_per_user = Column(Integer, default=1)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", backref="giveaways_created")
    entries = relationship("GiveawayEntry", backref="giveaway", cascade="all, delete-orphan")
    winners = relationship("GiveawayWinner", backref="giveaway", cascade="all, delete-orphan")
    
    @property
    def entries_count(self) -> int:
        """Get number of entries for this giveaway"""
        return len(self.entries)
    
    @property
    def is_active(self) -> bool:
        """Check if giveaway is currently active"""
        now = datetime.utcnow()
        return self.status == 'active' and self.start_at <= now <= self.end_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return GiveawayResponse(
            id=self.id,
            prize=self.prize,
            winner_count=self.winner_count,
            channel_id=self.channel_id,
            start_at=self.start_at,
            end_at=self.end_at,
            status=self.status,
            created_by=self.created_by,
            required_role_id=self.required_role_id,
            max_entries_per_user=self.max_entries_per_user,
            description=self.description,
            created_at=self.created_at,
            updated_at=self.updated_at,
            entries_count=self.entries_count
        ).model_dump()


class GiveawayEntry(Base):
    """Giveaway participant entries"""
    __tablename__ = 'GiveawayEntries'
    
    id = Column(Integer, primary_key=True)
    giveaway_id = Column(Integer, ForeignKey('Giveaways.id'), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    entered_at = Column(DateTime(timezone=True), default=func.now())
    is_winner = Column(Boolean, default=False)
    won_at = Column(DateTime(timezone=True))
    
    # Relationships
    giveaway = relationship("Giveaway", backref="entries")
    user = relationship("User", backref="giveaway_entries")
    
    __table_args__ = (
        Index('ix_giveaway_entries_giveaway_user', giveaway_id, user_id),
    )


class GiveawayWinner(Base):
    """Giveaway winners tracking"""
    __tablename__ = 'GiveawayWinners'
    
    id = Column(Integer, primary_key=True)
    giveaway_id = Column(Integer, ForeignKey('Giveaways.id'), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    announced_at = Column(DateTime(timezone=True), default=func.now())
    prize_received = Column(Boolean, default=False)
    
    # Relationships
    giveaway = relationship("Giveaway", backref="winners")
    user = relationship("User", backref="giveaway_wins")
    
    __table_args__ = (
        Index('ix_giveaway_winners_giveaway_user', giveaway_id, user_id),
    )


class TrackShow(Base):
    """Media show tracking for release notifications"""
    __tablename__ = 'TrackShows'
    
    id = Column(Integer, primary_key=True)
    show_id = Column(String(100), nullable=False)
    user_id = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    api_source = Column(String(20), nullable=False, index=True)  # tmdb, anilist, tvdb
    show_title = Column(String(255), nullable=False)
    show_type = Column(String(20))  # tv, anime
    last_checked = Column(DateTime(timezone=True), default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    is_active = Column(Boolean, default=True)
    notification_channel_id = Column(BigInteger)
    
    # Relationships
    user = relationship("User", backref="tracked_shows")
    
    __table_args__ = (
        Index('ix_track_shows_user_source', user_id, api_source),
        Index('ix_track_shows_active', 'is_active', postgresql_where=text("is_active = true")),
    )
    
    @classmethod
    def get_active_tracks(cls) -> List['TrackShow']:
        """Get all active show tracks for daily checking"""
        return cls.query.filter_by(is_active=True).all()


class MediaSearchHistory(Base):
    """Media search history tracking"""
    __tablename__ = 'MediaSearchHistory'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('Users.user_id'), index=True)
    # At-rest encryption for search queries (PII minimization)
    query = Column(EncryptedText(), nullable=False)
    media_type = Column(String(20), nullable=False)
    api_source = Column(String(20), nullable=False)
    results_count = Column(Integer, default=0)
    searched_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    
    user = relationship("User", backref="search_history")


class WatchPartyEvent(Base):
    """Discord watch party events"""
    __tablename__ = 'WatchPartyEvents'
    
    id = Column(Integer, primary_key=True)
    event_id = Column(BigInteger, unique=True, nullable=False)
    guild_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    scheduled_start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    privacy_level = Column(String(20), default='2')  # 1=private, 2=server_only, 3=public
    creator_id = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    media_poster_url = Column(String(500))
    rsvp_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now())
    status = Column(String(20), default='scheduled', index=True)
    
    # Relationships
    creator = relationship("User", backref="created_watch_parties")
    rsvps = relationship("WatchPartyRSVP", backref="event", cascade="all, delete-orphan")
    
    @property
    def is_upcoming(self) -> bool:
        """Check if event is upcoming"""
        return self.status == 'scheduled' and self.scheduled_start_time > datetime.utcnow()
    
    @property
    def needs_reminder(self) -> bool:
        """Check if reminder should be sent (30 minutes before)"""
        now = datetime.utcnow()
        thirty_min_before = self.scheduled_start_time - timedelta(minutes=30)
        return (self.status == 'scheduled' and 
                thirty_min_before <= now <= self.scheduled_start_time)


class WatchPartyRSVP(Base):
    """Watch party RSVP tracking"""
    __tablename__ = 'WatchPartyRSVPs'
    
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey('WatchPartyEvents.id'), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey('Users.user_id'), nullable=False, index=True)
    rsvp_status = Column(String(20), default='going')  # going, interested, declined
    rsvped_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    event = relationship("WatchPartyEvent", backref="rsvps")
    user = relationship("User", backref="watch_party_rsvps")
    
    __table_args__ = (
        Index('ix_watchparty_rsvps_event_user', event_id, user_id),
    )


class AuditLog(Base):
    """Audit logging for security and compliance"""
    __tablename__ = 'AuditLogs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('Users.user_id'), index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50))
    resource_id = Column(BigInteger)
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(INET)
    user_agent = Column(Text)
    success = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    
    user = relationship("User", backref="audit_logs")
    
    @classmethod
    def log_action(cls, user_id: Optional[int], action: str, resource_type: str = None,
                   resource_id: Optional[int] = None, old_values: Dict = None,
                   new_values: Dict = None, ip_address: str = None, 
                   user_agent: str = None, success: bool = True):
        """Log an audit action"""
        audit = cls(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success
        )
        db.session.add(audit)
        db.session.commit()
        return audit


# Materialized Views (managed via raw SQL)
class DailyUserMessageStats(Base):
    """Daily message statistics (materialized view)"""
    __tablename__ = None  # Abstract base for materialized view
    
    @classmethod
    def refresh(cls):
        """Refresh the materialized view"""
        db.session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY DailyUserMessageStats"))
        db.session.commit()


class MonthlyUserVoiceStats(Base):
    """Monthly voice statistics (materialized view)"""
    __tablename__ = None
    
    @classmethod
    def refresh(cls):
        """Refresh the materialized view"""
        db.session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY MonthlyUserVoiceStats"))
        db.session.commit()


# Event listeners for automatic operations
@event.listens_for(User.last_login, 'set')
def update_user_last_login(target, value, oldvalue, initiator):
    """Update user last login timestamp"""
    if value and value != oldvalue:
        target.updated_at = func.now()


@event.listens_for(db.session, 'after_flush')
def cleanup_old_conversations(session, flush_context):
    """Clean up old conversation history after flush"""
    # This would be implemented with a scheduled task in production
    pass


# Model utilities
def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=db.engine)


def drop_tables():
    """Drop all database tables"""
    Base.metadata.drop_all(bind=db.engine)


# Export all models for easy import
__all__ = [
    'User', 'AppConfig', 'MessageStats', 'VoiceStats', 'InviteStats',
    'EmbedTemplate', 'PostedMessage', 'ConversationHistory',
    'Giveaway', 'GiveawayEntry', 'GiveawayWinner',
    'TrackShow', 'MediaSearchHistory', 'WatchPartyEvent', 'WatchPartyRSVP',
    'AuditLog', 'DailyUserMessageStats', 'MonthlyUserVoiceStats',
    'UserBase', 'UserCreate', 'UserResponse',
    'EmbedTemplateBase', 'EmbedTemplateCreate', 'EmbedTemplateResponse',
    'GiveawayBase', 'GiveawayCreate', 'GiveawayResponse'
]