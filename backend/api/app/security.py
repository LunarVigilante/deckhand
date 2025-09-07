"""
Security utilities and middleware for Flask API
Handles input sanitization, rate limiting, and security headers
"""
import re
import bleach
from typing import Dict, Any, Optional
from flask import request, current_app, g
from werkzeug.exceptions import BadRequest
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Input sanitization patterns
SQL_INJECTION_PATTERNS = [
    r';\s*--',  # SQL comment
    r';\s*/\*',  # SQL comment block start
    r'\*/\s*;',  # SQL comment block end
    r'union\s+select',  # UNION SELECT
    r'exec\s*\(',  # EXEC function
    r'xp_cmdshell',  # XP_CMDSHELL
    r'sp_executesql',  # SP_EXECUTESQL
]

XSS_PATTERNS = [
    r'<script[^>]*>.*?</script>',  # Script tags
    r'javascript:',  # JavaScript protocol
    r'on\w+\s*=',  # Event handlers
    r'<iframe[^>]*>.*?</iframe>',  # Iframe tags
    r'<object[^>]*>.*?</object>',  # Object tags
    r'<embed[^>]*>.*?</embed>',  # Embed tags
]

# Allowed HTML tags for rich text content
ALLOWED_HTML_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'img', 'span', 'div'
]

ALLOWED_HTML_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'span': ['class', 'style'],
    'div': ['class', 'style'],
    '*': ['class', 'style']
}


def sanitize_input(text: str, allow_html: bool = False) -> str:
    """
    Sanitize user input to prevent XSS and injection attacks

    Args:
        text: Input text to sanitize
        allow_html: Whether to allow basic HTML tags

    Returns:
        Sanitized text
    """
    if not text or not isinstance(text, str):
        return text

    # Remove null bytes and other control characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # Check for SQL injection patterns
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning(f"Potential SQL injection detected: {text[:100]}...")
            raise BadRequest("Invalid input detected")

    # Check for XSS patterns
    for pattern in XSS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning(f"Potential XSS detected: {text[:100]}...")
            raise BadRequest("Invalid input detected")

    if allow_html:
        # Use bleach to sanitize HTML content
        text = bleach.clean(
            text,
            tags=ALLOWED_HTML_TAGS,
            attributes=ALLOWED_HTML_ATTRIBUTES,
            strip=True
        )
    else:
        # For plain text, escape HTML entities
        text = bleach.clean(text, tags=[], attributes={}, strip=True)

    # Limit maximum length
    max_length = current_app.config.get('MAX_INPUT_LENGTH', 10000)
    if len(text) > max_length:
        text = text[:max_length]

    return text


def validate_json_input(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate JSON input against a schema

    Args:
        data: Input data to validate
        schema: Validation schema

    Returns:
        Validated and sanitized data

    Raises:
        BadRequest: If validation fails
    """
    try:
        validated_data = {}

        for field, rules in schema.items():
            if field not in data and rules.get('required', False):
                raise BadRequest(f"Missing required field: {field}")

            if field in data:
                value = data[field]

                # Type validation
                expected_type = rules.get('type')
                if expected_type and not isinstance(value, expected_type):
                    if expected_type == str and isinstance(value, (int, float)):
                        value = str(value)
                    elif expected_type == int and isinstance(value, str) and value.isdigit():
                        value = int(value)
                    elif expected_type == float and isinstance(value, str):
                        try:
                            value = float(value)
                        except ValueError:
                            raise BadRequest(f"Invalid type for field {field}")
                    else:
                        raise BadRequest(f"Invalid type for field {field}")

                # Length validation
                if isinstance(value, str):
                    max_length = rules.get('max_length')
                    if max_length and len(value) > max_length:
                        raise BadRequest(f"Field {field} exceeds maximum length of {max_length}")

                    min_length = rules.get('min_length', 0)
                    if len(value) < min_length:
                        raise BadRequest(f"Field {field} must be at least {min_length} characters")

                # Range validation for numbers
                if isinstance(value, (int, float)):
                    min_value = rules.get('min_value')
                    max_value = rules.get('max_value')

                    if min_value is not None and value < min_value:
                        raise BadRequest(f"Field {field} must be at least {min_value}")

                    if max_value is not None and value > max_value:
                        raise BadRequest(f"Field {field} must be at most {max_value}")

                # Pattern validation
                pattern = rules.get('pattern')
                if pattern and isinstance(value, str):
                    if not re.match(pattern, value):
                        raise BadRequest(f"Field {field} does not match required pattern")

                # Sanitization
                if isinstance(value, str):
                    allow_html = rules.get('allow_html', False)
                    value = sanitize_input(value, allow_html)

                validated_data[field] = value

        return validated_data

    except Exception as e:
        if isinstance(e, BadRequest):
            raise
        logger.error(f"Validation error: {str(e)}")
        raise BadRequest("Input validation failed")


def rate_limit_exceeded_handler():
    """Handle rate limit exceeded"""
    return {
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.',
        'retry_after': 60
    }, 429


def security_headers_middleware():
    """Add security headers to responses"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            response = f(*args, **kwargs)

            # Add security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://api.themoviedb.org https://graphql.anilist.co https://openrouter.ai"
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

            return response
        return wrapper
    return decorator


def audit_log_middleware():
    """Middleware to log API requests for audit purposes"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Log request details
            user_id = getattr(g, 'user_id', None) if hasattr(g, 'user_id') else None
            user_agent = request.headers.get('User-Agent', '')
            ip_address = request.remote_addr
            method = request.method
            path = request.path
            query_string = request.query_string.decode('utf-8') if request.query_string else ''

            # Log the request
            logger.info(
                f"AUDIT: {method} {path} - User: {user_id}, IP: {ip_address}, UA: {user_agent[:100]}",
                extra={
                    'user_id': user_id,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'method': method,
                    'path': path,
                    'query_string': query_string,
                    'request_id': getattr(g, 'request_id', None)
                }
            )

            # Call the actual function
            response = f(*args, **kwargs)

            # Log response status
            if hasattr(response, 'status_code'):
                logger.info(
                    f"AUDIT RESPONSE: {method} {path} - Status: {response.status_code}",
                    extra={
                        'user_id': user_id,
                        'status_code': response.status_code,
                        'path': path
                    }
                )

            return response
        return wrapper
    return decorator


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_permissions = getattr(g, 'user_permissions', [])
            user_id = getattr(g, 'user_id', None)

            # Check if user has the required permission
            if permission not in user_permissions:
                logger.warning(
                    f"Permission denied: {permission} for user {user_id}",
                    extra={'user_id': user_id, 'permission': permission}
                )
                return {'error': 'Insufficient permissions'}, 403

            return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_embed_data(embed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate Discord embed data structure

    Args:
        embed_data: Embed data to validate

    Returns:
        Validated embed data

    Raises:
        BadRequest: If validation fails
    """
    embed_schema = {
        'title': {
            'type': str,
            'max_length': 256,
            'required': False
        },
        'description': {
            'type': str,
            'max_length': 4096,
            'required': False,
            'allow_html': False
        },
        'color': {
            'type': int,
            'min_value': 0,
            'max_value': 16777215,
            'required': False
        },
        'url': {
            'type': str,
            'max_length': 2048,
            'required': False,
            'pattern': r'^https?://'
        }
    }

    # Validate basic embed fields
    validated_embed = validate_json_input(embed_data, embed_schema)

    # Validate fields array if present
    if 'fields' in embed_data:
        if not isinstance(embed_data['fields'], list):
            raise BadRequest("Fields must be an array")

        if len(embed_data['fields']) > 25:
            raise BadRequest("Embed cannot have more than 25 fields")

        validated_fields = []
        for i, field in enumerate(embed_data['fields']):
            if not isinstance(field, dict):
                raise BadRequest(f"Field {i} must be an object")

            field_schema = {
                'name': {
                    'type': str,
                    'max_length': 256,
                    'required': True
                },
                'value': {
                    'type': str,
                    'max_length': 1024,
                    'required': True
                },
                'inline': {
                    'type': bool,
                    'required': False
                }
            }

            validated_field = validate_json_input(field, field_schema)
            validated_fields.append(validated_field)

        validated_embed['fields'] = validated_fields

    # Validate author, footer, thumbnail, image if present
    media_fields = ['author', 'footer', 'thumbnail', 'image']
    for field in media_fields:
        if field in embed_data:
            if not isinstance(embed_data[field], dict):
                raise BadRequest(f"{field} must be an object")

            media_schema = {
                'text': {
                    'type': str,
                    'max_length': 2048,
                    'required': False
                },
                'icon_url': {
                    'type': str,
                    'max_length': 2048,
                    'required': False,
                    'pattern': r'^https?://'
                },
                'url': {
                    'type': str,
                    'max_length': 2048,
                    'required': False,
                    'pattern': r'^https?://'
                }
            }

            validated_embed[field] = validate_json_input(embed_data[field], media_schema)

    return validated_embed


# Input validation schemas for different endpoints
EMBED_TEMPLATE_SCHEMA = {
    'template_name': {
        'type': str,
        'min_length': 1,
        'max_length': 100,
        'required': True,
        'pattern': r'^[a-zA-Z0-9_\-\s]+$'
    },
    'embed_json': {
        'required': True
        # Custom validation in validate_embed_data
    },
    'description': {
        'type': str,
        'max_length': 500,
        'required': False
    }
}

GIVEAWAY_SCHEMA = {
    'prize': {
        'type': str,
        'min_length': 1,
        'max_length': 255,
        'required': True
    },
    'winner_count': {
        'type': int,
        'min_value': 1,
        'max_value': 20,
        'required': True
    },
    'channel_id': {
        'type': str,
        'min_length': 15,
        'max_length': 20,
        'required': True,
        'pattern': r'^\d+$'
    },
    'start_at': {
        'required': True
        # Date validation handled separately
    },
    'end_at': {
        'required': True
        # Date validation handled separately
    },
    'description': {
        'type': str,
        'max_length': 1000,
        'required': False
    },
    'required_role_id': {
        'type': str,
        'min_length': 15,
        'max_length': 20,
        'required': False,
        'pattern': r'^\d+$'
    },
    'max_entries_per_user': {
        'type': int,
        'min_value': 1,
        'max_value': 100,
        'required': False
    }
}

MEDIA_TRACK_SCHEMA = {
    'show_id': {
        'type': str,
        'min_length': 1,
        'max_length': 100,
        'required': True
    },
    'show_title': {
        'type': str,
        'min_length': 1,
        'max_length': 255,
        'required': True
    },
    'api_source': {
        'type': str,
        'pattern': r'^(tmdb|anilist|tvdb)$',
        'required': True
    },
    'show_type': {
        'type': str,
        'pattern': r'^(movie|tv|anime)$',
        'required': True
    }
}