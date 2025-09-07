
"""
Statistics Cog
Handles message, voice, and invite statistics collection and aggregation
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import discord
from discord.ext import commands, tasks
from discord import app_commands
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from bot.database import get_async_session
from bot.utils import get_async_session as get_session
from bot.config import settings
from bot.services.stats_service import StatsService

logger = logging.getLogger(__name__)

class StatsCog(commands.Cog):
    """Statistics collection and aggregation for Discord server activity"""
    
    def __init__(self, bot):
        self.bot = bot
        self.stats_service = StatsService(bot.db_session)
        self.retention_days = settings.STATS_RETENTION_DAYS
        self.aggregation_batch_size = settings.STATS_AGGREGATION_BATCH_SIZE
        self.voice_session_timeout = timedelta(seconds=settings.VOICE_SESSION_TIMEOUT)
        
        # Track active voice sessions
        self.active_voice_sessions = {}  # user_id -> session_start
        
        # Cleanup task for old statistics data
        self.cleanup_old_stats.start()
        
        logger.info("Stats Cog initialized", retention_days=self.retention_days)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize statistics tracking when bot is ready"""
        logger.info("Stats tracking ready", guild_id=self.bot.guild_id)
        
        # Sync any pending voice sessions on startup
        await self.sync_voice_sessions()
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Track message activity for statistics
        
        Args:
            message: Discord message event
        """
        # Ignore bot messages and DMs (if not enabled)
        if message.author.bot or (not settings.ENABLE_DM_COMMANDS and not message.guild):
            return
        
        try:
            # Log raw message data
            await self.stats_service.log_raw_message(
                message_id=message.id,
                user_id=message.author.id,
                channel_id=message.channel.id,
                guild_id=message.guild.id if message.guild else None,
                content=message.content,
                content_length=len(message.content),
                has_attachments=bool(message.attachments),
                has_embeds=bool(message.embeds),
                sent_at=datetime.utcnow()
            )
            
            logger.debug(
                "Message tracked",
                user_id=message.author.id,
                channel_id=message.channel.id,
                content_length=len(message.content)
            )
            
        except SQLAlchemyError as e:
            logger.error("Failed to log message statistics", user_id=message.author.id, error=str(e))
        except Exception as e:
            logger.error("Unexpected error in message tracking", error=str(e))
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """
        Track voice channel activity
        
        Args:
            member: Discord member
            before: Previous voice state
            after: Current voice state
        """
        user_id = member.id
        guild_id = member.guild.id if member.guild else None
        
        try:
            # User joins voice channel
            if before.channel is None and after.channel is not None:
                session_start = datetime.utcnow()
                self.active_voice_sessions[user_id] = {
                    'channel_id': after.channel.id,
                    'session_start': session_start,
                    'guild_id': guild_id
                }
                
                logger.debug("Voice session started", user_id=user_id, channel_id=after.channel.id)
            
            # User leaves voice channel or disconnects
            elif after.channel is None and before.channel is not None:
                if user_id in self.active_voice_sessions:
                    session_data = self.active_voice_sessions.pop(user_id)
                    session_start = session_data['session_start']
                    channel_id = session_data['channel_id']
                    
                    duration = int((datetime.utcnow() - session_start).total_seconds())
                    
                    # Log completed voice session
                    await self.stats_service.log_voice_session(
                        user_id=user_id,
                        channel_id=channel_id,
                        session_start=session_start,
                        session_end=datetime.utcnow(),
                        duration_seconds=duration,
                        guild_id=guild_id
                    )
                    
                    logger.debug(
                        "Voice session ended",
                        user_id=user_id,
                        channel_id=channel_id,
                        duration=duration
                    )
            
            # User switches voice channels
            elif before.channel and after.channel and before.channel != after.channel:
                # End previous session
                if user_id in self.active_voice_sessions:
                    session_data = self.active_voice_sessions.pop(user_id)
                    session_start = session_data['session_start']
                    old_channel_id = session_data['channel_id']
                    
                    duration = int((datetime.utcnow() - session_start).total_seconds())
                    
                    await self.stats_service.log_voice_session(
                        user_id=user_id,
                        channel_id=old_channel_id,
                        session_start=session_start,
                        session_end=datetime.utcnow(),
                        duration_seconds=duration,
                        guild_id=guild_id
                    )
                
                # Start new session
                self.active_voice_sessions[user_id] = {
                    'channel_id': after.channel.id,
                    'session_start': datetime.utcnow(),
                    'guild_id': guild_id
                }
                
                logger.debug(
                    "Voice channel switch",
                    user_id=user_id,
                    from_channel=before.channel.id,
                    to_channel=after.channel.id
                )
            
            # Handle mute/deafen changes (optional enhanced tracking)
            if before.self_mute != after.self_mute or before.self_deaf != after.self_deaf:
                logger.debug(
                    "Voice state change (mute/deafen)",
                    user_id=user_id,
                    self_mute=after.self_mute,
                    self_deaf=after.self_deaf
                )
                
                # Log mute/deafen events if needed for advanced analytics
        
        except SQLAlchemyError as e:
            logger.error("Failed to log voice statistics", user_id=user_id, error=str(e))
        except Exception as e:
            logger.error("Unexpected error in voice tracking", user_id=user_id, error=str(e))
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """
        Track invite creation
        
        Args:
            invite: Discord invite object
        """
        try:
            await self.stats_service.log_invite_creation(
                invite_code=invite.code,
                creator_id=invite.inviter.id if invite.inviter else None,
                channel_id=invite.channel.id if invite.channel else None,
                guild_id=invite.guild.id if invite.guild else None,
                max_uses=invite.max_uses,
                max_age=invite.max_age,
                temporary=invite.temporary,
                created_at=datetime.utcnow()
            )
            
            logger.debug(
                "Invite created",
                code=invite.code,
                creator_id=invite.inviter.id if invite.inviter else None,
                max_uses=invite.max_uses,
                max_age=invite.max_age
            )
            
        except SQLAlchemyError as e:
            logger.error("Failed to log invite creation", code=invite.code, error=str(e))
        except Exception as e:
            logger.error("Unexpected error tracking invite creation", error=str(e))
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """
        Track invite deletion/expiration
        
        Args:
            invite: Discord invite object
        """
        try:
            await self.stats_service.log_invite_usage(
                invite_code=invite.code,
                uses=invite.uses,
                creator_id=invite.inviter.id if invite.inviter else None,
                channel_id=invite.channel.id if invite.channel else None,
                guild_id=invite.guild.id if invite.guild else None,
                expired=invite.expires_at is not None and datetime.utcnow() > invite.expires_at,
                temporary=invite.temporary,
                updated_at=datetime.utcnow()
            )
            
            logger.debug(
                "Invite usage updated",
                code=invite.code,
                uses=invite.uses,
                expired=(invite.expires_at is not None and datetime.utcnow() > invite.expires_at)
            )
            
        except SQLAlchemyError as e:
            logger.error("Failed to log invite usage", code=invite.code, error=str(e))
        except Exception as e:
            logger.error("Unexpected error tracking invite usage", error=str(e))
    
    @app_commands.command(name="stats", description="View server statistics")
    @app_commands.describe(
        time_period="Time period for statistics",
        user_id="Specific user to get stats for (optional)"
    )
    @app_commands.choices(
        time_period=[
            app_commands.Choice(name="Today", value="today"),
            app_commands.Choice(name="This Week", value="week"),
            app_commands.Choice(name="This Month", value="month"),
            app_commands.Choice(name="All Time", value="all")
        ]
    )
    async def stats_command(self, interaction: discord.Interaction, 
                           time_period: str, user_id: Optional[str] = None):
        """
        Slash command to view server or user statistics
        
        Args:
            interaction: Discord interaction
            time_period: Time period for statistics
            user_id: Optional specific user ID
        """
        # Permission check
        if not await self.user_has_view_permission(interaction.user):
            await interaction.response.send_message("❌ You don't have permission to view statistics.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Get statistics based on time period
            if user_id:
                # User-specific stats
                stats = await self.stats_service.get_user_stats(
                    user_id=int(user_id),
                    guild_id=interaction.guild.id,
                    time_period=time_period
                )
                title = f"📊 {time_period.title()} Statistics for <@{user_id}>"
            else:
                # Server-wide stats
                stats = await self.stats_service.get_server_stats(
                    guild_id=interaction.guild.id,
                    time_period=time_period
                )
                title = f"📊 {interaction.guild.name} - {time_period.title()} Statistics"
            
            if not stats:
                await interaction.followup.send(f"❌ No statistics available for {time_period.lower()}.", ephemeral=True)
                return
            
            # Create embed with statistics
            embed = discord.Embed(
                title=title,
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            # Add statistics fields
            if 'message_count' in stats:
                embed.add_field(
                    name="💬 Messages",
                    value=f"{stats['message_count']:,}",
                    inline=True
                )
            
            if 'voice_time' in stats:
                hours, remainder = divmod(stats['voice_time'], 3600)
                minutes, _ = divmod(remainder, 60)
                embed.add_field(
                    name="🎤 Voice Time",
                    value=f"{hours}h {minutes}m",
                    inline=True
                )
            
            if 'active_users' in stats:
                embed.add_field(
                    name="👥 Active Users",
                    value=str(stats['active_users']),
                    inline=True
                )
            
            if 'top_channels' in stats:
                channels_text = "\n".join([
                    f"{i+1}. <#{channel_id}> ({count})" 
                    for i, (channel_id, count) in enumerate(stats['top_channels'][:3])
                ])
                embed.add_field(
                    name="📢 Top Channels",
                    value=channels_text or "No data",
                    inline=False
                )
            
            if 'invites_created' in stats:
                embed.add_field(
                    name="🔗 Invites Created",
                    value=str(stats['invites_created']),
                    inline=True
                )
            
            embed.set_footer(text=f"Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            
            await interaction.followup.send(embed=embed)
            
            logger.info(
                "Statistics command executed",
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                time_period=time_period,
                user_specific=bool(user_id)
            )
            
        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid user ID provided: {str(e)}", ephemeral=True)
            logger.warning("Invalid user ID in stats command", user_id=user_id, error=str(e))
        except Exception as e:
            await interaction.followup.send("❌ Failed to retrieve statistics. Please try again.", ephemeral=True)
            logger.error("Stats command failed", user_id=interaction.user.id, error=str(e))
    
    @app_commands.command(name="top_users", description="View top active users")
    @app_commands.describe(
        metric="Metric to rank by",
        time_period="Time period to consider"
    )
    @app_commands.choices(
        metric=[
            app_commands.Choice(name="Messages", value="messages"),
            app_commands.Choice(name="Voice Time", value="voice_time"),
            app_commands.Choice(name="Overall Activity", value="overall")
        ],
        time_period=[
            app_commands.Choice(name="This Week", value="week"),
            app_commands.Choice(name="This Month", value="month"),
            app_commands.Choice(name="All Time", value="all")
        ]
    )
    async def top_users_command(self, interaction: discord.Interaction, 
                               metric: str, time_period: str):
        """
        Slash command to view top users by activity
        
        Args:
            interaction: Discord interaction
            metric: Activity metric
            time_period: Time period
        """
        # Permission check
        if not await self.user_has_view_permission(interaction.user):
            await interaction.response.send_message("❌ You don't have permission to view top users.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Get top users
            top_users = await self.stats_service.get_top_users(
                guild_id=interaction.guild.id,
                metric=metric,
                time_period=time_period,
                limit=10
            )
            
            if not top_users:
                await interaction.followup.send(f"❌ No {metric} data available for {time_period.lower()}.", ephemeral=True)
                return
            
            # Create embed
            embed = discord.Embed(
                title=f"🏆 Top {metric.title()} Users - {time_period.title()}",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            
            # Format leaderboard
            leaderboard = []
            for i, user_stats in enumerate(top_users, 1):
                user = interaction.guild.get_member(user_stats['user_id'])
                username = user.display_name if user else f"User {user_stats['user_id']}"
                
                if metric == 'messages':
                    value = f"{user_stats['count']:,} messages"
                elif metric == 'voice_time':
                    hours, remainder = divmod(user_stats['total_seconds'], 3600)
                    minutes, _ = divmod(remainder, 60)
                    value = f"{hours}h {minutes}m"
                else:
                    value = f"{user_stats['score']:.1f} points"
                
                leaderboard.append(f"{i:2d}. **{username}** - {value}")
            
            embed.description = "\n".join(leaderboard)
            embed.set_footer(text=f"Generated for {interaction.guild.name}")
            
            await interaction.followup.send(embed=embed)
            
            logger.info(
                "Top users command executed",
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                metric=metric,
                time_period=time_period
            )
            
        except Exception as e:
            await interaction.followup.send("❌ Failed to retrieve top users. Please try again.", ephemeral=True)
            logger.error("Top users command failed", user_id=interaction.user.id, error=str(e))
    
    @app_commands.command(name="server_stats", description="Get detailed server statistics")
    async def server_stats_command(self, interaction: discord.Interaction):
        """Get comprehensive server statistics"""
        # Permission check
        if not await self.user_has_view_permission(interaction.user):
            await interaction.response.send_message("❌ You don't have permission to view server statistics.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Get comprehensive server stats
            server_stats = await self.stats_service.get_comprehensive_server_stats(
                guild_id=interaction.guild.id
            )
            
            if not server_stats:
                await interaction.followup.send("❌ No server statistics available.", ephemeral=True)
                return
            
            # Create multi-page embed
            embeds = []
            
            # General server info
            embed1 = discord.Embed(
                title=f"📊 {interaction.guild.name} - Server Overview",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed1.add_field(
                name="👥 Members",
                value=f"Total: {server_stats['member_count']:,}\nBots: {server_stats['bot_count']:,}\nActive: {server_stats['active_members']:,}",
                inline=True
            )
            
            embed1.add_field(
                name="💬 Activity",
                value=f"Total Messages: {server_stats['total_messages']:,}\nAvg Daily: {server_stats['avg_daily_messages']:.0f}\nActive Channels: {server_stats['active_channels']}",
                inline=True
            )
            
            embed1.add_field(
                name="🎤 Voice",
                value=f"Total Voice Time: {server_stats['total_voice_time_formatted']}\nActive Voice Users: {server_stats['active_voice_users']}\nVoice Channels: {server_stats['voice_channels']}",
                inline=True
            )
            
            embed1.set_footer(text="Page 1/3 - General Stats")
            embeds.append(embed1)
            
            # Top users embed
            embed2 = discord.Embed(
                title=f"🏆 Top Active Users - Last 30 Days",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            
            top_users = server_stats['top_users_messages'][:5]
            leaderboard = []
            for i, user_stats in enumerate(top_users, 1):
                user = interaction.guild.get_member(user_stats['user_id'])
                username = user.display_name if user else f"User {user_stats['user_id']}"
                leaderboard.append(f"{i}. **{username}** - {user_stats['message_count']:,} msgs")
            
            embed2.description = "\n".join(leaderboard) or "No data available"
            embed2.set_footer(text="Page 2/3 - Top Users")
            embeds.append(embed2)
            
            # Channel activity embed
            embed3 = discord.Embed(
                title=f"📢 Most Active Channels - Last 30 Days",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            top_channels = server_stats['top_channels'][:5]
            channel_list = []
            for i, channel_stats in enumerate(top_channels, 1):
                channel = interaction.guild.get_channel(channel_stats['channel_id'])
                channel_name = channel.name if channel else f"Channel {channel_stats['channel_id']}"
                channel_list.append(f"{i}. **#{channel_name}** - {channel_stats['message_count']:,} msgs")
            
            embed3.description = "\n".join(channel_list) or "No data available"
            embed3.set_footer(text="Page 3/3 - Channel Activity")
            embeds.append(embed3)
            
            # Send first embed and store others for pagination
            await interaction.followup.send(embed=embed1)
            
            # Store additional embeds in interaction context (simplified - in production use database or cache)
            logger.info(
                "Server stats command executed",
                user_id=interaction.user.id,
                guild_id=interaction.guild.id
            )
            
        except Exception as e:
            await interaction.followup.send("❌ Failed to retrieve server statistics. Please try again.", ephemeral=True)
            logger.error("Server stats command failed", user_id=interaction.user.id, error=str(e))
    
    @tasks.loop(hours=1)
    async def aggregate_statistics(self):
        """Hourly statistics aggregation task"""
        try:
            logger.info("Starting hourly statistics aggregation")
            
            # Aggregate message statistics
            await self.stats_service.aggregate_message_stats(
                batch_size=self.aggregation_batch_size,
                retention_days=self.retention_days
            )
            
            # Aggregate voice statistics
            await self.stats_service.aggregate_voice_stats(
                batch_size=self.aggregation_batch_size,
                retention_days=self.retention_days
            )
            
            # Refresh materialized views
            await self.refresh_materialized_views()
            
            # Cleanup old raw data
            await self.cleanup_old_raw_data()
            
            logger.info("Hourly statistics aggregation completed")
            
        except Exception as e:
            logger.error("Statistics aggregation failed", error=str(e))
    
    @tasks.loop(days=1)
    async def cleanup_old_stats(self):
        """Daily cleanup of old statistics data"""
        try:
            logger.info("Starting daily statistics cleanup")
            
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            # Cleanup old raw message data
            deleted_messages = await self.stats_service.cleanup_old_messages(cutoff_date)
            
            # Cleanup old voice sessions
            deleted_voice = await self.stats_service.cleanup_old_voice_sessions(cutoff_date)
            
            # Cleanup old invite data
            deleted_invites = await self.stats_service.cleanup_old_invites(cutoff_date)
            
            logger.info(
                "Daily statistics cleanup completed",
                deleted_messages=deleted_messages,
                deleted_voice=deleted_voice,
                deleted_invites=deleted_invites,
                retention_days=self.retention_days
            )
            
        except Exception as e:
            logger.error("Statistics cleanup failed", error=str(e))
    
    async def sync_voice_sessions(self):
        """Sync voice sessions on bot startup (in case of restart)"""
        try:
            # Check for users currently in voice channels
            guild = self.bot.get_guild(settings.DISCORD_GUILD_ID)
            if not guild:
                return
            
            for member in guild.members:
                if member.voice and not member.voice.afk:
                    # Resume voice session
                    session_start = datetime.utcnow() - timedelta(minutes=5)  # Assume 5 min ago
                    self.active_voice_sessions[member.id] = {
                        'channel_id': member.voice.channel.id,
                        'session_start': session_start,
                        'guild_id': guild.id
                    }
                    
                    logger.debug("Resumed voice session on startup", user_id=member.id, channel_id=member.voice.channel.id)
                    
        except Exception as e:
            logger.error("Failed to sync voice sessions on startup", error=str(e))
    
    async def refresh_materialized_views(self):
        """Refresh materialized views for efficient querying"""
        try:
            async with get_async_session() as session:
                # Refresh daily message stats
                await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY daily_user_message_stats"))
                
                # Refresh monthly voice stats
                await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_user_voice_stats"))
                
                # Refresh server activity summary
                await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY server_activity_summary"))
                
                await session.commit()
                
                logger.debug("Materialized views refreshed successfully")
                
        except SQLAlchemyError as e:
            logger.error("Failed to refresh materialized views", error=str(e))
        except Exception as e:
            logger.error("Unexpected error refreshing materialized views", error=str(e))
    
    async def cleanup_old_raw_data(self):
        """Cleanup old raw statistics data while keeping aggregated data"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            async with get_async_session() as session:
                # Cleanup old message stats (keep recent for real-time queries)
                recent_cutoff = datetime.utcnow() - timedelta(days=7)
                deleted_messages = await session.execute(
                    text("""
                        DELETE FROM message_stats 
                        WHERE sent_at < :cutoff_date
                    """),
                    {'cutoff_date': recent_cutoff}
                )
                
                # Cleanup old voice stats
                deleted_voice = await session.execute(
                    text("""
                        DELETE FROM voice_stats 
                        WHERE session_start < :cutoff_date
                        AND (session_end IS NULL OR session_end < :cutoff_date)
                    """),
                    {'cutoff_date': cutoff_date}
                )
                
                # Cleanup old invite stats
                deleted_invites = await session.execute(
                    text("""
                        DELETE FROM invite_stats 
                        WHERE created_at < :cutoff_date
                        AND (expires_at IS NULL OR expires_at < :cutoff_date)
                    """),
                    {'cutoff_date': cutoff_date}
                )
                
                await session.commit()
                
                logger.debug(
                    "Raw data cleanup completed",
                    deleted_messages=deleted_messages.rowcount,
                    deleted_voice=deleted_voice.rowcount,
                    deleted_invites=deleted_invites.rowcount
                )
                
        except SQLAlchemyError as e:
            logger.error("Failed to cleanup raw data", error=str(e))
        except Exception as e:
            logger.error("Unexpected error in raw data cleanup", error=str(e))
    
    async def user_has_view_permission(self, user: discord.User) -> bool:
        """
        Check if user has permission to view statistics
        
        Args:
            user: Discord user
        
        Returns:
            True if user has permission
        """
        # Owner always has access
        if user.id == settings.OWNER_ID:
            return True
        
        # Check guild roles (integrate with RBAC)
        guild = self.bot.get_guild(settings.DISCORD_GUILD_ID)
        if guild:
            member = guild.get_member(user.id)
            if member:
                # Check for roles with stats permission
                allowed_roles = ['admin', 'moderator', 'staff']  # Configure via database
                user_roles = [role.name.lower() for role in member.roles]
                
                if any(role in allowed_roles for role in user_roles):
                    return True
        
        return False
    
    async def cog_load(self):
        """Called when cog is loaded"""
        # Start aggregation task
        self.aggregate_statistics.start()
        logger.info("Stats aggregation task started")
    
    async def cog_unload(self):
        """Called when cog is unloaded"""
        self.aggregate_statistics.cancel()
        self.cleanup_old_stats.cancel()
        logger.info("Stats tasks stopped")


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(StatsCog(bot))
    logger.info("Stats Cog registered with bot")


# Service class for statistics operations
class StatsService:
    """Statistics service for data collection and aggregation"""
    
    def __init__(self, db_session_maker):
        self.db_session_maker = db_session_maker
    
    async def log_raw_message(self, message_id: int, user_id: int, channel_id: int, 
                            guild_id: Optional[int], content: str, content_length: int,
                            has_attachments: bool, has_embeds: bool, sent_at: datetime):
        """
        Log raw message data for later aggregation
        
        Args:
            message_id: Discord message ID
            user_id: Discord user ID
            channel_id: Discord channel ID
            guild_id: Discord guild ID
            content: Message content
            content_length: Length of content
            has_attachments: Whether message has attachments
            has_embeds: Whether message has embeds
            sent_at: Timestamp when message was sent
        """
        async with self.db_session_maker() as session:
            try:
                # Sanitize content for database (truncate if too long)
                max_content_length = 1000
                safe_content = content[:max_content_length] if len(content) > max_content_length else content
                
                await session.execute(
                    text("""
                        INSERT INTO message_stats (message_id, user_id, channel_id, guild_id, 
                                                 content, content_length, has_attachments, 
                                                 has_embeds, sent_at)
                        VALUES (:message_id, :user_id, :channel_id, :guild_id, :content, 
                               :content_length, :has_attachments, :has_embeds, :sent_at)
                        ON CONFLICT (message_id) DO NOTHING
                    """),
                    {
                        'message_id': message_id,
                        'user_id': user_id,
                        'channel_id': channel_id,
                        'guild_id': guild_id,
                        'content': safe_content,
                        'content_length': content_length,
                        'has_attachments': has_attachments,
                        'has_embeds': has_embeds,
                        'sent_at': sent_at
                    }
                )
                
                await session.commit()
                
            except SQLAlchemyError as e:
                logger.error("Failed to log raw message", message_id=message_id, error=str(e))
                await session.rollback()
    
    async def log_voice_session(self, user_id: int, channel_id: int, session_start: datetime,
                               session_end: datetime, duration_seconds: int, guild_id: Optional[int]):
        """
        Log completed voice session
        
        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            session_start: Session start time
            session_end: Session end time
            duration_seconds: Session duration in seconds
            guild_id: Discord guild ID
        """
        async with self.db_session_maker() as session:
            try:
                await session.execute(
                    text("""
                        INSERT INTO voice_stats (user_id, channel_id, session_start, session_end, 
                                               duration_seconds, guild_id)
                        VALUES (:user_id, :channel_id, :session_start, :session_end, 
                               :duration_seconds, :guild_id)
                    """),
                    {
                        'user_id': user_id,
                        'channel_id': channel_id,
                        'session_start': session_start,
                        'session_end': session_end,
                        'duration_seconds': duration_seconds,
                        'guild_id': guild_id
                    }
                )
                
                await session.commit()
                
            except SQLAlchemyError as e:
                logger.error("Failed to log voice session", user_id=user_id, error=str(e))
                await session.rollback()
    
    async def log_invite_creation(self, invite_code: str, creator_id: Optional[int], 
                                 channel_id: Optional[int], guild_id: Optional[int],
                                 max_uses: Optional[int], max_age: Optional[int],
                                 temporary: bool, created_at: datetime):
        """
        Log invite creation event
        
        Args:
            invite_code: Discord invite code
            creator_id: Creator user ID
            channel_id: Target channel ID
            guild_id: Guild ID
            max_uses: Maximum uses
            max_age: Maximum age in seconds
            temporary: Whether invite is temporary
            created_at: Creation timestamp
        """
        async with self.db_session_maker() as session:
            try:
                await session.execute(
                    text("""
                        INSERT INTO invite_stats (invite_code, creator_id, channel_id, guild_id,
                                                uses, max_uses, created_at, expires_at, 
                                                is_temporary)
                        VALUES (:invite_code, :creator_id, :channel_id, :guild_id, 0, 
                               :max_uses, :created_at, 
                               CASE WHEN :max_age > 0 THEN :created_at + INTERVAL '1 second' * :max_age ELSE NULL END,
                               :temporary)
                        ON CONFLICT (invite_code) DO UPDATE SET
                            creator_id = EXCLUDED.creator_id,
                            channel_id = EXCLUDED.channel_id,
                            max_uses = EXCLUDED.max_uses,
                            created_at = EXCLUDED.created_at,
                            expires_at = EXCLUDED.expires_at,
                            is_temporary = EXCLUDED.temporary
                    """),
                    {
                        'invite_code': invite_code,
                        'creator_id': creator_id,
                        'channel_id': channel_id,
                        'guild_id': guild_id,
                        'max_uses': max_uses,
                        'max_age': max_age,
                        'created_at': created_at,
                        'temporary': temporary
                    }
                )
                
                await session.commit()
                
            except SQLAlchemyError as e:
                logger.error("Failed to log invite creation", invite_code=invite_code, error=str(e))
                await session.rollback()
    
    async def log_invite_usage(self, invite_code: str, uses: int, creator_id: Optional[int],
                              channel_id: Optional[int], guild_id: Optional[int],
                              expired: bool, temporary: bool, updated_at: datetime):
        """
        Update invite usage statistics
        
        Args:
            invite_code: Discord invite code
            uses: Current usage count
            creator_id: Creator user ID
            channel_id: Target channel ID
            guild_id: Guild ID
            expired: Whether invite has expired
            temporary: Whether invite is temporary
            updated_at: Update timestamp
        """
        async with self.db_session_maker() as session:
            try:
                await session.execute(
                    text("""
                        UPDATE invite_stats 
                        SET uses = :uses, updated_at = :updated_at,
                            expires_at = CASE 
                                WHEN :expired AND expires_at IS NULL 
                                THEN :updated_at 
                                ELSE expires_at 
                            END
                        WHERE invite_code = :invite_code
                    """),
                    {
                        'invite_code': invite_code,
                        'uses': uses,
                        'updated_at': updated_at,
                        'expired': expired
                    }
                )
                
                await session.commit()
                
            except SQLAlchemyError as e:
                logger.error("Failed to update invite usage", invite_code=invite_code, error=str(e))
                await session.rollback()
    
    async def aggregate_message_stats(self, batch_size: int = 1000, retention_days: int = 365):
        """
        Aggregate raw message data into daily statistics
        
        Args:
            batch_size: Number of messages to process per batch
            retention_days: Days of raw data to retain
        """
        async with self.db_session_maker() as session:
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
                
                # Process messages in batches to avoid memory issues
                offset = 0
                while True:
                    # Get batch of messages to aggregate
                    batch_messages = await session.execute(
                        text("""
                            SELECT user_id, channel_id, guild_id, sent_at, content_length, has_attachments
                            FROM message_stats
                            WHERE sent_at < :cutoff_date
                            ORDER BY sent_at ASC
                            LIMIT :batch_size OFFSET :offset
                        """),
                        {
                            'cutoff_date': cutoff_date,
                            'batch_size': batch_size,
                            'offset': offset
                        }
                    )
                    
                    messages = batch_messages.fetchall()
                    if not messages:
                        break
                    
                    # Aggregate this batch
                    for msg in messages:
                        await self._aggregate_single_message(
                            user_id=msg.user_id,
                            channel_id=msg.channel_id,
                            guild_id=msg.guild_id,
                            date=msg.sent_at.date(),
                            content_length=msg.content_length,
                            has_attachments=msg.has_attachments
                        )
                    
                    # Delete processed batch
                    await session.execute(
                        text("""
                            DELETE FROM message_stats
                            WHERE sent_at < :cutoff_date
                            AND id IN (
                                SELECT id FROM message_stats
                                WHERE sent_at < :cutoff_date
                                ORDER BY sent_at ASC
                                LIMIT :batch_size OFFSET :offset
                            )
                        """),
                        {
                            'cutoff_date': cutoff_date,
                            'batch_size': batch_size,
                            'offset': offset
                        }
                    )
                    
                    await session.commit()
                    offset += batch_size
                    
                    logger.debug(f"Aggregated message batch", offset=offset, batch_size=batch_size)
                
                logger.info("Message statistics aggregation completed", retention_days=retention_days)
                
            except SQLAlchemyError as e:
                logger.error("Failed to aggregate message stats", error=str(e))
                await session.rollback()
    
    async def _aggregate_single_message(self, user_id: int, channel_id: int, guild_id: Optional[int],
                                       date: datetime.date, content_length: int, has_attachments: bool):
        """Aggregate single message into daily stats"""
        try:
            async with self.db_session_maker() as session:
                # Use UPSERT to update or insert daily stats
                await session.execute(
                    text("""
                        INSERT INTO daily_user_message_stats (user_id, date, message_count, 
                                                            avg_message_length, attachments_count)
                        VALUES (:user_id, :date, 1, :content_length, :attachments_count)
                        ON CONFLICT (user_id, date) DO UPDATE SET
                            message_count = daily_user_message_stats.message_count + 1,
                            attachments_count = daily_user_message_stats.attachments_count + :attachments_count,
                            avg_message_length = (
                                (daily_user_message_stats.avg_message_length * daily_user_message_stats.message_count + :content_length) /
                                (daily_user_message_stats.message_count + 1)
                            )
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        'user_id': user_id,
                        'date': date,
                        'content_length': content_length,
                        'attachments_count': 1 if has_attachments else 0
                    }
                )
                
                await session.commit()
                
        except SQLAlchemyError as e:
            logger.error("Failed to aggregate single message", user_id=user_id, date=date, error=str(e))
    
    async def aggregate_voice_stats(self, batch_size: int = 1000, retention_days: int = 365):
        """
        Aggregate voice session data into monthly statistics
        
        Args:
            batch_size: Number of sessions to process per batch
            retention_days: Days of raw data to retain
        """
        async with self.db_session_maker() as session:
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
                
                offset = 0
                while True:
                    # Get batch of voice sessions to aggregate
                    batch_sessions = await session.execute(
                        text("""
                            SELECT user_id, channel_id, session_start, session_end, duration_seconds, guild_id
                            FROM voice_stats
                            WHERE session_start < :cutoff_date
                            ORDER BY session_start ASC
                            LIMIT :batch_size OFFSET :offset
                        """),
                        {
                            'cutoff_date': cutoff_date,
                            'batch_size': batch_size,
                            'offset': offset
                        }
                    )
                    
                    sessions = batch_sessions.fetchall()
                    if not sessions:
                        break
                    
                    # Aggregate this batch
                    for session in sessions:
                        month = session.session_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        
                        await self._aggregate_single_voice_session(
                            user_id=session.user_id,
                            month=month,
                            duration_seconds=session.duration_seconds,
                            channel_id=session.channel_id,
                            guild_id=session.guild_id
                        )
                    
                    # Delete processed batch
                    await session.execute(
                        text("""
                            DELETE FROM voice_stats
                            WHERE session_start < :cutoff_date
                            AND id IN (
                                SELECT id FROM voice_stats
                                WHERE session_start < :cutoff_date
                                ORDER BY session_start ASC
                                LIMIT :batch_size OFFSET :offset
                            )
                        """),
                        {
                            'cutoff_date': cutoff_date,
                            'batch_size': batch_size,
                            'offset': offset
                        }
                    )
                    
                    await session.commit()
                    offset += batch_size
                    
                    logger.debug(f"Aggregated voice batch", offset=offset, batch_size=batch_size)
                
                logger.info("Voice statistics aggregation completed", retention_days=retention_days)
                
            except SQLAlchemyError as e:
                logger.error("Failed to aggregate voice stats", error=str(e))
                await session.rollback()
    
    async def _aggregate_single_voice_session(self, user_id: int, month: datetime, 
                                            duration_seconds: int, channel_id: int,
                                            guild_id: Optional[int]):
        """Aggregate single voice session into monthly stats"""
        try:
            async with self.db_session_maker() as session:
                # Use UPSERT for monthly voice stats
                await session.execute(
                    text("""
                        INSERT INTO monthly_user_voice_stats (user_id, month, total_voice_time_seconds, 
                                                            unique_channels, avg_session_duration)
                        VALUES (:user_id, :month, :duration_seconds, 1, :duration_seconds)
                        ON CONFLICT (user_id, month) DO UPDATE SET
                            total_voice_time_seconds = monthly_user_voice_stats.total_voice_time_seconds + :duration_seconds,
                            unique_channels = (
                                SELECT COUNT(DISTINCT channel_id)
                                FROM voice_stats
                                WHERE user_id = :user_id AND DATE_TRUNC('month', session_start) = :month
                            ),
                            avg_session_duration = (
                                (monthly_user_voice_stats.total_voice_time_seconds * monthly_user_voice_stats.avg_session_duration + :duration_seconds * :duration_seconds) /
                                (monthly_user_voice_stats.total_voice_time_seconds + :duration_seconds)
                            )
                    """),
                    {
                        'user_id': user_id,
                        'month': month,
                        'duration_seconds': duration_seconds,
                        'channel_id': channel_id
                    }
                )
                
                await session.commit()
                
        except SQLAlchemyError as e:
            logger.error("Failed to aggregate single voice session", user_id=user_id, month=month, error=str(e))
    
    async def get_user_stats(self, user_id: int, guild_id: int, time_period: str) -> Dict[str, Any]:
        """
        Get user statistics for specified time period
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            time_period: Time period ('today', 'week', 'month', 'all')
        
        Returns:
            User statistics dictionary
        """
        try:
            async with self.db_session_maker() as session:
                # Determine date range
                now = datetime.utcnow()
                
                if time_period == 'today':
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
                elif time_period == 'week':
                    start_date = now - timedelta(days=now.weekday())  # Monday
                    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
                elif time_period == 'month':
                    start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    if now.month == 12:
                        end_date = (now.replace(year=now.year+1, month=1, day=1) - timedelta(seconds=1))
                    else:
                        end_date = now.replace(month=now.month+1, day=1) - timedelta(seconds=1)
                else:  # all time
                    start_date = datetime.min.replace(tzinfo=now.tzinfo)
                    end_date = now
                
                # Get message stats
                message_stats = await session.execute(
                    text("""
                        SELECT 
                            COUNT(*) as message_count,
                            AVG(content_length) as avg_message_length,
                            SUM(CASE WHEN has_attachments THEN 1 ELSE 0 END) as attachments_count
                        FROM message_stats
                        WHERE user_id = :user_id
                        AND guild_id = :guild_id
                        AND sent_at >= :start_date
                        AND sent_at <= :end_date
                    """),
                    {
                        'user_id': user_id,
                        'guild_id': guild_id,
                        'start_date': start_date,
                        'end_date': end_date
                    }
                )
                
                msg_result = message_stats.fetchone()
                
                # Get voice stats
                voice_stats = await session.execute(
                    text("""
                        SELECT 
                            COALESCE(SUM(duration_seconds), 0) as total_voice_seconds,
                            COUNT(DISTINCT channel_id) as unique_voice_channels
                        FROM voice_stats
                        WHERE user_id = :user_id
                        AND guild_id = :guild_id
                        AND session_start >= :start_date
                        AND (session_end <= :end_date OR session_end IS NULL)
                    """),
                    {
                        'user_id': user_id,
                        'guild_id': guild_id,
                        'start_date': start_date,
                        'end_date': end_date
                    }
                )
                
                voice_result = voice_stats.fetchone()
                
                # Get invite stats
                invite_stats = await session.execute(
                    text("""
                        SELECT COUNT(*) as invites_created
                        FROM invite_stats
                        WHERE creator_id = :user_id
                        AND guild_id = :guild_id
                        AND created_at >= :start_date
                        AND (expires_at <= :end_date OR expires_at IS NULL)
                    """),
                    {
                        'user_id': user_id,
                        'guild_id': guild_id,
                        'start_date': start_date,
                        'end_date': end_date
                    }
                )
                
                invite_result = invite_stats.fetchone()
                
                # Compile results
                stats = {
                    'user_id': user_id,
                    'time_period': time_period,
                    'message_count': msg_result.message_count or 0,
                    'avg_message_length': round(msg_result.avg_message_length or 0, 1),
                    'attachments_count': msg_result.attachments_count or 0,
                    'total_voice_time_seconds': voice_result.total_voice_seconds or 0,
                    'unique_voice_channels': voice_result.unique_voice_channels or 0,
                    'invites_created': invite_result.invites_created or 0,
                    'activity_score': self.calculate_activity_score(
                        msg_result.message_count or 0,
                        voice_result.total_voice_seconds or 0,
                        invite_result.invites_created or 0
                    )
                }
                
                await session.commit()
                return stats
                
        except SQLAlchemyError as e:
            logger.error("Failed to get user stats", user_id=user_id, error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error getting user stats", user_id=user_id, error=str(e))
            return None
    
    def calculate_activity_score(self, messages: int, voice_seconds: int, invites: int) -> float:
        """
        Calculate overall activity score for user
        
        Args:
            messages: Number of messages
            voice_seconds: Total voice time in seconds
            invites: Number of invites created
        
        Returns:
            Activity score (0-100)
        """
        # Weighted scoring system
        message_score = min(messages * 0.1, 40)  # Max 40 points for messages
        voice_score = min((voice_seconds / 3600) * 5, 30)  # Max 30 points for 10 hours voice
        invite_score = min(invites * 10, 20)  # Max 20 points for 2 invites
        
        total_score = message_score + voice_score + invite_score
        return min(total_score, 100.0)
    
    async def get_server_stats(self, guild_id: int, time_period: str) -> Dict[str, Any]:
        """
        Get server-wide statistics
        
        Args:
            guild_id: Discord guild ID
            time_period: Time period
        
        Returns:
            Server statistics dictionary
        """
        try:
            async with self.db_session_maker() as session:
                # Determine date range
                now = datetime.utcnow()
                
                if time_period == 'today':
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
                elif time_period == 'week':
                    start_date = now - timedelta(days=now.weekday())
                    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
                elif time_period == 'month':
                    start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    if now.month == 12:
                        end_date = (now.replace(year=now.year+1, month=1, day=1) - timedelta(seconds=1))
                    else:
                        end_date = now.replace(month=now.month+1, day=1) - timedelta(seconds=1)
                else:  # all time
                    start_date = datetime.min.replace(tzinfo=now.tzinfo)
                    end_date = now
                
                # Get overall message stats
                message_stats = await session.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_messages,
                            AVG(content_length) as avg_message_length,
                            COUNT(DISTINCT user_id) as unique_authors,
                            COUNT(DISTINCT channel_id) as active_channels
                        FROM message_stats
                        WHERE guild_id = :guild_id
                        AND sent_at >= :start_date
                        AND sent_at <= :end_date
                    """),
                    {
                        'guild_id': guild_id,
                        'start_date': start_date,
                        'end_date': end_date
                    }
                )
                
                msg_result = message_stats.fetchone()
                
                # Get voice stats
                voice_stats = await session.execute(
                    text("""
                        SELECT
                            COALESCE(SUM(duration_seconds), 0) as total_voice_seconds,
                            COUNT(DISTINCT channel_id) as unique_voice_channels,
                            COUNT(*) as total_sessions
                        FROM voice_stats
                        WHERE user_id = :user_id
                        AND guild_id = :guild_id
                        AND session_start >= :start_date
                        AND (session_end <= :end_date OR session_end IS NULL)
                    """),
                    {
                        'user_id': user_id,
                        'guild_id': guild_id,
                        'start_date': start_date,
                        'end_date': end_date
                    }
                )

                voice_result = voice_stats.fetchone()

                # Get invite stats
                invite_stats = await session.execute(
                    text("""
                        SELECT COUNT(*) as invites_created
                        FROM invite_stats
                        WHERE creator_id = :user_id
                        AND guild_id = :guild_id
                        AND created_at >= :start_date
                        AND (expires_at <= :end_date OR expires_at IS NULL)
                    """),
                    {
                        'user_id': user_id,
                        'guild_id': guild_id,
                        'start_date': start_date,
                        'end_date': end_date
                    }
                )

                invite_result = invite_stats.fetchone()

                # Compile results
                stats = {
                    'user_id': user_id,
                    'time_period': time_period,
                    'message_count': msg_result.message_count or 0,
                    'avg_message_length': round(msg_result.avg_message_length or 0, 1),
                    'attachments_count': msg_result.attachments_count or 0,
                    'total_voice_time_seconds': voice_result.total_voice_seconds or 0,
                    'unique_voice_channels': voice_result.unique_voice_channels or 0,
                    'invites_created': invite_result.invites_created or 0,
                    'activity_score': self.calculate_activity_score(
                        msg_result.message_count or 0,
                        voice_result.total_voice_seconds or 0,
                        invite_result.invites_created or 0
                    )
                }

                await session.commit()
                return stats

        except SQLAlchemyError as e:
            logger.error("Failed to get user stats", user_id=user_id, error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error getting user stats", user_id=user_id, error=str(e))
            return None