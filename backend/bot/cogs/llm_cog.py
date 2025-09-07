"""
LLM Chatbot Cog
Handles LLM-powered conversations with conversation memory and rate limiting
"""
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
from sqlalchemy.exc import SQLAlchemyError

from bot.utils import OpenRouterClient, get_async_session
from bot.database import ConversationHistory
from bot.config import settings
from bot.services.llm_service import LLMPromptBuilder, LLMRateLimiter

logger = logging.getLogger(__name__)

class LLMCog(commands.Cog):
    """LLM Chatbot integration with OpenRouter API and conversation memory"""
    
    def __init__(self, bot):
        self.bot = bot
        self.llm_client = OpenRouterClient(settings.OPENROUTER_API_KEY)
        self.prompt_builder = LLMPromptBuilder()
        self.rate_limiter = LLMRateLimiter(
            max_requests=settings.LLM_RATE_LIMIT_PER_MINUTE,
            window_seconds=60
        )
        self.max_context_messages = settings.LLM_MAX_CONTEXT_MESSAGES
        self.model = settings.LLM_DEFAULT_MODEL
        self.fallback_model = settings.LLM_FALLBACK_MODEL
        
        # Conversation cooldowns per user
        self.user_cooldowns = {}
        
        logger.info("LLM Cog initialized", model=self.model, max_context=self.max_context_messages)
    
    @app_commands.command(name="chat", description="Chat with the AI assistant")
    @app_commands.describe(
        message="Your message to the AI",
        model="AI model to use (optional)"
    )
    @app_commands.choices(
        model=[
            app_commands.Choice(name=settings.LLM_DEFAULT_MODEL, value=settings.LLM_DEFAULT_MODEL),
            app_commands.Choice(name=settings.LLM_FALLBACK_MODEL, value=settings.LLM_FALLBACK_MODEL)
        ]
    )
    async def chat_command(self, interaction: discord.Interaction, message: str, model: Optional[str] = None):
        """
        Slash command for LLM chatbot interaction
        
        Args:
            interaction: Discord interaction
            message: User message to send to LLM
            model: Optional model override
        """
        # Check if DM commands are enabled
        if not settings.ENABLE_DM_COMMANDS and not interaction.guild:
            await interaction.response.send_message("❌ Direct messages are not supported.", ephemeral=True)
            return
        
        # Rate limiting
        if await self.rate_limiter.is_limited(interaction.user.id):
            remaining = self.rate_limiter.get_remaining_time(interaction.user.id)
            await interaction.response.send_message(
                f"⏰ Please wait {remaining:.1f} seconds before sending another message.",
                ephemeral=True
            )
            return
        
        # Command cooldown per user
        user_id = interaction.user.id
        if user_id in self.user_cooldowns:
            cooldown_end = self.user_cooldowns[user_id] + timedelta(seconds=2)
            if datetime.utcnow() < cooldown_end:
                remaining = (cooldown_end - datetime.utcnow()).total_seconds()
                await interaction.response.send_message(
                    f"⏰ Please wait {remaining:.1f} seconds before using the command again.",
                    ephemeral=True
                )
                return
        
        self.user_cooldowns[user_id] = datetime.utcnow()
        
        # Defer response for long-running operations
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get conversation history
            history = await self.get_conversation_history(user_id)
            
            # Build prompt
            system_prompt = settings.LLM_SYSTEM_PROMPT
            full_prompt = self.prompt_builder.build_conversation_prompt(
                system_prompt=system_prompt,
                history=history,
                user_message=message
            )
            
            # Generate response
            model_to_use = model or self.model
            response_data = await self.llm_client.chat_completion(
                messages=full_prompt,
                model=model_to_use,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=0.7
            )
            
            # Extract response
            if 'choices' in response_data and len(response_data['choices']) > 0:
                ai_response = response_data['choices'][0]['message']['content'].strip()
                usage = response_data.get('usage', {})
                
                # Create embed response
                embed = discord.Embed(
                    title="🤖 AI Assistant",
                    description=ai_response,
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                
                # Add usage info for staff
                if await self.user_has_permission(interaction.user, 'llm.view_usage'):
                    embed.add_field(
                        name="Usage",
                        value=f"Tokens: {usage.get('total_tokens', 0)} | Model: {model_to_use}",
                        inline=True
                    )
                
                embed.set_footer(text=f"User: {interaction.user.display_name}")
                
                # Send response
                await interaction.followup.send(embed=embed)
                
                # Save conversation to database
                await self.save_conversation(
                    user_id=user_id,
                    role='user',
                    content=message,
                    model_used=None
                )
                await self.save_conversation(
                    user_id=user_id,
                    role='assistant',
                    content=ai_response,
                    model_used=model_to_use,
                    tokens_used=usage.get('total_tokens', 0)
                )
                
                logger.info(
                    "LLM conversation completed",
                    user_id=user_id,
                    guild_id=interaction.guild_id if interaction.guild else None,
                    model=model_to_use,
                    tokens=usage.get('total_tokens', 0),
                    message_length=len(ai_response)
                )
                
                # Rate limiting applied
                await self.rate_limiter.record_request(user_id)
                
            else:
                # Fallback to default model
                logger.warning("Primary model failed, using fallback", model=model_to_use)
                fallback_response = await self.llm_client.chat_completion(
                    messages=full_prompt,
                    model=self.fallback_model,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    temperature=0.7
                )
                
                if 'choices' in fallback_response and len(fallback_response['choices']) > 0:
                    ai_response = fallback_response['choices'][0]['message']['content'].strip()
                    embed = discord.Embed(
                        title="🤖 AI Assistant (Fallback)",
                        description=ai_response,
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow()
                    )
                    embed.set_footer(text="Using fallback model due to primary model error")
                    
                    await interaction.followup.send(embed=embed)
                    
                    await self.save_conversation(
                        user_id=user_id,
                        role='assistant',
                        content=ai_response,
                        model_used=self.fallback_model
                    )
                else:
                    await interaction.followup.send(
                        "❌ Sorry, I'm having trouble connecting to the AI service right now. Please try again later.",
                        ephemeral=True
                    )
                    logger.error("Both primary and fallback LLM models failed", user_id=user_id)
        
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "⏰ The AI service is taking too long to respond. Please try again.",
                ephemeral=True
            )
            logger.warning("LLM request timed out", user_id=user_id, timeout=True)
        
        except Exception as e:
            await interaction.followup.send(
                "❌ An unexpected error occurred while processing your request. Please try again.",
                ephemeral=True
            )
            logger.error("LLM command error", user_id=user_id, error=str(e), exc_info=True)
    
    @app_commands.command(name="clear_chat", description="Clear recent conversation history")
    @app_commands.describe(days="Number of days of history to clear (1-30)")
    async def clear_chat_command(self, interaction: discord.Interaction, days: int = 7):
        """
        Clear recent conversation history for the user
        
        Args:
            interaction: Discord interaction
            days: Number of days of history to clear (1-30)
        """
        days = max(1, min(30, days))
        
        # Permission check
        if not await self.user_has_permission(interaction.user, 'llm.clear_history'):
            await interaction.response.send_message("❌ You don't have permission to clear chat history.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            deleted_count = await self.clear_conversation_history(interaction.user.id, days)
            
            embed = discord.Embed(
                title="🧹 Chat History Cleared",
                description=f"Cleared {deleted_count} messages from the last {days} days.",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            await interaction.followup.send(embed=embed)
            
            logger.info(
                "Chat history cleared by user",
                user_id=interaction.user.id,
                guild_id=interaction.guild_id if interaction.guild else None,
                days_cleared=days,
                deleted_count=deleted_count
            )
            
        except Exception as e:
            await interaction.followup.send(
                "❌ Failed to clear chat history. Please try again.",
                ephemeral=True
            )
            logger.error("Failed to clear chat history", user_id=interaction.user.id, error=str(e))
    
    @app_commands.command(name="ai_status", description="Check AI service status and usage")
    async def ai_status_command(self, interaction: discord.Interaction):
        """Check LLM service status and usage statistics"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check service health
            health_check = await self.check_llm_health()
            
            # Get user usage stats
            user_stats = await self.get_user_usage_stats(interaction.user.id)
            
            embed = discord.Embed(
                title="🤖 AI Service Status",
                color=discord.Color.blue() if health_check['healthy'] else discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="Service Status",
                value="🟢 Online" if health_check['healthy'] else "🔴 Offline",
                inline=True
            )
            
            embed.add_field(
                name="Current Model",
                value=self.model,
                inline=True
            )
            
            embed.add_field(
                name="Rate Limit",
                value=f"{settings.LLM_RATE_LIMIT_PER_MINUTE}/minute",
                inline=True
            )
            
            if user_stats:
                embed.add_field(
                    name="Your Usage",
                    value=f"{user_stats['total_messages']} messages | {user_stats['total_tokens']} tokens",
                    inline=False
                )
            
            embed.set_footer(text="Usage resets monthly")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                "❌ Could not retrieve AI status information.",
                ephemeral=True
            )
            logger.error("AI status command failed", user_id=interaction.user.id, error=str(e))
    
    async def get_conversation_history(self, user_id: int, limit: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history for a user
        
        Args:
            user_id: Discord user ID
            limit: Maximum number of messages (None for all)
        
        Returns:
            List of conversation messages
        """
        limit = limit or self.max_context_messages
        
        async with get_async_session() as session:
            try:
                # Get recent conversation history
                result = await session.execute(
                    text("""
                        SELECT role, content, created_at, model_used, message_tokens, response_tokens
                        FROM conversation_history
                        WHERE user_id = :user_id
                        AND role IN ('user', 'assistant')
                        AND created_at > NOW() - INTERVAL '30 days'
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """),
                    {'user_id': user_id, 'limit': limit}
                )
                
                messages = result.fetchall()
                
                # Format messages for LLM API (newest first, then reverse for chronological order)
                formatted_history = []
                for row in reversed(messages):
                    message_data = {
                        "role": row.role,
                        "content": row.content,
                        "timestamp": row.created_at.isoformat()
                    }
                    
                    if row.model_used:
                        message_data["model"] = row.model_used
                    
                    if row.message_tokens or row.response_tokens:
                        message_data["tokens"] = {
                            "input": row.message_tokens,
                            "output": row.response_tokens
                        }
                    
                    formatted_history.append(message_data)
                
                logger.debug(f"Retrieved {len(formatted_history)} messages from history", user_id=user_id)
                return formatted_history
                
            except SQLAlchemyError as e:
                logger.error("Failed to retrieve conversation history", user_id=user_id, error=str(e))
                return []
    
    async def save_conversation(self, user_id: int, role: str, content: str, 
                               model_used: str = None, tokens_used: int = 0):
        """
        Save conversation message to database
        
        Args:
            user_id: Discord user ID
            role: Message role ('user' or 'assistant')
            content: Message content
            model_used: Model used (for assistant messages)
            tokens_used: Tokens used for this message
        """
        async with get_async_session() as session:
            try:
                conversation = ConversationHistory(
                    user_id=user_id,
                    role=role,
                    content=content,
                    model_used=model_used,
                    message_tokens=tokens_used if role == 'user' else 0,
                    response_tokens=tokens_used if role == 'assistant' else 0
                )
                
                session.add(conversation)
                await session.commit()
                
                logger.debug("Conversation saved to database", user_id=user_id, role=role, tokens=tokens_used)
                
            except SQLAlchemyError as e:
                logger.error("Failed to save conversation", user_id=user_id, role=role, error=str(e))
                await session.rollback()
                raise
    
    async def clear_conversation_history(self, user_id: int, days: int = 7) -> int:
        """
        Clear conversation history for a user
        
        Args:
            user_id: Discord user ID
            days: Number of days back to clear
        
        Returns:
            Number of deleted messages
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        async with get_async_session() as session:
            try:
                # Soft delete by marking as deleted or actually delete
                result = await session.execute(
                    text("""
                        DELETE FROM conversation_history
                        WHERE user_id = :user_id
                        AND role IN ('user', 'assistant')
                        AND created_at < :cutoff_date
                    """),
                    {'user_id': user_id, 'cutoff_date': cutoff_date}
                )
                
                deleted_count = result.rowcount
                await session.commit()
                
                logger.info("Cleared conversation history", user_id=user_id, days=days, deleted_count=deleted_count)
                return deleted_count
                
            except SQLAlchemyError as e:
                logger.error("Failed to clear conversation history", user_id=user_id, error=str(e))
                await session.rollback()
                return 0
    
    async def check_llm_health(self) -> Dict[str, Any]:
        """
        Check LLM service health
        
        Returns:
            Health check result
        """
        try:
            # Test with simple prompt
            test_messages = [{"role": "system", "content": "You are a helpful assistant."},
                           {"role": "user", "content": "Say 'healthy'"}]
            
            response = await self.llm_client.chat_completion(
                messages=test_messages,
                model=self.model,
                max_tokens=10
            )
            
            content = response['choices'][0]['message']['content'].strip().lower()
            healthy = 'healthy' in content
            
            return {
                'healthy': healthy,
                'model': self.model,
                'response_time': response.get('generated_tokens', 0),
                'status': 'online' if healthy else 'degraded'
            }
            
        except Exception as e:
            logger.error("LLM health check failed", error=str(e))
            return {
                'healthy': False,
                'model': self.model,
                'error': str(e),
                'status': 'offline'
            }
    
    async def get_user_usage_stats(self, user_id: int, days: int = 30) -> Optional[Dict[str, Any]]:
        """
        Get usage statistics for a user
        
        Args:
            user_id: Discord user ID
            days: Number of days to look back
        
        Returns:
            User usage statistics
        """
        async with get_async_session() as session:
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                result = await session.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_messages,
                            SUM(message_tokens + response_tokens) as total_tokens,
                            COUNT(DISTINCT model_used) as models_used,
                            MAX(created_at) as last_interaction
                        FROM conversation_history
                        WHERE user_id = :user_id
                        AND created_at >= :cutoff_date
                        AND role IN ('user', 'assistant')
                    """),
                    {'user_id': user_id, 'cutoff_date': cutoff_date}
                )
                
                row = result.fetchone()
                
                if row and row.total_messages > 0:
                    return {
                        'total_messages': row.total_messages,
                        'total_tokens': row.total_tokens or 0,
                        'models_used': row.models_used or 1,
                        'last_interaction': row.last_interaction,
                        'avg_tokens_per_message': (row.total_tokens or 0) // row.total_messages if row.total_messages else 0
                    }
                
                return None
                
            except SQLAlchemyError as e:
                logger.error("Failed to get user usage stats", user_id=user_id, error=str(e))
                return None
    
    async def user_has_permission(self, user: discord.User, permission: str) -> bool:
        """
        Check if user has specific permission based on roles
        
        Args:
            user: Discord user
            permission: Permission string (e.g., 'llm.admin', 'llm.user')
        
        Returns:
            True if user has permission, False otherwise
        """
        # Get user roles from guild
        guild = self.bot.get_guild(settings.DISCORD_GUILD_ID)
        if not guild:
            return False
        
        member = guild.get_member(user.id)
        if not member:
            return False
        
        # Check role permissions (this would integrate with RBAC system)
        role_permissions = {
            'admin': ['llm.admin', 'llm.user', 'llm.view_usage'],
            'moderator': ['llm.user', 'llm.view_usage'],
            'member': ['llm.user']
        }
        
        user_roles = [role.name.lower() for role in member.roles]
        
        for role_name, perms in role_permissions.items():
            if role_name in user_roles and permission in perms:
                return True
        
        # Owner always has all permissions
        if user.id == settings.OWNER_ID:
            return True
        
        return False
    
    @tasks.loop(minutes=60)
    async def cleanup_old_conversations(self):
        """Periodic cleanup of old conversation history"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=settings.CONVERSATION_HISTORY_DAYS)
            
            async with get_async_session() as session:
                result = await session.execute(
                    text("""
                        DELETE FROM conversation_history
                        WHERE created_at < :cutoff_date
                        AND role IN ('user', 'assistant')
                    """),
                    {'cutoff_date': cutoff_date}
                )
                
                deleted_count = result.rowcount
                await session.commit()
                
                if deleted_count > 0:
                    logger.info("Cleaned up old conversations", deleted_count=deleted_count, cutoff_days=settings.CONVERSATION_HISTORY_DAYS)
        
        except Exception as e:
            logger.error("Failed to cleanup old conversations", error=str(e))
    
    async def cog_load(self):
        """Called when cog is loaded"""
        self.cleanup_old_conversations.start()
        logger.info("LLM Cog loaded and cleanup task started")
    
    async def cog_unload(self):
        """Called when cog is unloaded"""
        self.cleanup_old_conversations.cancel()
        logger.info("LLM Cog unloaded and cleanup task stopped")


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(LLMCog(bot))
    logger.info("LLM Cog registered with bot")


# LLM Service Classes (used by the cog)
class LLMPromptBuilder:
    """Build prompts for LLM conversations"""
    
    def __init__(self):
        self.system_prompt_template = """
You are {bot_name}, a helpful AI assistant for the {guild_name} Discord community. You specialize in media discussions, entertainment recommendations, and community engagement.

Guidelines:
- Be friendly, helpful, and engaging
- Keep responses concise but informative (under 2000 characters)
- Use Discord formatting when appropriate (bold, italic, code blocks)
- For media recommendations, provide relevant details (ratings, genres, where to watch)
- Avoid spoilers unless specifically requested
- If unsure about something, say so and offer to look it up
- End responses conversationally to encourage further interaction

Current context:
- Server: {guild_name}
- Channel: {channel_name}
- User: {user_name}

{special_instructions}
"""
    
    def build_conversation_prompt(self, system_prompt: str, history: List[Dict[str, Any]], 
                                user_message: str, max_context: int = 20) -> List[Dict[str, str]]:
        """
        Build complete prompt for LLM conversation
        
        Args:
            system_prompt: System prompt for the AI
            history: Conversation history
            user_message: Current user message
            max_context: Maximum context messages to include
        
        Returns:
            Formatted prompt messages list
        """
        # Limit context to avoid token limits
        recent_history = history[-max_context:] if history else []
        
        # Build messages list
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (oldest first)
        for msg in recent_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Truncate if too long (basic token estimation)
        total_length = sum(len(msg["content"]) for msg in messages)
        max_length = 3000  # Rough character limit before truncation
        
        if total_length > max_length:
            # Keep system prompt and recent messages
            messages = messages[:1]  # Keep system
            messages.extend(messages[-4:])  # Add last 2 exchanges (4 messages)
            messages[-1]["content"] = f"[Previous conversation context truncated]\n\n{user_message}"
        
        logger.debug(f"Built LLM prompt with {len(messages)} messages", total_chars=total_length)
        return messages
    
    def build_media_recommendation_prompt(self, user_preferences: Dict[str, Any], 
                                        media_type: str, context: str = "") -> str:
        """
        Build prompt for media recommendations
        
        Args:
            user_preferences: User preferences and history
            media_type: Type of media ('movie', 'tv', 'anime')
            context: Additional context
        
        Returns:
            Recommendation prompt
        """
        prompt = f"""
Based on the following user preferences and context, recommend {media_type}s that they might enjoy:

User Preferences:
{user_preferences}

Context:
{context}

Please provide:
1. 3-5 specific {media_type} recommendations
2. Brief reason why each recommendation matches their preferences
3. Where to watch (streaming services, availability)
4. Rotten Tomatoes/IMDB ratings if available
5. Keep it conversational and engaging

Format your response as a Discord-friendly message with emojis and formatting.
"""
        return prompt


class LLMRateLimiter:
    """Rate limiting for LLM requests"""
    
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # user_id -> list of timestamps
    
    async def is_limited(self, user_id: int) -> bool:
        """Check if user is rate limited"""
        now = time.time()
        
        # Clean old requests
        if user_id in self.requests:
            self.requests[user_id] = [
                timestamp for timestamp in self.requests[user_id]
                if now - timestamp < self.window_seconds
            ]
        
        current_count = len(self.requests.get(user_id, []))
        return current_count >= self.max_requests
    
    async def get_remaining_time(self, user_id: int) -> float:
        """Get remaining time until rate limit resets"""
        if not await self.is_limited(user_id):
            return 0.0
        
        now = time.time()
        oldest_request = min(self.requests[user_id])
        return max(0, self.window_seconds - (now - oldest_request))
    
    async def record_request(self, user_id: int):
        """Record a new request for rate limiting"""
        now = time.time()
        
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        # Remove old requests
        self.requests[user_id] = [
            timestamp for timestamp in self.requests[user_id]
            if now - timestamp < self.window_seconds
        ]
        
        self.requests[user_id].append(now)
        
        logger.debug("Recorded LLM request", user_id=user_id, current_count=len(self.requests[user_id]))


# Error handling decorator for LLM operations
def handle_llm_error(max_retries: int = 3):
    """Decorator for handling LLM API errors with retries"""
    def decorator(func):
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((requests.RequestException, asyncio.TimeoutError))
        )
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"LLM operation failed after {max_retries} retries", error=str(e))
                raise
        return wrapper
    return decorator


# Usage example and testing
async def test_llm_integration():
    """Test LLM integration (for development)"""
    if not settings.DEBUG:
        return
    
    logger.info("Testing LLM integration...")
    
    test_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! Can you tell me about recent anime releases?"}
    ]
    
    try:
        client = OpenRouterClient(settings.OPENROUTER_API_KEY)
        response = await client.chat_completion(test_messages, max_tokens=100)
        
        if 'choices' in response:
            ai_response = response['choices'][0]['message']['content']
            logger.info("LLM test successful", response_preview=ai_response[:100])
        else:
            logger.error("LLM test failed", response=response)
    
    except Exception as e:
        logger.error("LLM test failed", error=str(e))


if __name__ == "__main__":
    # Run test if in development
    asyncio.run(test_llm_integration())