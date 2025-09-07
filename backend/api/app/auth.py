"""
Authentication Blueprint for Flask API
Implements Discord OAuth2 with PKCE and RBAC integration
"""
import base64
import secrets
import hashlib
from datetime import timedelta, datetime
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode
import requests
import time
from flask import Blueprint, request, current_app, jsonify, redirect, session, url_for
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt, decode_token
from werkzeug.exceptions import BadRequest, Unauthorized
from sqlalchemy.exc import IntegrityError
from .models import db, User, AuditLog
from .utils import generate_pkce_challenge, validate_pkce_challenge, get_discord_user_roles
from .errors import api_error_response
from .middleware import require_permission

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Discord OAuth2 configuration
DISCORD_OAUTH_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'
DISCORD_USER_URL = 'https://discord.com/api/users/@me'
DISCORD_GUILDS_URL = 'https://discord.com/api/users/@me/guilds'
DISCORD_GUILD_MEMBERS_URL = 'https://discord.com/api/guilds/{guild_id}/members/{user_id}'

# Permission mapping for RBAC
PERMISSIONS = {
    'admin': ['*'],  # Full access
    'moderator': ['embeds.create', 'embeds.edit', 'giveaways.manage', 'stats.view'],
    'staff': ['giveaways.enter', 'media.search', 'watchparty.create'],
    'member': ['giveaways.enter', 'media.search', 'llm.chat'],
    'guest': []
}

class DiscordOAuthClient:
    """Discord OAuth2 client with PKCE support"""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
    
    def generate_auth_url(self, state: str = None, scopes: list = None) -> str:
        """Generate Discord OAuth2 authorization URL with PKCE"""
        if not scopes:
            scopes = current_app.config['OAUTH2_SCOPES']
        
        # Generate PKCE challenge
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = generate_pkce_challenge(code_verifier)
        
        # Store PKCE verifier in session
        session['oauth_state'] = state or secrets.token_urlsafe(32)
        session['pkce_verifier'] = code_verifier
        
        # Build authorization URL
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(scopes),
            'state': session['oauth_state'],
            'code_challenge': code_challenge,
            'code_challenge_method': current_app.config['OAUTH2_PKCE_METHOD']
        }
        
        return f"{DISCORD_OAUTH_URL}?{urlencode(params)}"
    
    def exchange_code_for_token(self, code: str, state: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token"""
        if session.get('oauth_state') != state:
            raise BadRequest("Invalid state parameter")
        
        code_verifier = session.pop('pkce_verifier', None)
        if not code_verifier:
            raise BadRequest("PKCE verifier not found")
        
        # Prepare token request
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'code_verifier': code_verifier
        }
        
        try:
            response = requests.post(DISCORD_TOKEN_URL, data=data, timeout=10)
            response.raise_for_status()
            token_data = response.json()
            
            # Verify PKCE challenge
            if not validate_pkce_challenge(code_verifier, token_data.get('code_challenge')):
                raise BadRequest("PKCE validation failed")
            
            return token_data
        except requests.RequestException as e:
            current_app.logger.error(f"Token exchange failed: {e}")
            raise Unauthorized("Failed to exchange authorization code")
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Discord API"""
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(DISCORD_USER_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    
    def get_user_guilds(self, access_token: str) -> List[Dict[str, Any]]:
        """Get user's guilds from Discord API"""
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(DISCORD_GUILDS_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    
    def get_user_guild_roles(self, access_token: str, guild_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get user's roles in specific guild using bot token"""
        bot_token = current_app.config['DISCORD_BOT_TOKEN']
        if not bot_token:
            return []
        
        url = DISCORD_GUILD_MEMBERS_URL.format(guild_id=guild_id, user_id=user_id)
        headers = {'Authorization': f'Bot {bot_token}'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            member_data = response.json()
            return member_data.get('roles', [])
        return []


# Initialize OAuth client
def get_oauth_client() -> DiscordOAuthClient:
    """Get Discord OAuth client instance"""
    return DiscordOAuthClient(
        client_id=current_app.config['DISCORD_CLIENT_ID'],
        client_secret=current_app.config['DISCORD_CLIENT_SECRET'],
        redirect_uri=current_app.config['DISCORD_REDIRECT_URI']
    )


@bp.route('/login')
def login():
    """Initiate Discord OAuth2 login flow"""
    oauth_client = get_oauth_client()
    auth_url = oauth_client.generate_auth_url()
    
    # Log login attempt
    AuditLog.log_action(
        user_id=None,
        action='auth.login_initiated',
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        success=True
    )
    
    return redirect(auth_url)


@bp.route('/callback')
def oauth_callback():
    """Handle Discord OAuth2 callback"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        current_app.logger.warning(f"OAuth error: {error}")
        return api_error_response(400, f"OAuth error: {error}")
    
    if not code or not state:
        return api_error_response(400, "Missing authorization code or state")
    
    try:
        oauth_client = get_oauth_client()
        token_data = oauth_client.exchange_code_for_token(code, state)
        user_info = oauth_client.get_user_info(token_data['access_token'])
        
        # Get user's roles from guild
        guild_id = current_app.config['DISCORD_GUILD_ID']
        roles = []
        if guild_id:
            roles = oauth_client.get_user_guild_roles(
                token_data['access_token'], 
                guild_id, 
                str(user_info['id'])
            )
        
        # Create or update user in database
        user = User.query.filter_by(user_id=int(user_info['id'])).first()
        if not user:
            user = User(
                user_id=int(user_info['id']),
                username=user_info.get('username', 'unknown'),
                global_name=user_info.get('global_name'),
                avatar_hash=user_info.get('avatar')
            )
            db.session.add(user)
            db.session.flush()  # Get user_id for audit log
        else:
            # Update user info
            user.username = user_info.get('username', user.username)
            user.global_name = user_info.get('global_name', user.global_name)
            user.avatar_hash = user_info.get('avatar', user.avatar_hash)
            user.last_login = datetime.utcnow()
        
        db.session.commit()
        
        # Generate JWT tokens with minimal claims (data minimization)
        identity = {'sub': str(user.user_id)}
        ua = request.headers.get('User-Agent', '')
        add_claims = {
            'iss': current_app.config.get('JWT_ISSUER', 'https://api.local'),
            'aud': current_app.config.get('JWT_AUDIENCE', 'deckhand-api'),
            'ua': hashlib.sha256(ua.encode('utf-8')).hexdigest(),
            'kid': current_app.config.get('JWT_KEY_ID', 'jwt-key-1')
        }
        access_token = create_access_token(
            identity=identity,
            additional_claims=add_claims,
            expires_delta=timedelta(seconds=current_app.config['JWT_ACCESS_TOKEN_EXPIRES'])
        )
        refresh_token = create_refresh_token(identity=identity, additional_claims=add_claims)

        # Persist refresh token (hashed) with rotation family
        store_refresh_token(user.user_id, refresh_token, rotate=True)

        # Log successful authentication
        AuditLog.log_action(
            user_id=user.user_id,
            action='auth.login_success',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            success=True,
            new_values={'user_id': user.user_id, 'username': user.username}
        )
        
        # Store refresh token in database (secure storage)
        store_refresh_token(user.user_id, refresh_token)
        
        # Redirect to frontend with tokens
        redirect_uri = current_app.config['DISCORD_REDIRECT_URI']
        params = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user_id': user.user_id,
            'success': 'true'
        }
        return redirect(f"{redirect_uri}?{urlencode(params)}")
    
    except Exception as e:
        current_app.logger.error(f"OAuth callback error: {str(e)}")
        AuditLog.log_action(
            user_id=None,
            action='auth.login_failed',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            success=False,
            new_values={'error': str(e)}
        )
        return api_error_response(500, "Authentication failed")


@bp.route('/logout')
@jwt_required()
def logout():
    """Logout and invalidate tokens"""
    user_id = get_jwt_identity()

    # Revoke current access token via blocklist (JWT jti)
    try:
        claims = get_jwt()
        jti = claims.get('jti')
        exp = claims.get('exp')  # epoch seconds
        ttl = max(int(exp - time.time()), 0) if exp else 0
        store = current_app.extensions.get('token_store')
        if store and jti:
            # Blocklist the token until it would have expired
            store.setex(f"jwt:blocklist:{jti}", ttl or 1, '1')
    except Exception as e:
        current_app.logger.warning(f"Failed to revoke access token: {e}")

    # Invalidate all refresh tokens for user (logout all sessions)
    invalidate_refresh_tokens(user_id)

    # Log logout
    AuditLog.log_action(
        user_id=user_id,
        action='auth.logout',
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        success=True
    )

    return jsonify({'message': 'Logged out successfully'}), 200


@bp.route('/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token using refresh token (rotation with reuse detection)"""
    payload = request.get_json(silent=True) or {}
    refresh_token = payload.get('refresh_token') or request.args.get('refresh_token')
    if not refresh_token:
        return api_error_response(400, "Refresh token required")
    
    try:
        user_identity = rotate_refresh_token(refresh_token)
        if not user_identity:
            return api_error_response(401, "Invalid or reused refresh token")
        ua = request.headers.get('User-Agent', '')
        add_claims = {
            'iss': current_app.config.get('JWT_ISSUER', 'https://api.local'),
            'aud': current_app.config.get('JWT_AUDIENCE', 'deckhand-api'),
            'ua': hashlib.sha256(ua.encode('utf-8')).hexdigest(),
            'kid': current_app.config.get('JWT_KEY_ID', 'jwt-key-1')
        }
        access_token = create_access_token(identity=user_identity, additional_claims=add_claims)
        return jsonify({
            'access_token': access_token,
            'expires_in': current_app.config['JWT_ACCESS_TOKEN_EXPIRES']
        }), 200
    except Exception as e:
        current_app.logger.error(f"Token refresh failed: {str(e)}")
        return api_error_response(401, "Token refresh failed")


@bp.route('/me')
@jwt_required()
def get_current_user():
    """Get current authenticated user information"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return api_error_response(404, "User not found")
    
    # Refresh roles from Discord
    guild_id = current_app.config['DISCORD_GUILD_ID']
    if guild_id:
        oauth_client = get_oauth_client()
        # Note: For role refresh, we might need to use bot token or stored access token
        # Implementation depends on token storage strategy
        pass
    
    # Get permissions
    permissions = get_user_permissions(user.roles or [])
    
    return jsonify({
        'user': user.to_dict(),
        'permissions': permissions,
        'session_active': True
    })


@bp.route('/permissions')
@jwt_required()
def get_user_permissions_view():
    """Get current user's permissions"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return api_error_response(404, "User not found")
    
    permissions = get_user_permissions(user.roles or [])
    return jsonify({'permissions': permissions})


def get_user_permissions(roles: List[str]) -> List[str]:
    """Map Discord roles to application permissions"""
    permissions = set()
    
    # Check role mappings (configured in AppConfig or external service)
    role_mappings = current_app.config.get('ROLE_MAPPINGS', {
        'admin': ['*'],
        'moderator': ['embeds.*', 'giveaways.*', 'stats.view'],
        'staff': ['giveaways.enter', 'media.*'],
        'member': ['giveaways.enter', 'media.search', 'llm.chat']
    })
    
    for role in roles:
        if role in role_mappings:
            for perm in role_mappings[role]:
                if perm == '*':
                    permissions.update(['*'])
                    break
                elif perm.endswith('.*'):
                    # Wildcard permissions
                    base_perm = perm[:-2]
                    permissions.update([f"{base_perm}.{action}" for action in ['create', 'read', 'update', 'delete']])
                else:
                    permissions.add(perm)
        else:
            # Default member permissions
            permissions.update(['giveaways.enter', 'media.search'])
    
    return list(permissions)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def store_refresh_token(user_id: int, refresh_token: str, rotate: bool = True):
    """Store hashed refresh token in Redis with rotation family keys."""
    store = current_app.extensions.get('token_store')
    if not store:
        return
    token_hash = _hash_token(refresh_token)
    family = f"jwt:rf:{user_id}"
    ttl = int(current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 2592000))
    if rotate:
        last = store.get(f"{family}:latest")
        if last:
            store.setex(f"{family}:bl:{last}", ttl, '1')
        store.setex(f"{family}:latest", ttl, token_hash)
    store.setex(f"{family}:ok:{token_hash}", ttl, '1')


def invalidate_refresh_tokens(user_id: int):
    """Invalidate all refresh tokens for a user (logout-all)."""
    store = current_app.extensions.get('token_store')
    if not store:
        return
    family = f"jwt:rf:{user_id}"
    store.setex(f"{family}:logout_all", int(current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 2592000)), '1')


def rotate_refresh_token(refresh_token: str) -> Optional[Dict[str, Any]]:
    """Verify, detect reuse, and rotate refresh token using Redis store."""
    store = current_app.extensions.get('token_store')
    if not store:
        return None
    try:
        decoded = decode_token(refresh_token)
    except Exception:
        return None
    sub = decoded.get('sub')
    if not sub:
        return None
    token_hash = _hash_token(refresh_token)
    family = f"jwt:rf:{sub}"
    # logout-all?
    if store.get(f"{family}:logout_all"):
        return None
    # Reuse detection
    if store.get(f"{family}:bl:{token_hash}"):
        invalidate_refresh_tokens(sub)
        return None
    if not store.get(f"{family}:ok:{token_hash}"):
        return None
    # Rotate: add current to blocklist
    ttl = int(current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 2592000))
    store.setex(f"{family}:bl:{token_hash}", ttl, '1')
    return {'sub': str(sub)}


# Permission decorators
def require_role(role: str):
    """Decorator to require specific Discord role"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user or role not in (user.roles or []):
                AuditLog.log_action(
                    user_id=user_id,
                    action=f'auth.role_check_failed_{role}',
                    ip_address=request.remote_addr,
                    success=False
                )
                return api_error_response(403, f"Required role '{role}' not found")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user_id = get_jwt_identity()
            permissions = get_jwt().get('permissions', [])
            
            if '*' not in permissions and permission not in permissions:
                AuditLog.log_action(
                    user_id=user_id,
                    action=f'auth.permission_check_failed_{permission}',
                    ip_address=request.remote_addr,
                    success=False
                )
                return api_error_response(403, f"Required permission '{permission}' not found")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Token introspection endpoint (for debugging)
@bp.route('/tokens/introspect', methods=['POST'])
@jwt_required(optional=True)
def introspect_token():
    """Introspect current JWT token (for debugging)"""
    if current_user := get_jwt_identity():
        user = User.query.get(current_user)
        return jsonify({
            'active': True,
            'user_id': current_user,
            'username': user.username if user else None,
            'exp': get_jwt()['exp'],
            'iat': get_jwt()['iat'],
            'permissions': get_jwt().get('permissions', [])
        })
    else:
        return jsonify({'active': False})


# Health check for authentication service
@bp.route('/health')
def auth_health():
    """Health check for authentication service"""
    try:
        oauth_client = get_oauth_client()
        if not all([oauth_client.client_id, oauth_client.client_secret, current_app.config['DISCORD_BOT_TOKEN']]):
            return {'status': 'warning', 'message': 'Missing OAuth configuration'}
        
        return {'status': 'healthy', 'service': 'auth'}
    except Exception as e:
        current_app.logger.error(f"Auth health check failed: {e}")
        return {'status': 'unhealthy', 'message': str(e)}