"""
Flask API Application Factory
Main application initialization and configuration
"""
import logging
import os
from pathlib import Path
from flask import Flask, request, g
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_restx import Api
from flask_caching import Cache
from flask_talisman import Talisman
from werkzeug.exceptions import HTTPException
from structlog import configure, get_logger, processors, stdlib
import redis

from .config import get_config
from . import auth, embeds, stats, giveaways, media, llm, users, health, errors
from .middleware import rbac_middleware, audit_middleware
from .utils import discord_oauth, embed_validator, rate_limiter

# Global extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)
cache = Cache()
talisman = Talisman()
api = Api(
    title='Discord Bot Platform API',
    version='1.0.0',
    description='REST API for Discord bot management platform',
    doc='/docs'
)
logger = get_logger()

# Configure structlog for structured logging
def setup_logging(app: Flask):
    """Configure structured logging for the application"""
    # Configure structlog
    configure(
        processors=[processors.add_log_level, processors.TimeStamper(fmt="iso"), stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=stdlib.LoggerFactory(),
        wrapper_class=stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure Python logging
    log_level = getattr(logging, app.config['LOG_LEVEL'])
    logging.basicConfig(
        level=log_level,
        format=app.config.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Configure Flask logger
    app.logger.setLevel(log_level)
    
    # Add file handler if LOG_FILE is configured
    if app.config.get('LOG_FILE'):
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(
            app.config['LOG_FILE'], 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        handler.setFormatter(logging.Formatter(app.config['LOG_FORMAT']))
        app.logger.addHandler(handler)
    
    # Log application startup
    app.logger.info(f'Flask API starting in {app.config["ENV"]} mode')
    logger.info("Application initialized", env=app.config["ENV"], debug=app.config["DEBUG"])


def create_app(config_name: str = None) -> Flask:
    """
    Application factory function
    
    Args:
        config_name: Configuration environment name (development, testing, production)
    
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cache.init_app(app, config={
        'CACHE_TYPE': 'redis',
        'CACHE_REDIS_URL': app.config.get('REDIS_URL', 'redis://redis:6379/0'),
        'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes default
        'CACHE_KEY_PREFIX': 'api:'
    })

    # Initialize Talisman for HSTS/CSP and security headers
    talisman.init_app(
        app,
        force_https=(app.config['ENV'] == 'production'),
        strict_transport_security=True,
        strict_transport_security_max_age=31536000,
        content_security_policy=app.config.get('CONTENT_SECURITY_POLICY', "default-src 'self'"),
        frame_options='DENY',
        referrer_policy='no-referrer'
    )

    # Token store (Redis) for JWT blocklist/refresh token management
    try:
        app.extensions['token_store'] = redis.Redis.from_url(
            app.config.get('REDIS_URL', 'redis://redis:6379/0'),
            decode_responses=True
        )
    except Exception:
        app.extensions['token_store'] = None

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        store = app.extensions.get('token_store')
        if not store:
            return False
        jti = jwt_payload.get('jti')
        if not jti:
            return False
        try:
            return store.exists(f"jwt:blocklist:{jti}") == 1
        except Exception:
            return False

    setup_cors(app)
    setup_limiter(app)
    setup_logging(app)
    setup_error_handlers(app)
    setup_blueprints(app)
    setup_middleware(app)
    setup_health_checks(app)
    
    # Configure JWT token verification
    @jwt.user_identity_loader
    def user_identity_lookup(user):
        """JWT user identity loader"""
        return user.get('sub')  # Discord user ID
    
    @jwt.user_lookup_loader
    def user_lookup_callback(jwt_token):
        """JWT user lookup callback"""
        return jwt_token
    
    # Configure API documentation
    setup_api_docs(app)
    
    # Run database migrations on startup (development only)
    if app.config['ENV'] == 'development':
        with app.app_context():
            from alembic import command
            try:
                command.upgrade('head', config='alembic.ini')
                logger.info("Database migrations applied successfully")
            except Exception as e:
                logger.error("Failed to apply migrations", error=str(e))
    
    return app


def setup_cors(app: Flask):
    """Configure CORS for the application"""
    cors = CORS(
        app,
        origins=app.config['CORS_ORIGINS'],
        allow_headers=app.config['CORS_ALLOW_HEADERS'],
        expose_headers=app.config['CORS_EXPOSE_HEADERS'],
        allow_credentials=app.config['CORS_ALLOW_CREDENTIALS'],
        methods=app.config['CORS_METHODS']
    )
    logger.info("CORS configured", origins=app.config['CORS_ORIGINS'])


def setup_limiter(app: Flask):
    """Configure rate limiting"""
    global limiter
    limiter.init_app(app)
    limiter.storage_uri = app.config['RATE_LIMIT_STORAGE_URI']
    
    # Apply default rate limits to all routes
    app.before_request(limiter.limit("100 per minute", key_func=get_remote_address))
    
    # Specific rate limits for sensitive endpoints
    @limiter.limit("10 per minute")
    @app.before_request
    def auth_rate_limit():
        if '/auth/' in request.path:
            return True
    
    logger.info("Rate limiting configured", storage=app.config['RATE_LIMIT_STORAGE_URI'])


def setup_blueprints(app: Flask):
    """Register all blueprints with the application"""
    # Health check blueprint (no auth required)
    app.register_blueprint(health.bp, url_prefix='/health')
    
    # API blueprints with version prefix
    api_prefix = app.config['API_PREFIX']
    
    # Auth blueprint
    app.register_blueprint(auth.bp, url_prefix=f'{api_prefix}/auth')
    
    # User management (requires auth)
    app.register_blueprint(users.bp, url_prefix=f'{api_prefix}/users')
    
    # Feature blueprints
    if app.config['FEATURE_EMBED_MANAGEMENT']:
        app.register_blueprint(embeds.bp, url_prefix=f'{api_prefix}/embeds')
    
    if app.config['FEATURE_STATISTICS']:
        app.register_blueprint(stats.bp, url_prefix=f'{api_prefix}/stats')
    
    if app.config['FEATURE_GIVEAWAYS']:
        app.register_blueprint(giveaways.bp, url_prefix=f'{api_prefix}/giveaways')
    
    if app.config['FEATURE_MEDIA_SEARCH']:
        app.register_blueprint(media.bp, url_prefix=f'{api_prefix}/media')
    
    if app.config['FEATURE_LLM_CHAT']:
        app.register_blueprint(llm.bp, url_prefix=f'{api_prefix}/llm')
    
    logger.info("Blueprints registered", prefix=api_prefix)


def setup_middleware(app: Flask):
    """Configure application middleware"""
    # RBAC middleware for protected routes
    rbac_middleware.init_app(app)
    
    # Audit logging middleware
    audit_middleware.init_app(app)
    
    # Request logging
    @app.before_request
    def log_request():
        logger.info(
            "Incoming request",
            method=request.method,
            path=request.path,
            remote_addr=get_remote_address(request),
            user_agent=request.headers.get('User-Agent', '')
        )
    
    # Response logging
    @app.after_request
    def log_response(response):
        # Prevent caching of sensitive endpoints
        sensitive_prefixes = ['/api/v1/auth', '/api/v1/users', '/api/v1/llm']
        if any(request.path.startswith(p) for p in sensitive_prefixes):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Vary'] = 'Authorization'

        # If Authorization header is present, ensure caches vary by it
        if request.headers.get('Authorization'):
            existing_vary = response.headers.get('Vary')
            response.headers['Vary'] = 'Authorization' if not existing_vary else f"{existing_vary}, Authorization"

        # Defensive security headers
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')

        logger.info(
            "Response sent",
            status=response.status_code,
            content_length=response.content_length
        )
        return response


def setup_error_handlers(app: Flask):
    """Configure global error handlers"""
    # 404 handler
    @app.errorhandler(404)
    def not_found(error):
        return errors.api_error_response(404, "Resource not found"), 404
    
    # 500 handler
    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error", exc_info=error)
        return errors.api_error_response(500, "Internal server error"), 500
    
    # HTTP exception handler
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        logger.warning(f"HTTP error: {error.description}", status_code=error.code)
        return errors.api_error_response(error.code, error.description), error.code
    
    # JSON serialization error
    @app.errorhandler(400)
    def bad_request(error):
        return errors.api_error_response(400, "Bad request"), 400
    
    # Unauthorized access
    @app.errorhandler(401)
    def unauthorized(error):
        return errors.api_error_response(401, "Unauthorized"), 401
    
    # Forbidden access
    @app.errorhandler(403)
    def forbidden(error):
        logger.warning("Access forbidden", details=str(error))
        return errors.api_error_response(403, "Forbidden"), 403
    
    # Rate limit exceeded
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return errors.api_error_response(429, "Rate limit exceeded"), 429


def setup_health_checks(app: Flask):
    """Configure health check endpoints"""
    from .health import register_health_checks
    
    # Basic health check
    @app.route('/health')
    def health_check():
        return {
            'status': 'healthy',
            'timestamp': discord_oauth.get_current_timestamp(),
            'version': app.config['API_VERSION'],
            'environment': app.config['ENV']
        }
    
    # Detailed health check
    @app.route('/health/detailed')
    def detailed_health_check():
        checks = register_health_checks()
        results = {}
        
        for check_name, check_func in checks.items():
            try:
                results[check_name] = check_func()
            except Exception as e:
                logger.error(f"Health check failed: {check_name}", error=str(e))
                results[check_name] = {'status': 'error', 'message': str(e)}
        
        return {
            'status': 'healthy' if all(r.get('status') == 'healthy' for r in results.values()) else 'unhealthy',
            'checks': results,
            'timestamp': discord_oauth.get_current_timestamp()
        }


def setup_api_docs(app: Flask):
    """Configure API documentation"""
    # Add Swagger UI
    @app.route('/docs')
    def swagger_docs():
        return app.send_static_file('docs/index.html')
    
    # Add ReDoc
    @app.route('/redoc')
    def redoc_docs():
        return app.send_static_file('docs/redoc.html')
    
    logger.info("API documentation configured", endpoints=['/docs', '/redoc'])


# Context processors
@app.context_processor
def utility_processor():
    """Global template utilities"""
    from .utils import format_timestamp, format_size
    return dict(
        format_timestamp=format_timestamp,
        format_size=format_size,
        config=app.config
    )


# Shell context for Flask CLI
@app.shell_context_processor
def make_shell_context():
    """Enhanced shell context with common objects"""
    return dict(
        app=app,
        db=db,
        config=app.config,
        logger=logger,
        discord_oauth=discord_oauth,
        embed_validator=embed_validator
    )


# Test client
@app.test_client()
def test_client():
    """Test client with proper configuration"""
    return app.test_client()


if __name__ == '__main__':
    # Create and run the application
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('API_PORT', 5000)))