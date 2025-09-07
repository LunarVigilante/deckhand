"""
Bot Utilities Module
Shared utility functions for Discord bot operations
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import discord
from discord import app_commands
from structlog import configure, get_logger, processors, stdlib
from sqlalchemy.exc import SQLAlchemyError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings
from database import get_async_session, get_sync_session
from models import db, MessageStats, VoiceStats, ConversationHistory

logger = get_logger()

class BotLogger:
    """Structured logging setup for the bot"""
    
    @staticmethod
    def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None):
        """
        Configure structured logging for the bot
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional log file path
        """
        # Configure structlog
        configure(
            processors=[
                processors.TimeStamper(fmt="iso"),
                processors.add_log_level,
                processors.format_exc_info,
                processors.JSONRenderer() if log_file else processors.ExceptionPrettyPrinter(),
            ],
            logger_factory=stdlib.LoggerFactory(),
            wrapper_class=stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Configure Python standard logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file) if log_file else logging.NullHandler()
            ]
        )
        
        # Configure discord.py logger
        logging.getLogger('discord').setLevel(logging.WARNING)
        logging.getLogger('discord.http').setLevel(logging.WARNING)
        logging.getLogger('discord.gateway').setLevel(logging.INFO)
        
        logger.info(
            "Logging configured",
            level=log_level,
            log_file=log_file,
            bot_name=settings.APPLICATION_ID
        )
    
    @staticmethod
    def log_bot_event(event_name: str, guild_id: Optional[int] = None, user_id: Optional[int] = None, **kwargs):
        """Log bot events with structured data"""
        logger.info(
            f"Bot event: {event_name}",
            event=event_name,
            guild_id=guild_id,
            user_id=user_id,
            **kwargs
        )


def setup_logging():
    """Setup bot logging"""
    BotLogger.setup_logging(
        log_level=settings.LOG_LEVEL,
        log_file=settings.LOG_FILE
    )


class ErrorHandler:
    """Global error handling for bot operations"""
    
    @staticmethod
    async def handle_bot_error(bot: discord.Bot, event: str, *args, **kwargs):
        """
        Handle unhandled bot errors
        
        Args:
            bot: Discord bot instance
            event: Event name that caused the error
            *args, **kwargs: Event arguments
        """
        try:
            exc_info = sys.exc_info()
            logger.error(
                "Unhandled bot error",
                event=event,
                bot_id=bot.user.id if bot.user else None,
                guild_id=getattr(args[0], 'guild_id', None) if args else None,
                exc_type=exc_info[0].__name__ if exc_info[0] else None,
                exc_info=True
            )
            
            # Send error notification to owner
            owner = bot.get_user(settings.OWNER_ID)
            if owner:
                try:
                    embed = discord.Embed(
                        title="❌ Bot Error Occurred",
                        description=f"An error occurred in event `{event}`",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    embed.add_field(name="Event", value=event, inline=True)
                    embed.add_field(name="Guild", value=str(args[0].guild) if args and hasattr(args[0], 'guild') else "Unknown", inline=True)
                    
                    await owner.send(embed=embed)
                except discord.Forbidden:
                    logger.warning("Could not send error notification to owner (missing permissions)")
        
        except Exception as e:
            logger.error("Error in error handler", error=str(e))
    
    @staticmethod
    async def handle_command_error(ctx: commands.Context, error: Exception):
        """
        Handle command errors and provide user feedback
        
        Args:
            ctx: Command context
            error: Exception raised
        """
        # Ignore certain errors
        if isinstance(error, commands.CommandNotFound):
            return
        
        # Handle common command errors
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            logger.warning("Missing permissions", command=ctx.command.qualified_name, user=ctx.author.id)
            return
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`\nUsage: `{ctx.command.qualified_name} {ctx.command.signature}`", ephemeral=True)
            return
        
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided. Please check your input.", ephemeral=True)
            return
        
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ This command is on cooldown. Try again in {error.retry_after:.1f} seconds.", ephemeral=True)
            return
        
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send("⏳ This command is already being used. Please wait for it to complete.", ephemeral=True)
            return
        
        if isinstance(error, commands.DisabledCommand):
            await ctx.send("🚫 This command has been temporarily disabled.", ephemeral=True)
            return
        
        # Database errors
        if isinstance(error, SQLAlchemyError):
            await ctx.send("💾 Database error occurred. Please try again later.", ephemeral=True)
            logger.error("Database error in command", command=ctx.command.qualified_name, user=ctx.author.id, error=str(error))
            return
        
        # HTTP/External API errors
        if isinstance(error, requests.RequestException):
            await ctx.send("🌐 External service temporarily unavailable. Please try again.", ephemeral=True)
            logger.error("External API error", command=ctx.command.qualified_name, user=ctx.author.id, error=str(error))
            return
        
        # Generic error
        await ctx.send("❌ An unexpected error occurred. Please try again or contact an administrator.", ephemeral=True)
        logger.error(
            "Unexpected command error",
            command=ctx.command.qualified_name,
            user=ctx.author.id,
            guild=ctx.guild.id if ctx.guild else None,
            error=str(error),
            exc_info=True
        )


class DiscordUtils:
    """Discord-specific utility functions"""
    
    @staticmethod
    def format_user_mention(user_id: int) -> str:
        """Format user mention from user ID"""
        return f"<@{user_id}>"
    
    @staticmethod
    def format_channel_mention(channel_id: int) -> str:
        """Format channel mention from channel ID"""
        return f"<#{channel_id}>"
    
    @staticmethod
    def format_role_mention(role_id: int) -> str:
        """Format role mention from role ID"""
        return f"<@&{role_id}>"
    
    @staticmethod
    def get_user_avatar_url(user: discord.User) -> str:
        """Get user avatar URL with fallback to default"""
        if user.avatar:
            return str(user.avatar.with_size(128).with_format('png'))
        return f"https://cdn.discordapp.com/embed/avatars/{user.discriminator % 5}.png"
    
    @staticmethod
    def create_embed(title: str, description: str = None, color: int = 0x00ff00, 
                    fields: List[Dict[str, Any]] = None, footer: str = None,
                    thumbnail: str = None, image: str = None, timestamp: datetime = None) -> discord.Embed:
        """
        Create Discord embed with validation
        
        Args:
            title: Embed title
            description: Embed description
            color: Embed color (hex)
            fields: List of embed fields
            footer: Footer text
            thumbnail: Thumbnail URL
            image: Image URL
            timestamp: Timestamp
        
        Returns:
            Validated Discord embed
        """
        embed = discord.Embed(
            title=title[:256],
            description=description[:4096] if description else None,
            color=color,
            timestamp=timestamp
        )
        
        # Add fields
        if fields:
            for field in fields[:25]:  # Discord limit
                embed.add_field(
                    name=field.get('name', '')[:256],
                    value=field.get('value', '')[:1024],
                    inline=field.get('inline', False)
                )
        
        # Add footer
        if footer:
            embed.set_footer(text=footer[:2048])
        
        # Add thumbnail
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        
        # Add image
        if image:
            embed.set_image(url=image)
        
        return embed
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 2000) -> str:
        """Truncate text to Discord message limit"""
        if len(text) <= max_length:
            return text
        
        # Try to truncate at sentence boundary
        sentences = text.split('. ')
        truncated = '. '.join(sentences[:-1])
        
        if len(truncated) <= max_length - 4:
            return f"{truncated}... "
        
        # Fallback to simple truncation
        return text[:max_length-4] + "..."
    
    @staticmethod
    async def safe_send_message(channel: discord.abc.Messageable, content: str = None, 
                               embed: discord.Embed = None, ephemeral: bool = False, 
                               retry_attempts: int = 3) -> Optional[discord.Message]:
        """
        Safely send message with retry logic
        
        Args:
            channel: Discord channel to send to
            content: Message content
            embed: Embed to send
            ephemeral: Whether message should be ephemeral (slash commands)
            retry_attempts: Number of retry attempts
        
        Returns:
            Sent message or None if failed
        """
        for attempt in range(retry_attempts):
            try:
                if isinstance(channel, discord.Interaction):
                    if ephemeral:
                        return await channel.response.send_message(content=content, embed=embed, ephemeral=True)
                    else:
                        return await channel.response.send_message(content=content, embed=embed)
                else:
                    return await channel.send(content=content, embed=embed)
            
            except discord.HTTPException as e:
                if attempt == retry_attempts - 1:
                    logger.error("Failed to send message after retries", channel_id=channel.id, error=str(e))
                    return None
                
                # Wait before retry (exponential backoff)
                await asyncio.sleep(2 ** attempt)
                logger.warning(f"Message send attempt {attempt + 1} failed, retrying", error=str(e))
            
            except Exception as e:
                logger.error("Unexpected error sending message", channel_id=channel.id, error=str(e))
                return None
    
    @staticmethod
    async def safe_edit_message(message: discord.Message, content: str = None, 
                               embed: discord.Embed = None, retry_attempts: int = 3) -> bool:
        """
        Safely edit message with retry logic
        
        Args:
            message: Discord message to edit
            content: New content
            embed: New embed
            retry_attempts: Number of retry attempts
        
        Returns:
            True if successful, False otherwise
        """
        for attempt in range(retry_attempts):
            try:
                await message.edit(content=content, embed=embed)
                return True
            
            except discord.NotFound:
                logger.error("Message not found for editing", message_id=message.id)
                return False
            
            except discord.HTTPException as e:
                if attempt == retry_attempts - 1:
                    logger.error("Failed to edit message after retries", message_id=message.id, error=str(e))
                    return False
                
                await asyncio.sleep(2 ** attempt)
                logger.warning(f"Message edit attempt {attempt + 1} failed, retrying", error=str(e))
            
            except Exception as e:
                logger.error("Unexpected error editing message", message_id=message.id, error=str(e))
                return False


class MediaClients:
    """Factory for media API clients"""
    
    @staticmethod
    def get_tmdb_client(api_key: str):
        """Get TMDB API client"""
        from tmdbv3api import TMDb
        
        tmdb = TMDb()
        tmdb.api_key = api_key
        tmdb.language = 'en'
        tmdb.debug = settings.DEBUG
        
        return tmdb
    
    @staticmethod
    def get_anilist_client():
        """Get Anilist GraphQL client"""
        from gql import Client, gql
        from gql.transport.requests import RequestsHTTPTransport
        
        transport = RequestsHTTPTransport(
            url=settings.ANILIST_BASE_URL,
            headers={'User-Agent': 'DiscordBotPlatform/1.0'},
            verify=True,
            retries=3
        )
        
        client = Client(transport=transport, fetch_schema_from_transport=True)
        return client
    
    @staticmethod
    def get_tvdb_client(api_key: str, pin: str):
        """Get TVDB API client"""
        # TVDB uses JWT authentication, so we need to handle token refresh
        class TVDBClient:
            def __init__(self, api_key: str, pin: str):
                self.api_key = api_key
                self.pin = pin
                self.base_url = settings.TVDB_BASE_URL
                self.token = None
                self.token_expires = 0
                
                # Get initial token
                self._refresh_token()
            
            def _refresh_token(self):
                """Refresh JWT token for TVDB API"""
                import requests
                import jwt
                
                login_url = f"{self.base_url}/login"
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f"{self.api_key} {self.pin}"
                }
                
                try:
                    response = requests.post(login_url, headers=headers, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    self.token = data['data']['token']
                    
                    # Decode token to get expiration
                    decoded = jwt.decode(self.token, options={"verify_signature": False})
                    self.token_expires = decoded['exp']
                    
                    logger.debug("TVDB token refreshed successfully")
                    
                except Exception as e:
                    logger.error("Failed to refresh TVDB token", error=str(e))
                    raise
                
            
            async def search_series(self, name: str, limit: int = 20):
                """Search for TV series"""
                if time.time() > self.token_expires - 60:  # Refresh 1 minute before expiry
                    self._refresh_token()
                
                import requests
                
                search_url = f"{self.base_url}/search/series"
                headers = {
                    'Authorization': f'Bearer {self.token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
                params = {'name': name, 'limit': limit}
                
                try:
                    response = requests.get(search_url, headers=headers, params=params, timeout=10)
                    response.raise_for_status()
                    return response.json()
                except requests.RequestException as e:
                    logger.error("TVDB search failed", error=str(e))
                    return {'data': []}
        
        return TVDBClient(api_key, pin)


# LLM Client for OpenRouter integration
class OpenRouterClient:
    """OpenRouter API client for LLM integration"""
    
    def __init__(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url or settings.OPENROUTER_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'DiscordBotPlatform/1.0'
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0
        self.request_window_start = time.time()
        self.max_requests_per_minute = settings.LLM_RATE_LIMIT_PER_MINUTE
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    async def chat_completion(self, messages: List[Dict[str, str]], model: str = None, 
                             max_tokens: int = None, temperature: float = 0.7,
                             stream: bool = False) -> Dict[str, Any]:
        """
        Generate chat completion using OpenRouter API
        
        Args:
            messages: List of message dictionaries [{"role": "user", "content": "Hello"}]
            model: Model name (defaults to LLM_DEFAULT_MODEL)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream response
        
        Returns:
            API response dictionary
        """
        # Rate limiting
        await self._check_rate_limit()
        
        model = model or settings.LLM_DEFAULT_MODEL
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=60,
                headers={'Accept': 'application/json'}
            )
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            logger.error("OpenRouter API request failed", model=model, error=str(e))
            # Fallback to default model
            if 'deepseek' in model:
                return await self.chat_completion(messages, settings.LLM_FALLBACK_MODEL, max_tokens, temperature, stream)
            raise
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        current_time = time.time()
        
        # Reset window if needed
        if current_time - self.request_window_start >= 60:
            self.request_count = 0
            self.request_window_start = current_time
        
        # Wait if rate limit exceeded
        if self.request_count >= self.max_requests_per_minute:
            wait_time = 60 - (current_time - self.request_window_start)
            logger.info("Rate limit reached, waiting", wait_time=wait_time)
            await asyncio.sleep(wait_time)
            self.request_count = 0
            self.request_window_start = time.time()
        
        # Small delay between requests
        await asyncio.sleep(0.1)
        self.request_count += 1
    
    async def get_conversation_history(self, user_id: int, limit: int = 20) -> List[Dict[str, str]]:
        """
        Get conversation history for user from database
        
        Args:
            user_id: Discord user ID
            limit: Maximum number of messages to retrieve
        
        Returns:
            List of conversation messages
        """
        async with get_async_session() as session:
            result = await session.execute(
                text("""
                    SELECT role, content, created_at 
                    FROM conversation_history 
                    WHERE user_id = :user_id 
                    ORDER BY created_at DESC 
                    LIMIT :limit
                """),
                {'user_id': user_id, 'limit': limit}
            )
            
            messages = result.fetchall()
            
            # Format for LLM API (reverse order, most recent first)
            formatted_messages = []
            for row in reversed(messages):
                formatted_messages.append({
                    "role": row[0],  # user, assistant, system
                    "content": row[1]
                })
            
            return formatted_messages
    
    async def save_conversation_message(self, user_id: int, role: str, content: str, 
                                      model_used: str = None, tokens_used: int = 0):
        """
        Save conversation message to database
        
        Args:
            user_id: Discord user ID
            role: Message role (user, assistant)
            content: Message content
            model_used: Model used for assistant messages
            tokens_used: Tokens used for this message
        """
        async with get_async_session() as session:
            stmt = ConversationHistory(
                user_id=user_id,
                role=role,
                content=content,
                model_used=model_used,
                message_tokens=tokens_used if role == 'assistant' else 0,
                response_tokens=tokens_used if role == 'user' else 0
            )
            session.add(stmt)
            await session.commit()


# Service factories (these will be implemented in services directory)
class StatsService:
    """Statistics service placeholder"""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    async def log_message(self, message: discord.Message):
        """Log message for statistics"""
        pass
    
    async def log_voice_activity(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Log voice activity changes"""
        pass
    
    async def aggregate_daily_stats(self):
        """Aggregate daily statistics"""
        pass


class GiveawayService:
    """Giveaway service placeholder"""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    async def handle_reaction(self, reaction: discord.Reaction, user: discord.User):
        """Handle giveaway reaction"""
        pass
    
    async def cleanup_expired_giveaways(self):
        """Clean up expired giveaways"""
        pass


class MediaService:
    """Media service placeholder"""
    
    def __init__(self):
        pass
    
    async def check_new_releases(self):
        """Check for new media releases"""
        pass


class NotificationService:
    """Notification service placeholder"""
    
    def __init__(self, bot: discord.Bot):
        self.bot = bot
    
    async def log_bot_status(self):
        """Log bot status to notification channel"""
        pass
    
    async def handle_scheduled_event(self, event: discord.ScheduledEvent):
        """Handle scheduled events"""
        pass
    
    async def send_watchparty_reminders(self):
        """Send watch party reminders"""
        pass
    
    async def log_guild_join(self, guild: discord.Guild):
        """Log guild join event"""
        pass
    
    async def log_guild_remove(self, guild: discord.Guild):
        """Log guild remove event"""
        pass


# Export utilities
__all__ = [
    'setup_logging', 'BotLogger', 'ErrorHandler', 'DiscordUtils',
    'MediaClients', 'OpenRouterClient', 'StatsService', 'GiveawayService',
    'MediaService', 'NotificationService'
]