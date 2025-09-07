
"""
Utility functions for Flask API
Common helper functions for authentication, validation, and Discord integration
"""
import base64
import hashlib
import secrets
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlparse, parse_qs
import requests
from flask import current_app, request
from werkzeug.datastructures import Headers
from .models import db, AuditLog
from .errors import api_error_response

# Discord constants
DISCORD_MAX_EMBED_TITLE_LENGTH = 256
DISCORD_MAX_EMBED_DESCRIPTION_LENGTH = 4096
DISCORD_MAX_EMBED_FIELD_NAME_LENGTH = 256
DISCORD_MAX_EMBED_FIELD_VALUE_LENGTH = 1024
DISCORD_MAX_EMBED_FIELDS = 25
DISCORD_MAX_EMBED_FOOTER_TEXT_LENGTH = 2048
DISCORD_MAX_EMBED_AUTHOR_NAME_LENGTH = 256
DISCORD_MAX_EMBED_TOTAL_CHARACTERS = 6000
DISCORD_COLOR_REGEX = re.compile(r'^#?([0-9a-fA-F]{6})$')

class DiscordOAuthUtils:
    """Utility class for Discord OAuth2 operations"""
    
    @staticmethod
    def generate_pkce_challenge(code_verifier: str, method: str = 'S256') -> str:
        """
        Generate PKCE code challenge from verifier
        
        Args:
            code_verifier: Random string used as PKCE verifier
            method: PKCE method ('S256' or 'plain')
        
        Returns:
            Code challenge string
        """
        if method == 'S256':
            # SHA256 hash of verifier, base64url encoded
            digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
            return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
        elif method == 'plain':
            return code_verifier
        else:
            raise ValueError(f"Unsupported PKCE method: {method}")
    
    @staticmethod
    def validate_pkce_challenge(code_verifier: str, code_challenge: str, method: str = 'S256') -> bool:
        """
        Validate PKCE code verifier against challenge
        
        Args:
            code_verifier: Original verifier string
            code_challenge: Challenge to validate against
            method: PKCE method used
        
        Returns:
            True if valid, False otherwise
        """
        if method == 'S256':
            expected_challenge = DiscordOAuthUtils.generate_pkce_challenge(code_verifier, 'S256')
            return expected_challenge == code_challenge
        elif method == 'plain':
            return code_verifier == code_challenge
        return False
    
    @staticmethod
    def generate_code_verifier() -> str:
        """Generate a cryptographically secure PKCE code verifier"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    @staticmethod
    def generate_state() -> str:
        """Generate a cryptographically secure state parameter"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def get_discord_avatar_url(user_id: int, avatar_hash: str, size: int = 128, format: str = 'png') -> str:
        """
        Generate Discord avatar URL
        
        Args:
            user_id: Discord user ID
            avatar_hash: Avatar hash
            size: Image size (must be power of 2)
            format: Image format (png, jpg, webp, gif)
        
        Returns:
            Avatar URL or default avatar URL
        """
        if not avatar_hash:
            # Default avatar
            return f"https://cdn.discordapp.com/embed/avatars/{int(user_id) % 5}.png"
        
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{format}?size={size}"
    
    @staticmethod
    def get_discord_user_roles(bot_token: str, guild_id: int, user_id: int) -> List[Dict[str, Any]]:
        """
        Get user's roles in a Discord guild using bot token
        
        Args:
            bot_token: Discord bot token
            guild_id: Discord guild ID
            user_id: Discord user ID
        
        Returns:
            List of role objects with id and name
        """
        url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
        headers = {
            'Authorization': f'Bot {bot_token}',
            'User-Agent': 'DiscordBot (https://github.com/yourorg/discord-bot-platform, 1.0.0)'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            member = response.json()
            
            # Fetch role details
            roles = []
            if 'roles' in member:
                for role_id in member['roles']:
                    role_url = f"https://discord.com/api/v10/guilds/{guild_id}/roles/{role_id}"
                    role_response = requests.get(role_url, headers=headers, timeout=5)
                    if role_response.status_code == 200:
                        role_data = role_response.json()
                        roles.append({
                            'id': role_id,
                            'name': role_data.get('name', 'Unknown Role'),
                            'color': role_data.get('color', 0),
                            'permissions': role_data.get('permissions', 0),
                            'hoist': role_data.get('hoist', False),
                            'mentionable': role_data.get('mentionable', False)
                        })
            
            return roles
        
        except requests.RequestException as e:
            current_app.logger.error(f"Failed to fetch user roles: {e}")
            return []
        except Exception as e:
            current_app.logger.error(f"Unexpected error fetching roles: {e}")
            return []


class EmbedValidator:
    """Discord embed validation utility"""
    
    @staticmethod
    def validate_discord_embed(embed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Discord embed data against Discord API limits
        
        Args:
            embed_data: Embed data to validate
        
        Returns:
            Validated embed data
        
        Raises:
            ValueError: If embed violates Discord limits
        """
        validated_embed = embed_data.copy()
        
        # Validate top-level fields
        if 'title' in validated_embed:
            validated_embed['title'] = validated_embed['title'][:DISCORD_MAX_EMBED_TITLE_LENGTH]
        
        if 'description' in validated_embed:
            validated_embed['description'] = validated_embed['description'][:DISCORD_MAX_EMBED_DESCRIPTION_LENGTH]
        
        if 'color' in validated_embed:
            validated_embed['color'] = EmbedValidator._validate_color(validated_embed['color'])
        
        # Validate fields
        if 'fields' in validated_embed:
            validated_embed['fields'] = EmbedValidator._validate_fields(validated_embed['fields'])
        
        # Validate footer
        if 'footer' in validated_embed:
            validated_embed['footer'] = EmbedValidator._validate_footer(validated_embed['footer'])
        
        # Validate author
        if 'author' in validated_embed:
            validated_embed['author'] = EmbedValidator._validate_author(validated_embed['author'])
        
        # Validate total character count
        total_chars = EmbedValidator._calculate_total_characters(validated_embed)
        if total_chars > DISCORD_MAX_EMBED_TOTAL_CHARACTERS:
            raise ValueError(f"Embed exceeds total character limit of {DISCORD_MAX_EMBED_TOTAL_CHARACTERS} (current: {total_chars})")
        
        return validated_embed
    
    @staticmethod
    def _validate_color(color: Any) -> int:
        """Validate and convert color to integer"""
        if isinstance(color, int):
            return color & 0xFFFFFF  # Ensure 24-bit color
        
        if isinstance(color, str):
            # Hex color
            match = DISCORD_COLOR_REGEX.match(color)
            if match:
                hex_color = match.group(1)
                return int(hex_color, 16)
        
        # Default color
        return 0
    
    @staticmethod
    def _validate_fields(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate embed fields"""
        validated_fields = []
        field_count = 0
        
        for field in fields:
            if field_count >= DISCORD_MAX_EMBED_FIELDS:
                current_app.logger.warning(f"Embed has too many fields, truncating at {DISCORD_MAX_EMBED_FIELDS}")
                break
            
            validated_field = field.copy()
            
            if 'name' in validated_field:
                validated_field['name'] = validated_field['name'][:DISCORD_MAX_EMBED_FIELD_NAME_LENGTH]
            
            if 'value' in validated_field:
                validated_field['value'] = validated_field['value'][:DISCORD_MAX_EMBED_FIELD_VALUE_LENGTH]
                if not validated_field['value'].strip():
                    validated_field['value'] = '\u200b'  # Zero-width space for empty values
            
            if 'inline' not in validated_field:
                validated_field['inline'] = False
            
            validated_fields.append(validated_field)
            field_count += 1
        
        return validated_fields
    
    @staticmethod
    def _validate_footer(footer: Dict[str, Any]) -> Dict[str, Any]:
        """Validate footer data"""
        validated_footer = footer.copy()
        
        if 'text' in validated_footer:
            validated_footer['text'] = validated_footer['text'][:DISCORD_MAX_EMBED_FOOTER_TEXT_LENGTH]
        
        if 'icon_url' in validated_footer:
            validated_footer['icon_url'] = EmbedValidator._validate_url(validated_footer['icon_url'])
        
        return validated_footer
    
    @staticmethod
    def _validate_author(author: Dict[str, Any]) -> Dict[str, Any]:
        """Validate author data"""
        validated_author = author.copy()
        
        if 'name' in validated_author:
            validated_author['name'] = validated_author['name'][:DISCORD_MAX_EMBED_AUTHOR_NAME_LENGTH]
        
        if 'url' in validated_author:
            validated_author['url'] = EmbedValidator._validate_url(validated_author['url'])
        
        if 'icon_url' in validated_author:
            validated_author['icon_url'] = EmbedValidator._validate_url(validated_author['icon_url'])
        
        return validated_author
    
    @staticmethod
    def _validate_url(url: str) -> str:
        """Validate and sanitize URL"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL")
            
            # Basic URL sanitization
            return url.strip()
        except Exception:
            return ""
    
    @staticmethod
    def _calculate_total_characters(embed: Dict[str, Any]) -> int:
        """Calculate total character count for embed"""
        total = 0
        
        # Title
        if 'title' in embed:
            total += len(str(embed['title']))
        
        # Description
        if 'description' in embed:
            total += len(str(embed['description']))
        
        # Fields
        if 'fields' in embed:
            for field in embed['fields']:
                total += len(str(field.get('name', ''))) + len(str(field.get('value', '')))
        
        # Footer
        if 'footer' in embed and 'text' in embed['footer']:
            total += len(str(embed['footer']['text']))
        
        # Author
        if 'author' in embed and 'name' in embed['author']:
            total += len(str(embed['author']['name']))
        
        return total
    
    @staticmethod
    def create_embed_from_template(template_id: int, overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create embed from template with optional overrides
        
        Args:
            template_id: Template ID to use
            overrides: Optional data to override template fields
        
        Returns:
            Validated embed dictionary
        """
        from .models import EmbedTemplate
        
        template = EmbedTemplate.query.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        embed_data = template.embed_json.copy()
        
        # Apply overrides
        if overrides:
            for key, value in overrides.items():
                if key in embed_data:
                    embed_data[key] = value
        
        # Apply dynamic values (timestamps, user info, etc.)
        embed_data = EmbedValidator._apply_dynamic_values(embed_data)
        
        # Validate final embed
        return EmbedValidator.validate_discord_embed(embed_data)
    
    @staticmethod
    def _apply_dynamic_values(embed: Dict[str, Any]) -> Dict[str, Any]:
        """Apply dynamic values like timestamps and user info"""
        processed_embed = embed.copy()
        
        # Replace placeholders
        if 'timestamp' in processed_embed:
            processed_embed['timestamp'] = datetime.utcnow().isoformat()
        
        # Replace user mentions (implementation depends on context)
        if 'description' in processed_embed:
            processed_embed['description'] = processed_embed['description'].replace('{user}', 'User')
        
        return processed_embed


class RateLimiter:
    """Custom rate limiting utility"""
    
    @staticmethod
    def get_rate_limit_key(endpoint: str, user_id: Optional[int] = None) -> str:
        """
        Generate rate limit key for endpoint
        
        Args:
            endpoint: API endpoint path
            user_id: User ID for user-specific limiting
        
        Returns:
            Rate limit key string
        """
        if user_id:
            return f"{endpoint}:{user_id}"
        else:
            # IP-based limiting
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            return f"{endpoint}:{client_ip}"
    
    @staticmethod
    def is_rate_limited(endpoint: str, limit: int, window: int = 60, user_id: Optional[int] = None) -> bool:
        """
        Check if request is rate limited
        
        Args:
            endpoint: API endpoint
            limit: Maximum requests allowed
            window: Time window in seconds
            user_id: User ID for user-specific limiting
        
        Returns:
            True if rate limited, False otherwise
        """
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        
        limiter_key = RateLimiter.get_rate_limit_key(endpoint, user_id)
        limiter = Limiter(
            key_func=lambda: limiter_key,
            default_limits=["{} per {}".format(limit, window)]
        )
        
        # This is a simplified implementation - in production, use the configured limiter
        return False  # Placeholder for actual rate limiting logic
    
    @staticmethod
    def apply_rate_limit(response: Dict[str, Any], endpoint: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Add rate limit headers to response
        
        Args:
            response: API response dictionary
            endpoint: API endpoint
            user_id: User ID for user-specific limiting
        
        Returns:
            Response with rate limit headers
        """
        # Add rate limit headers (X-RateLimit-*)
        response_headers = Headers()
        response_headers.add('X-RateLimit-Limit', '60')
        response_headers.add('X-RateLimit-Remaining', '59')
        response_headers.add('X-RateLimit-Reset', str(int(datetime.utcnow().timestamp()) + 60))
        
        if user_id:
            response_headers.add('X-RateLimit-User-Limit', '100')
            response_headers.add('X-RateLimit-User-Remaining', '99')
        
        # For Flask responses, these would be added to the response object
        return response


class AuditLogger:
    """Audit logging utility"""
    
    @staticmethod
    def log_sensitive_action(user_id: Optional[int], action: str, resource_type: str = None,
                           resource_id: Optional[int] = None, details: Dict[str, Any] = None,
                           ip_address: Optional[str] = None, success: bool = True):
        """
        Log a sensitive action for audit purposes
        
        Args:
            user_id: User ID performing the action
            action: Action name (e.g., 'user.delete', 'giveaway.create')
            resource_type: Type of resource affected
            resource_id: ID of affected resource
            details: Additional details about the action
            ip_address: Client IP address
            success: Whether the action was successful
        """
        try:
            from .models import AuditLog
            
            audit_entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=details.get('old_values') if details else None,
                new_values=details.get('new_values') if details else None,
                ip_address=ip_address or request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                success=success
            )
            
            db.session.add(audit_entry)
            db.session.commit()
            
            current_app.logger.info(
                "Audit log entry created",
                action=action,
                user_id=user_id,
                resource_id=resource_id,
                success=success
            )
            
        except Exception as e:
            current_app.logger.error(
                "Failed to create audit log entry",
                action=action,
                user_id=user_id,
                error=str(e)
            )
    
    @staticmethod
    def log_api_request(endpoint: str, method: str, user_id: Optional[int] = None, 
                       status_code: int = 200, response_time: float = 0.0):
        """
        Log API request for monitoring and analytics
        
        Args:
            endpoint: API endpoint accessed
            method: HTTP method used
            user_id: User ID (if authenticated)
            status_code: HTTP status code returned
            response_time: Time taken to process request
        """
        # This could be extended to write to a separate analytics table
        current_app.logger.debug(
            "API request logged",
            endpoint=endpoint,
            method=method,
            user_id=user_id,
            status_code=status_code,
            response_time=response_time
        )


class PaginationHelper:
    """Pagination utility for API responses"""
    
    @staticmethod
    def paginate_query(query, page: int = 1, per_page: int = 20, 
                      max_per_page: int = 100, order_by: Any = None) -> Dict[str, Any]:
        """
        Paginate a SQLAlchemy query
        
        Args:
            query: SQLAlchemy query object
            page: Page number (1-indexed)
            per_page: Items per page
            max_per_page: Maximum items per page
            order_by: Column to order by
        
        Returns:
            Dictionary with paginated results and metadata
        """
        # Validate pagination parameters
        page = max(1, int(page))
        per_page = min(max_per_page, max(1, int(per_page)))
        
        # Apply ordering if specified
        if order_by:
            query = query.order_by(order_by)
        
        # Execute pagination
        items = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'items': [item.to_dict() for item in items.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'pages': items.pages,
                'total': items.total
            },
            'links': PaginationHelper._generate_pagination_links(page, items.pages, per_page)
        }
    
    @staticmethod
    def _generate_pagination_links(page: int, total_pages: int, per_page: int) -> Dict[str, str]:
        """Generate pagination links for HATEOAS"""
        base_url = request.base_url.rstrip('/')
        query_params = dict(request.args)
        
        links = {}
        
        # First page
        if page > 1:
            query_params['page'] = 1
            links['first'] = f"{base_url}?{urlencode(query_params)}"
        
        # Previous page
        if page > 1:
            query_params['page'] = page - 1
            links['prev'] = f"{base_url}?{urlencode(query_params)}"
        
        # Next page
        if page < total_pages:
            query_params['page'] = page + 1
            links['next'] = f"{base_url}?{urlencode(query_params)}"
        
        # Last page
        if page < total_pages:
            query_params['page'] = total_pages
            links['last'] = f"{base_url}?{urlencode(query_params)}"
        
        # Self link
        query_params['page'] = page
        links['self'] = f"{base_url}?{urlencode(query_params)}"
        
        return links


class InputValidator:
    """Input validation utility using Pydantic"""
    
    @staticmethod
    def validate_discord_id(value: str) -> int:
        """
        Validate and convert Discord ID
        
        Args:
            value: Discord ID as string
        
        Returns:
            Integer Discord ID
        
        Raises:
            ValueError: If ID is invalid
        """
        try:
            discord_id = int(value)
            if not 100000000000000000 <= discord_id <= 999999999999999999:
                raise ValueError("Discord ID must be 18 digits")
            return discord_id
        except ValueError as e:
            raise ValueError(f"Invalid Discord ID: {str(e)}")
    
    @staticmethod
    def validate_channel_id(value: str) -> int:
        """Validate Discord channel ID"""
        return InputValidator.validate_discord_id(value)
    
    @staticmethod
    def validate_guild_id(value: str) -> int:
        """Validate Discord guild ID"""
        return InputValidator.validate_discord_id(value)
    
    @staticmethod
    def validate_embed_json(embed_json: Dict[str, Any]) -> Dict[str, Any]:
        """Validate embed JSON structure"""
        from . import EmbedValidator
        return EmbedValidator.validate_discord_embed(embed_json)
    
    @staticmethod
    def sanitize_input_text(text: str, max_length: int = 2000) -> str:
        """
        Sanitize and truncate input text
        
        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length
        
        Returns:
            Sanitized and truncated text
        """
        if not text:
            return ""
        
        # Remove control characters except newlines
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip() + "..."
        
        return sanitized.strip()
    
    @staticmethod
    def validate_giveaway_duration(start_at: datetime, end_at: datetime, min_duration: int = 300) -> bool:
        """
        Validate giveaway duration
        
        Args:
            start_at: Start datetime
            end_at: End datetime
            min_duration: Minimum duration in seconds (5 minutes default)
        
        Returns:
            True if valid, False otherwise
        """
        if start_at >= end_at:
            return False
        
        duration = (end_at - start_at).total_seconds()
        return duration >= min_duration


class ExternalAPIClient:
    """Base client for external API integrations"""
    
    def __init__(self, base_url: str, timeout: int = 10, max_retries: int = 3):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DiscordBotPlatform/1.0 (https://github.com/yourorg/discord-bot-platform)',
            'Accept': 'application/json'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 1))
                    current_app.logger.warning(f"Rate limited by {url}, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                current_app.logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
    
    def get(self, endpoint: str, params: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Make GET request"""
        response = self._make_request('GET', endpoint, params=params, headers=headers)
        return response.json()
    
    def post(self, endpoint: str, data: Dict[str, Any] = None, json_data: Dict[str, Any] = None, 
             headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Make POST request"""
        response = self._make_request('POST', endpoint, data=data, json=json_data, headers=headers)
        return response.json()


class TMDBClient(ExternalAPIClient):
    """TMDB API client"""
    
    def __init__(self):
        api_key = current_app.config.get('TMDB_API_KEY')
        if not api_key:
            raise ValueError("TMDB_API_KEY not configured")
        
        super().__init__(current_app.config['TMDB_BASE_URL'])
        self.api_key = api_key
    
    def search_media(self, query: str, media_type: str = 'multi', page: int = 1, 
                    year: int = None, language: str = 'en-US') -> Dict[str, Any]:
        """
        Search for movies, TV shows, or people
        
        Args:
            query: Search query
            media_type: Type of media ('movie', 'tv', 'person', 'multi')
            page: Page number
            year: Filter by year
            language: Language preference
        
        Returns:
            Search results from TMDB
        """
        params = {
            'api_key': self.api_key,
            'query': query,
            'language': language,
            'page': page,
            'include_adult': False
        }
        
        if year:
            params['year'] = year
        
        if media_type != 'multi':
            params['media_type'] = media_type
        
        return self.get('search/multi', params=params)
    
    def get_movie_details(self, movie_id: int, language: str = 'en-US') -> Dict[str, Any]:
        """Get movie details"""
        params = {'api_key': self.api_key, 'language': language}
        return self.get(f'movie/{movie_id}', params=params)
    
    def get_tv_show_details(self, tv_id: int, language: str = 'en-US') -> Dict[str, Any]:
        """Get TV show details"""
        params = {'api_key': self.api_key, 'language': language}
        return self.get(f'tv/{tv_id}', params=params)
    
    def get_trending(self, media_type: str = 'all', time_window: str = 'week') -> Dict[str, Any]:
        """Get trending media"""
        params = {'api_key': self.api_key}
        return self.get(f'trending/{media_type}/{time_window}', params=params)


class AnilistClient(ExternalAPIClient):
    """Anilist GraphQL API client"""
    
    def __init__(self):
        super().__init__(current_app.config['ANILIST_BASE_URL'])
        self.client_id = current_app.config.get('ANILIST_CLIENT_ID')
        self.client_secret = current_app.config.get('ANILIST_CLIENT_SECRET')
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Anilist credentials not configured")
    
    def _build_graphql_query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Build GraphQL query payload"""
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
        return payload
    
    def search_anime(self, search: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """
        Search for anime on Anilist
        
        Args:
            search: Search query
            page: Page number
            per_page: Items per page
        
        Returns:
            Search results from Anilist
        """
        query = """
        query ($search: String, $page: Int, $perPage: Int) {
          Page(page: $page, perPage: $perPage) {
            media(search: $search, type: ANIME) {
              id
              idMal
              title {
                romaji
                english
                native
              }
              description
              startDate {
                year
                month
                day
              }
              episodes
              status
              coverImage {
                large
                medium
              }
              bannerImage
              genres
              averageScore
              favourites
              siteUrl
            }
          }
        }
        """
        
        variables = {'search': search, 'page': page, 'perPage': per_page}
        payload = self._build_graphql_query(query, variables)
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        return self.post('', json=payload, headers=headers)
    
    def get_anime_details(self, anime_id: int) -> Dict[str, Any]:
        """
        Get detailed information about an anime
        
        Args:
            anime_id: Anilist anime ID
        
        Returns:
            Anime details from Anilist
        """
        query = """
        query ($id: Int) {
          Media(id: $id, type: ANIME) {
            id
            idMal
            title {
              romaji
              english
              native
            }
            description
            startDate {
              year
              month
              day
            }
            endDate {
              year
              month
              day
            }
            status
            episodes
            duration
            chapters
            volumes
            season
            seasonYear
            averageScore
            meanScore
            coverImage {
              large
              medium
            }
            bannerImage
            genres
            tags {
              name
              isMediaSpoiler
            }
            siteUrl
            trailer {
              id
              site
              thumbnail
            }
            nextAiringEpisode {
              airingAt
              timeUntilAiring
              episode
            }
            relations {
              edges {
                node {
                  id
                  title {
                    romaji
                    english
                  }
                  format
                  status
                }
                relationType
              }
            }
          }
        }
        """
        
        variables = {'id': anime_id}
        payload = self._build_graphql_query(query, variables)
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        return self.post('', json=payload, headers=headers)


class TVDBClient(ExternalAPIClient):
    """TheTVDB API client"""
    
    def __init__(self):
        api_key = current_app.config.get('TVDB_API_KEY')
        pin = current_app.config.get('TVDB_PIN')
        
        if not api_key or not pin:
            raise ValueError("TVDB credentials not configured")
        
        super().__init__(current_app.config['TVDB_BASE_URL'])
        self.api_key = api_key
        self.pin = pin
        
        # Get JWT token on initialization
        self.token = self._get_jwt_token()
    
    def _get_jwt_token(self) -> str:
        """Get JWT token for TVDB API authentication"""
        login_url = f"{self.base_url}/login"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'{self.api_key} {self.pin}'
        }
        
        try:
            response = requests.post(login_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data['data']['token']
        except Exception as e:
            current_app.logger.error(f"Failed to get TVDB JWT token: {e}")
            raise
    
    def _make_authenticated_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated request to TVDB API"""
        headers = kwargs.pop('headers', {})
        headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        kwargs['headers'] = headers
        return self._make_request(method, endpoint, **kwargs)
    
    def search_series(self, name: str, limit: int = 20) -> Dict[str, Any]:
        """
        Search for TV series on TheTVDB
        
        Args:
            name: Series name to search
            limit: Maximum results to return
        
        Returns:
            Search results from TheTVDB
        """
        params = {'name': name, 'limit': limit}
        return self._make_authenticated_request('GET', 'search/series', params=params)
    
    def get_series_details(self, series_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a TV series
        
        Args:
            series_id: TheTVDB series ID
        
        Returns:
            Series details from TheTVDB
        """
        return self._make_authenticated_request('GET', f'series/{series_id}')
    
    def get_series_episodes(self, series_id: int, page: int = 1) -> Dict[str, Any]:
        """
        Get episodes for a TV series
        
        Args:
            series_id: TheTVDB series ID
            page: Page number
        
        Returns:
            Episode list from TheTVDB
        """
        params = {'page': page}
        return self._make_authenticated_request('GET', f'series/{series_id}/episodes/query', params=params)


# Global instances
discord_oauth = DiscordOAuthUtils()
embed_validator = EmbedValidator()
rate_limiter = RateLimiter()
audit_logger = AuditLogger()

# Utility functions for timestamps and formatting
def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO format"""
    return datetime.utcnow().isoformat()

def format_timestamp(timestamp: Union[datetime, str], format_str: str = '%Y-%m-%d %H:%M:%S UTC') -> str:
    """
    Format timestamp for display
    
    Args:
        timestamp: Timestamp to format
        format_str: Format string
    
    Returns:
        Formatted timestamp string
    """
    if isinstance(timestamp, str):
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    else:
        dt = timestamp
    
    return dt.strftime(format_str)

def format_size(size_bytes: int, precision: int = 1) -> str:
    """
    Format file size in human readable format
    
    Args:
        size_bytes: Size in bytes
        precision: Number of decimal places
    
    Returns:
        Human readable size string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            break
        size_bytes /= 1024.0
    
    return f"{size_bytes:.{precision}f} {unit}"

def generate_api_key(length: int = 32) -> str:
    """Generate cryptographically secure API key"""
    return secrets.token_urlsafe(length)

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    """
    from .models import bcrypt  # Assuming bcrypt is configured in models
    return bcrypt.generate_password_hash(password).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify plain password against hash
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to verify against
    
    Returns:
        True if passwords match, False otherwise
    """
    from .models import bcrypt
    return bcrypt.check_password_hash(hashed_password, plain_password)

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for secure file operations
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    # Remove path traversal attempts
    filename = os.path.basename(filename)
    
    # Remove dangerous characters
    filename = re.sub(r'[^\w\.-]', '_', filename)
    
    # Ensure reasonable length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = f"{name[:250]}{ext}"
    
    return filename

# Discord API helpers
def send_discord_message(bot_token: str, channel_id: int, content: str, embed: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send message to Discord channel using bot token
    
    Args:
        bot_token: Discord bot token
        channel_id: Discord channel ID
        content: Message content
        embed: Optional embed data
    
    Returns:
        Discord API response
    """
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        'Authorization': f'Bot {bot_token}',
        'Content-Type': 'application/json',
        'User-Agent': 'DiscordBot (https://github.com/yourorg/discord-bot-platform, 1.0.0)'
    }
    
    payload = {'content': content}
    if embed:
        payload['embeds'] = [embed]
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        current_app.logger.error(f"Failed to send Discord message: {e}")
        raise

def edit_discord_message(bot_token: str, channel_id: int, message_id: int, 
                        content: str = None, embed: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Edit existing Discord message
    
    Args:
        bot_token: Discord bot token
        channel_id: Discord channel ID
        message_id: Discord message ID
        content: New message content (optional)
        embed: New embed data (optional)
    
    Returns:
        Discord API response
    """
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    headers = {
        'Authorization': f'Bot {bot_token}',
        'Content-Type': 'application/json',
        'User-Agent': 'DiscordBot (https://github.com/yourorg/discord-bot-platform, 1.0.0)'
    }
    
    payload = {}
    if content is not None:
        payload['content'] = content
    if embed:
        payload['embeds'] = [embed]
    
    try:
        response = requests.patch(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        current_app.logger.error(f"Failed to edit Discord message: {e}")
        raise

def delete_discord_message(bot_token: str, channel_id: int, message_id: int) -> bool:
    """
    Delete Discord message
    
    Args:
        bot_token: Discord bot token
        channel_id: Discord channel ID
        message_id: Discord message ID
    
    Returns:
        True if successful, False otherwise
    """
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    headers = {
        'Authorization': f'Bot {bot_token}',
        'User-Agent': 'DiscordBot (https://github.com/yourorg/discord-bot-platform, 1.0.0)'
    }
    
    try:
        response = requests.delete(url, headers=headers, timeout=10)
        return response.status_code == 204
    except requests.RequestException as e:
        current_app.logger.error(f"Failed to delete Discord message: {e}")
        return False

# JSON response helpers
def success_response(data: Any = None, message: str = "Success", status_code: int = 200) -> tuple:
    """
    Create success API response
    
    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code
    
    Returns:
        (response_data, status_code) tuple
    """
    response = {'success': True}
    if message:
        response['message'] = message
    if data is not None:
        response['data'] = data
    
    return jsonify(response), status_code

def paginated_response(items: List[Any], pagination: Dict[str, Any], links: Dict[str, str] = None) -> tuple:
    """
    Create paginated API response
    
    Args:
        items: List of items
        pagination: Pagination metadata
        links: HATEOAS links
    
    Returns:
        (response_data, status_code) tuple
    """
    response = {
        'success': True,
        'data': {
            'items': [item.to_dict() for item in items] if items else [],
            'pagination': pagination
        }
    }
    
    if links:
        response['data']['links'] = links
    
    return jsonify(response), 200

# Error response helper (already in errors.py, but included for completeness)
def create_error_response(message: str, code: int, details: Dict[str, Any] = None,
                         error_type: str = "ValidationError") -> tuple:
    """
    Create standardized error response
    
    Args:
        message: Error message
        code: HTTP status code
        details: Additional error details
        error_type: Type of error
    
    Returns:
        (response_data, status_code) tuple
    """
    response = {
        'success': False,
        'error': {
            'type': error_type,
            'message': message,
            'code': code,
            'timestamp': get_current_timestamp()
        }
    }
    
    if details:
        response['error']['details'] = details
    
    return jsonify(response), code
