"""
Discord Bot Configuration
Configuration management for the bot worker
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field, validator

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent

class BotSettings(BaseSettings):
    """Bot configuration settings"""
    
    # Bot identification
    BOT_TOKEN: str = Field(..., env='DISCORD_BOT_TOKEN')
    APPLICATION_ID: str = Field(..., env='DISCORD_APPLICATION_ID')
    OWNER_ID: int = Field(..., env='OWNER_ID')
    BOT_PREFIX: str = Field('!', env='BOT_PREFIX')
    
    # Discord server configuration
    DISCORD_GUILD_ID: int = Field(..., env='DISCORD_GUILD_ID')
    NOTIFICATION_CHANNEL_ID: Optional[int] = Field(None, env='NOTIFICATION_CHANNEL_ID')
    GIVEAWAY_CHANNEL_ID: Optional[int] = Field(None, env='GIVEAWAY_CHANNEL_ID')
    MEDIA_RELEASE_CHANNEL_ID: Optional[int] = Field(None, env='MEDIA_RELEASE_CHANNEL_ID')
    
    # Database configuration
    DATABASE_URL: str = Field(..., env='DATABASE_URL')
    DATABASE_POOL_SIZE: int = Field(5, env='DATABASE_POOL_SIZE')
    DATABASE_MAX_OVERFLOW: int = Field(10, env='DATABASE_MAX_OVERFLOW')
    
    # Scheduler configuration
    SCHEDULER_TIMEZONE: str = Field('UTC', env='SCHEDULER_TIMEZONE')
    STATS_AGGREGATION_HOUR: int = Field(2, env='STATS_AGGREGATION_HOUR')
    RELEASE_CHECK_HOUR: int = Field(8, env='RELEASE_CHECK_HOUR')
    STATS_RETENTION_DAYS: int = Field(365, env='STATS_RETENTION_DAYS')
    CONVERSATION_HISTORY_DAYS: int = Field(30, env='CONVERSATION_HISTORY_DAYS')
    
    # External API keys
    OPENROUTER_API_KEY: str = Field(..., env='OPENROUTER_API_KEY')
    OPENROUTER_BASE_URL: str = Field('https://openrouter.ai/api/v1', env='OPENROUTER_BASE_URL')
    LLM_DEFAULT_MODEL: str = Field('deepseek/deepseek-chat', env='LLM_DEFAULT_MODEL')
    LLM_FALLBACK_MODEL: str = Field('anthropic/claude-3-haiku', env='LLM_FALLBACK_MODEL')
    LLM_MAX_CONTEXT_MESSAGES: int = Field(20, env='LLM_MAX_CONTEXT_MESSAGES')
    LLM_MAX_TOKENS: int = Field(1000, env='LLM_MAX_TOKENS')
    LLM_SYSTEM_PROMPT: str = Field('You are a helpful assistant for a media community Discord server.', env='LLM_SYSTEM_PROMPT')
    
    # Media APIs
    TMDB_API_KEY: str = Field(..., env='TMDB_API_KEY')
    TMDB_BASE_URL: str = Field('https://api.themoviedb.org/3', env='TMDB_BASE_URL')
    
    ANILIST_CLIENT_ID: str = Field(..., env='ANILIST_CLIENT_ID')
    ANILIST_CLIENT_SECRET: str = Field(..., env='ANILIST_CLIENT_SECRET')
    ANILIST_BASE_URL: str = Field('https://graphql.anilist.co', env='ANILIST_BASE_URL')
    
    TVDB_API_KEY: str = Field(..., env='TVDB_API_KEY')
    TVDB_PIN: str = Field(..., env='TVDB_PIN')
    TVDB_BASE_URL: str = Field('https://api.thetvdb.com/v4', env='TVDB_BASE_URL')
    
    # Logging configuration
    LOG_LEVEL: str = Field('INFO', env='LOG_LEVEL')
    LOG_FILE: Optional[str] = Field(None, env='BOT_LOG_FILE')
    LOG_FORMAT: str = Field('%(asctime)s - %(name)s - %(levelname)s - %(message)s', env='LOG_FORMAT')
    
    # Discord API configuration
    DISCORD_API_BASE_URL: str = Field('https://discord.com/api/v10', env='DISCORD_API_BASE_URL')
    COMMAND_SYNC_GUILD_ONLY: bool = Field(False, env='COMMAND_SYNC_GUILD_ONLY')
    
    # Rate limiting and caching
    REDIS_URL: Optional[str] = Field(None, env='REDIS_URL')
    RATE_LIMIT_PER_USER: int = Field(10, env='RATE_LIMIT_PER_USER')
    RATE_LIMIT_WINDOW: int = Field(60, env='RATE_LIMIT_WINDOW')  # seconds
    
    # Feature flags
    ENABLE_STATISTICS: bool = Field(True, env='FEATURE_STATISTICS')
    ENABLE_GIVEAWAYS: bool = Field(True, env='FEATURE_GIVEAWAYS')
    ENABLE_MEDIA_SEARCH: bool = Field(True, env='FEATURE_MEDIA_SEARCH')
    ENABLE_LLM_CHAT: bool = Field(True, env='FEATURE_LLM_CHAT')
    ENABLE_EMBED_MANAGEMENT: bool = Field(True, env='FEATURE_EMBED_MANAGEMENT')
    ENABLE_WATCH_PARTIES: bool = Field(True, env='FEATURE_WATCH_PARTIES')
    
    # Giveaway settings
    MAX_GIVEAWAY_WINNERS: int = Field(10, env='MAX_GIVEAWAY_WINNERS')
    MIN_GIVEAWAY_DURATION: int = Field(300, env='MIN_GIVEAWAY_DURATION')  # 5 minutes in seconds
    MAX_GIVEAWAY_DURATION: int = Field(2592000, env='MAX_GIVEAWAY_DURATION')  # 30 days in seconds
    
    # Media search settings
    MAX_SEARCH_RESULTS: int = Field(10, env='MAX_SEARCH_RESULTS')
    DEFAULT_MEDIA_PAGE_SIZE: int = Field(5, env='DEFAULT_MEDIA_PAGE_SIZE')
    
    # LLM settings
    LLM_RATE_LIMIT_PER_MINUTE: int = Field(5, env='LLM_RATE_LIMIT_PER_MINUTE')
    LLM_CONVERSATION_MEMORY_LIMIT: int = Field(50, env='LLM_CONVERSATION_MEMORY_LIMIT')
    
    # Statistics settings
    STATS_AGGREGATION_BATCH_SIZE: int = Field(1000, env='STATS_AGGREGATION_BATCH_SIZE')
    VOICE_SESSION_TIMEOUT: int = Field(300, env='VOICE_SESSION_TIMEOUT')  # 5 minutes
    
    # Watch party settings
    WATCH_PARTY_REMINDER_MINUTES: int = Field(30, env='WATCH_PARTY_REMINDER_MINUTES')
    MAX_WATCH_PARTY_RSVPS: int = Field(100, env='MAX_WATCH_PARTY_RSVPS')
    
    # Error handling and recovery
    MAX_RECONNECT_ATTEMPTS: int = Field(5, env='MAX_RECONNECT_ATTEMPTS')
    RECONNECT_DELAY: int = Field(5, env='RECONNECT_DELAY')  # seconds
    COMMAND_ERROR_COOLDOWN: int = Field(30, env='COMMAND_ERROR_COOLDOWN')
    
    # Security settings
    ENABLE_DM_COMMANDS: bool = Field(False, env='ENABLE_DM_COMMANDS')
    RESTRICT_COMMANDS_TO_GUILD: bool = Field(True, env='RESTRICT_COMMANDS_TO_GUILD')
    
    # Development settings
    DEBUG: bool = Field(False, env='DEBUG')
    DEVELOPMENT_GUILD_ID: Optional[int] = Field(None, env='DEVELOPMENT_GUILD_ID')
    
    # Performance settings
    MAX_CONCURRENT_COMMANDS: int = Field(10, env='MAX_CONCURRENT_COMMANDS')
    COMMAND_TIMEOUT: int = Field(30, env='COMMAND_TIMEOUT')  # seconds
    
    # Notification settings
    ENABLE_NEW_RELEASE_NOTIFICATIONS: bool = Field(True, env='ENABLE_NEW_RELEASE_NOTIFICATIONS')
    NOTIFICATION_COOLDOWN: int = Field(3600, env='NOTIFICATION_COOLDOWN')  # 1 hour
    
    class Config:
        env_file = '.env'
        case_sensitive = False
        extra = 'ignore'
    
    @validator('BOT_TOKEN')
    def validate_bot_token(cls, v):
        if not v or v.startswith('your_bot_token_here'):
            raise ValueError('BOT_TOKEN must be set to a valid Discord bot token')
        return v
    
    @validator('DISCORD_GUILD_ID')
    def validate_guild_id(cls, v):
        if not v or v <= 0:
            raise ValueError('DISCORD_GUILD_ID must be a valid Discord guild ID')
        return v
    
    @validator('DATABASE_URL')
    def validate_database_url(cls, v):
        if not v or v.startswith('your_database_url_here'):
            raise ValueError('DATABASE_URL must be set to a valid PostgreSQL connection string')
        return v
    
    @validator('OPENROUTER_API_KEY')
    def validate_openrouter_key(cls, v):
        if not v or v.startswith('your_openrouter_api_key_here'):
            raise ValueError('OPENROUTER_API_KEY must be set to a valid OpenRouter API key')
        return v
    
    @validator('TMDB_API_KEY')
    def validate_tmdb_key(cls, v):
        if not v or v.startswith('your_tmdb_api_key_here'):
            raise ValueError('TMDB_API_KEY must be set to a valid TMDB API key')
        return v
    
    @validator('TVDB_API_KEY')
    def validate_tvdb_key(cls, v):
        if not v or v.startswith('your_tvdb_api_key_here'):
            raise ValueError('TVDB_API_KEY must be set to a valid TVDB API key')
        return v
    
    @validator('TVDB_PIN')
    def validate_tvdb_pin(cls, v):
        if not v or v.startswith('your_tvdb_pin_here'):
            raise ValueError('TVDB_PIN must be set to a valid TVDB PIN')
        return v


class DevelopmentSettings(BotSettings):
    """Development configuration overrides"""
    
    DEBUG: bool = True
    LOG_LEVEL: str = 'DEBUG'
    DEVELOPMENT_GUILD_ID: Optional[int] = Field(..., env='DEVELOPMENT_GUILD_ID')
    
    # More permissive settings for development
    RATE_LIMIT_PER_USER: int = 100
    LLM_RATE_LIMIT_PER_MINUTE: int = 20
    MAX_CONCURRENT_COMMANDS: int = 20
    
    # Use in-memory database for testing
    DATABASE_URL: str = Field('sqlite:///./dev_bot.db', env='DATABASE_URL')


class ProductionSettings(BotSettings):
    """Production configuration overrides"""
    
    DEBUG: bool = False
    LOG_LEVEL: str = 'INFO'
    
    # More restrictive settings for production
    RATE_LIMIT_PER_USER: int = 5
    LLM_RATE_LIMIT_PER_MINUTE: int = 3
    MAX_CONCURRENT_COMMANDS: int = 5
    
    # Security settings
    ENABLE_DM_COMMANDS: bool = False
    RESTRICT_COMMANDS_TO_GUILD: bool = True
    
    # Production database with connection pooling
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30


def get_config(environment: str = 'production') -> Dict[str, Any]:
    """
    Get bot configuration based on environment
    
    Args:
        environment: Environment name ('development', 'production', 'testing')
    
    Returns:
        Configuration dictionary
    """
    if environment == 'development':
        settings = DevelopmentSettings()
    elif environment == 'production':
        settings = ProductionSettings()
    else:
        # Default to production for unknown environments
        settings = ProductionSettings()
    
    # Convert Pydantic model to dictionary
    config_dict = settings.model_dump()
    
    # Add computed values
    config_dict['BOT_STARTED_AT'] = datetime.utcnow()
    config_dict['BASE_DIR'] = str(BASE_DIR)
    
    # Log configuration (without sensitive data)
    log_config = {k: v for k, v in config_dict.items() if not k.endswith('_KEY') and k != 'BOT_TOKEN'}
    logger.info("Bot configuration loaded", environment=environment, config=log_config)
    
    return config_dict


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate that required configuration is present
    
    Args:
        config: Configuration dictionary
    
    Returns:
        True if configuration is valid, False otherwise
    """
    required_keys = [
        'BOT_TOKEN', 'APPLICATION_ID', 'OWNER_ID', 'DISCORD_GUILD_ID', 
        'DATABASE_URL', 'OPENROUTER_API_KEY', 'TMDB_API_KEY',
        'TVDB_API_KEY', 'TVDB_PIN'
    ]
    
    missing_keys = [key for key in required_keys if not config.get(key)]
    
    if missing_keys:
        logger.error("Missing required configuration keys", missing=missing_keys)
        return False
    
    # Validate Discord IDs
    try:
        int(config['DISCORD_GUILD_ID'])
        int(config['OWNER_ID'])
    except (ValueError, TypeError):
        logger.error("Invalid Discord ID format", guild_id=config.get('DISCORD_GUILD_ID'), owner_id=config.get('OWNER_ID'))
        return False
    
    logger.info("Configuration validation passed")
    return True


# Global configuration instance
settings = get_config(os.getenv('BOT_ENV', 'production'))

if __name__ == '__main__':
    # Validate configuration on startup
    if not validate_config(settings):
        print("Configuration validation failed. Please check your environment variables.")
        sys.exit(1)
    
    print(f"Bot Configuration: {settings['BOT_ENV'] if 'BOT_ENV' in settings else 'production'}")
    print(f"Guild ID: {settings['DISCORD_GUILD_ID']}")
    print(f"Database: {settings['DATABASE_URL'][:30]}...")
    print("Configuration loaded successfully")