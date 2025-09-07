"""
Flask API Configuration Management
Handles different environments (development, testing, production)
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from dynaconf import Dynaconf

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent

# Dynaconf settings for configuration management
settings = Dynaconf(
    envvar_prefix="FLASK",
    settings_files=[BASE_DIR / "settings.toml", BASE_DIR / "settings.local.toml"],
    environments=True,
    env_switcher="FLASK_ENV",
    load_dotenv=False,  # Already loaded above
    merge_enabled=True,
)

class Config:
    """Base configuration class"""
    
    # Application settings
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or settings.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    TESTING = os.environ.get('TESTING', 'False').lower() == 'true'
    ENV = os.environ.get('FLASK_ENV', 'development')
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or settings.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 20,
        'max_overflow': 10,
        'pool_timeout': 30,
    }
    
    # Redis/Caching settings
    REDIS_URL = os.environ.get('REDIS_URL') or settings.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Discord settings
    DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
    DISCORD_CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID')
    DISCORD_CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET')
    DISCORD_REDIRECT_URI = os.environ.get('DISCORD_REDIRECT_URI', 'http://localhost:3000/auth/callback')
    DISCORD_GUILD_ID = os.environ.get('DISCORD_GUILD_ID')
    DISCORD_API_BASE_URL = 'https://discord.com/api/v10'
    
    # OAuth2 settings for Discord authentication
    OAUTH2_SCOPES = ['identify', 'guilds']
    OAUTH2_PKCE_METHOD = 'S256'
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or settings.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    JWT_REFRESH_TOKEN_EXPIRES = int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', 2592000))
    JWT_ALGORITHM = 'HS256'
    # Cookie-based JWT transport (compliance hardening)
    JWT_TOKEN_LOCATION = tuple(os.environ.get('JWT_TOKEN_LOCATION', 'headers,cookies').split(','))
    JWT_COOKIE_SECURE = os.environ.get('JWT_COOKIE_SECURE', 'True').lower() == 'true'
    JWT_COOKIE_SAMESITE = os.environ.get('JWT_COOKIE_SAMESITE', 'Lax')
    JWT_COOKIE_CSRF_PROTECT = os.environ.get('JWT_COOKIE_CSRF_PROTECT', 'True').lower() == 'true'
    JWT_COOKIE_PATH = os.environ.get('JWT_COOKIE_PATH', '/')
    JWT_COOKIE_DOMAIN = os.environ.get('JWT_COOKIE_DOMAIN') or None
    
    # Rate limiting settings
    RATE_LIMIT_STORAGE_URI = os.environ.get('RATE_LIMIT_STORAGE_URL', 'memory://')
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', 60))
    RATE_LIMIT_PER_HOUR = int(os.environ.get('RATE_LIMIT_PER_HOUR', 1000))
    
    # External API settings
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
    OPENROUTER_BASE_URL = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    LLM_DEFAULT_MODEL = os.environ.get('LLM_DEFAULT_MODEL', 'deepseek/deepseek-chat')
    LLM_FALLBACK_MODEL = os.environ.get('LLM_FALLBACK_MODEL', 'anthropic/claude-3-haiku')
    LLM_MAX_CONTEXT_MESSAGES = int(os.environ.get('LLM_MAX_CONTEXT_MESSAGES', 20))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', 1000))
    
    # Media APIs
    TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
    TMDB_BASE_URL = 'https://api.themoviedb.org/3'
    ANILIST_CLIENT_ID = os.environ.get('ANILIST_CLIENT_ID')
    ANILIST_CLIENT_SECRET = os.environ.get('ANILIST_CLIENT_SECRET')
    ANILIST_BASE_URL = 'https://graphql.anilist.co'
    TVDB_API_KEY = os.environ.get('TVDB_API_KEY')
    TVDB_PIN = os.environ.get('TVDB_PIN')
    TVDB_BASE_URL = 'https://api.thetvdb.com/v4'
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',')
    CORS_ALLOW_HEADERS = ['Content-Type', 'Authorization', 'X-Requested-With']
    CORS_EXPOSE_HEADERS = ['Content-Range']
    CORS_ALLOW_CREDENTIALS = True
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH']
    
    # Logging settings
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('API_LOG_FILE', 'logs/api.log')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Feature flags
    FEATURE_STATISTICS = os.environ.get('FEATURE_STATISTICS', 'true').lower() == 'true'
    FEATURE_GIVEAWAYS = os.environ.get('FEATURE_GIVEAWAYS', 'true').lower() == 'true'
    FEATURE_MEDIA_SEARCH = os.environ.get('FEATURE_MEDIA_SEARCH', 'true').lower() == 'true'
    FEATURE_LLM_CHAT = os.environ.get('FEATURE_LLM_CHAT', 'true').lower() == 'true'
    FEATURE_EMBED_MANAGEMENT = os.environ.get('FEATURE_EMBED_MANAGEMENT', 'true').lower() == 'true'
    FEATURE_WATCH_PARTIES = os.environ.get('FEATURE_WATCH_PARTIES', 'true').lower() == 'true'
    
    # Pagination defaults
    PAGINATION_PAGE_SIZE = 20
    PAGINATION_MAX_PAGE_SIZE = 100
    
    # Security settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    # CSP used by Flask-Talisman (override in env for production)
    CONTENT_SECURITY_POLICY = os.environ.get(
        'CONTENT_SECURITY_POLICY',
        "default-src 'self'; img-src 'self' data: https:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    )
    
    # Health check settings
    HEALTH_CHECK_ENABLED = True
    HEALTH_CHECK_INTERVAL = 30
    
    # API versioning
    API_VERSION = 'v1'
    API_PREFIX = f'/api/{API_VERSION}'
    
    def __repr__(self):
        return f'<Config {self.ENV}>'
    
    @classmethod
    def from_env(cls, env: str = None) -> 'Config':
        """Factory method to create config based on environment"""
        env = env or cls.ENV
        config_class = getattr(cls, f'{env.upper()}Config', cls)
        return config_class()


class DevelopmentConfig(Config):
    """Development configuration"""
    
    DEBUG = True
    TESTING = False
    ENV = 'development'
    
    # Use SQLite for development (optional)
    # SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'dev.db')
    
    # Extended logging for development
    LOG_LEVEL = 'DEBUG'
    
    # Disable rate limiting in development
    RATE_LIMIT_PER_MINUTE = 1000
    RATE_LIMIT_PER_HOUR = 10000
    
    # CORS for all origins in development
    CORS_ORIGINS = ['*']


class TestingConfig(Config):
    """Testing configuration"""
    
    DEBUG = False
    TESTING = True
    ENV = 'testing'
    
    # Use test database
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite:///:memory:'
    
    # Disable rate limiting for tests
    RATE_LIMIT_STORAGE_URI = 'memory://'
    RATE_LIMIT_PER_MINUTE = 10000
    RATE_LIMIT_PER_HOUR = 100000
    
    # WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    
    # Logging to console only
    LOG_LEVEL = 'WARNING'


class ProductionConfig(Config):
    """Production configuration"""
    
    DEBUG = False
    TESTING = False
    ENV = 'production'
    
    # Enable secure cookies in production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Security headers
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SSL_STRICT = True
    
    # More restrictive CORS
    CORS_ALLOW_CREDENTIALS = True
    
    # Production logging
    LOG_LEVEL = 'INFO'
    
    # Redis for production rate limiting
    RATE_LIMIT_STORAGE_URI = os.environ.get('RATE_LIMIT_STORAGE_URL', 'redis://redis:6379/0')


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(env: Optional[str] = None) -> Config:
    """
    Get configuration based on environment variable or default to development.
    
    Args:
        env: Environment name (optional)
    
    Returns:
        Config instance
    """
    env = env or os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])()


if __name__ == '__main__':
    # Example usage
    cfg = get_config()
    print(f"Environment: {cfg.ENV}")
    print(f"Debug: {cfg.DEBUG}")
    print(f"Database URI: {cfg.SQLALCHEMY_DATABASE_URI[:50]}...")
    print(f"CORS Origins: {cfg.CORS_ORIGINS}")