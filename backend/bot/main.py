"""
Discord Bot Main Application
Main entry point for the discord.py bot worker
"""
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path
import discord
from discord.ext import commands, tasks
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from structlog import get_logger

from config import get_config
from database import get_db_session
from cogs import embed_cog, stats_cog, giveaway_cog, media_cog, llm_cog, watchparty_cog
from utils import setup_logging, handle_bot_error, discord_utils, media_clients, llm_client
from services import stats_service, giveaway_service, media_service, notification_service

# Configure logging
logger = get_logger()
setup_logging()

# Global variables
bot: Optional[commands.Bot] = None
scheduler: Optional[AsyncIOScheduler] = None
db_session = None

class DiscordBot(commands.Bot):
    """Custom Discord bot with extended functionality"""
    
    def __init__(self, config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guild_messages = True
        intents.guild_reactions = True
        intents.guild_voice_states = True
        intents.guild_invites = True
        intents.guild_members = True
        intents.guild_scheduled_events = True
        
        super().__init__(
            command_prefix=commands.when_mentioned_or(config['BOT_PREFIX']),
            intents=intents,
            help_command=None,
            case_insensitive=True,
            owner_id=config['OWNER_ID']
        )
        
        self.config = config
        self.db_session = db_session
        self.start_time = None
        self.guild_id = config['DISCORD_GUILD_ID']
        self.notification_channel_id = config['NOTIFICATION_CHANNEL_ID']
        self.giveaway_channel_id = config['GIVEAWAY_CHANNEL_ID']
        self.media_release_channel_id = config['MEDIA_RELEASE_CHANNEL_ID']
        
        # Initialize services
        self.stats_service = stats_service.StatsService(self.db_session)
        self.giveaway_service = giveaway_service.GiveawayService(self.db_session)
        self.media_service = media_service.MediaService()
        self.notification_service = notification_service.NotificationService(self)
        
        # Initialize external clients
        self.tmdb_client = media_clients.TMDBClient(config['TMDB_API_KEY'])
        self.anilist_client = media_clients.AniListClient()
        self.tvdb_client = media_clients.TVDBClient(config['TVDB_API_KEY'], config['TVDB_PIN'])
        self.llm_client = llm_client.OpenRouterClient(config['OPENROUTER_API_KEY'])
    
    async def setup_hook(self):
        """Setup bot before running"""
        # Wait for database to be ready
        await self.wait_for_database()
        
        # Load cogs
        await self.load_cogs()
        
        # Start scheduler
        await self.start_scheduler()
        
        # Set bot start time
        self.start_time = datetime.utcnow()
        
        logger.info("Bot setup completed", bot_id=self.user.id if self.user else None)
    
    async def wait_for_database(self):
        """Wait for database connection to be established"""
        max_retries = 30
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Test database connection
                with self.db_session() as session:
                    session.execute(text("SELECT 1"))
                    logger.info("Database connection established")
                    return
            except Exception as e:
                logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
        
        raise RuntimeError("Failed to connect to database after maximum retries")
    
    async def load_cogs(self):
        """Load all bot cogs"""
        cogs_to_load = [
            embed_cog.EmbedCog(self),
            stats_cog.StatsCog(self),
            giveaway_cog.GiveawayCog(self),
            media_cog.MediaCog(self),
            llm_cog.LLMCog(self),
            watchparty_cog.WatchPartyCog(self)
        ]
        
        for cog in cogs_to_load:
            try:
                await self.add_cog(cog)
                logger.info(f"Loaded cog: {cog.qualified_name}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog.qualified_name}: {e}")
    
    async def start_scheduler(self):
        """Start APScheduler with PostgreSQL job store"""
        global scheduler
        
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=self.config['DATABASE_URL'],
                tablename='apscheduler_jobs'
            )
        }
        
        scheduler = AsyncIOScheduler(timezone=self.config['SCHEDULER_TIMEZONE'], jobstores=jobstores)
        
        # Statistics aggregation job (hourly)
        scheduler.add_job(
            self.stats_service.aggregate_daily_stats,
            'cron',
            hour=self.config.get('STATS_AGGREGATION_HOUR', 2),
            minute=0,
            id='aggregate_daily_stats',
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=3600  # 1 hour
        )
        
        # Media release checking job (daily)
        scheduler.add_job(
            self.media_service.check_new_releases,
            'cron',
            hour=self.config.get('RELEASE_CHECK_HOUR', 8),
            minute=0,
            id='check_new_releases',
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=7200  # 2 hours
        )
        
        # Giveaway cleanup job (daily)
        scheduler.add_job(
            self.giveaway_service.cleanup_expired_giveaways,
            'cron',
            hour=3,
            minute=0,
            id='cleanup_giveaways',
            replace_existing=True,
            coalesce=True
        )
        
        # Watch party reminder job (every 5 minutes)
        scheduler.add_job(
            self.notification_service.send_watchparty_reminders,
            'interval',
            minutes=5,
            id='watchparty_reminders',
            replace_existing=True,
            coalesce=True,
            max_instances=1
        )
        
        scheduler.start()
        logger.info("APScheduler started with jobs", job_count=len(scheduler.get_jobs()))
    
    async def close(self):
        """Clean shutdown of bot and scheduler"""
        logger.info("Bot shutting down, performing cleanup")
        
        # Stop scheduler
        if scheduler:
            scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")
        
        # Close database session
        if self.db_session:
            self.db_session.remove()
        
        # Call parent close method
        await super().close()
    
    async def on_ready(self):
        """Event handler for when bot is ready"""
        logger.info(
            f"Bot logged in as {self.user} (ID: {self.user.id})",
            guilds=len(self.guilds),
            uptime=datetime.utcnow() - self.start_time
        )
        
        # Sync commands to Discord
        await self.sync_commands()
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | {self.config['BOT_PREFIX']}help"
            )
        )
        
        # Log bot status to notification channel
        await self.notification_service.log_bot_status()
    
    async def on_disconnect(self):
        """Event handler for bot disconnect"""
        logger.warning("Bot disconnected from Discord Gateway")
    
    async def on_resumed(self):
        """Event handler for bot resume after disconnect"""
        logger.info("Bot resumed connection to Discord Gateway")
    
    async def on_error(self, event, *args, **kwargs):
        """Global error handler for unhandled exceptions"""
        logger.error(f"Unhandled error in event {event}", exc_info=True, args=args, kwargs=kwargs)
        await handle_bot_error(self, event, *args, **kwargs)
    
    async def on_command_error(self, ctx, error):
        """Command error handler"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
            return
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param}", ephemeral=True)
            return
        
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided", ephemeral=True)
            return
        
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ This command is on cooldown. Try again in {error.retry_after:.1f}s", ephemeral=True)
            return
        
        # Log unexpected errors
        logger.error("Command error", command=ctx.command.qualified_name, user=ctx.author.id, error=str(error))
        await handle_bot_error(self, "command_error", ctx, error)
    
    async def sync_commands(self):
        """Sync slash commands to Discord"""
        try:
            synced = await self.tree.sync(guild=discord.Object(id=self.guild_id))
            logger.info(f"Synced {len(synced)} slash commands to guild {self.guild_id}")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
    
    async def on_guild_join(self, guild):
        """Event handler for joining new guild"""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        await self.notification_service.log_guild_join(guild)
    
    async def on_guild_remove(self, guild):
        """Event handler for leaving guild"""
        logger.info(f"Removed from guild: {guild.name} (ID: {guild.id})")
        await self.notification_service.log_guild_remove(guild)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down bot")
    if bot:
        asyncio.create_task(bot.close())
    sys.exit(0)


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def run_bot():
    """Main function to run the bot"""
    global bot, scheduler, db_session
    
    try:
        # Load configuration
        config = get_config('production')
        logger.info("Configuration loaded", env=config.ENV)
        
        # Setup database session
        db_session = get_db_session(config['DATABASE_URL'])
        
        # Create bot instance
        bot = DiscordBot(config)
        
        # Register global event handlers
        @bot.event
        async def on_message(message):
            # Ignore bot messages
            if message.author.bot:
                return
            
            # Log message for statistics
            await bot.stats_service.log_message(message)
            
            # Process commands
            await bot.process_commands(message)
        
        @bot.event
        async def on_voice_state_update(member, before, after):
            """Track voice channel activity"""
            await bot.stats_service.log_voice_activity(member, before, after)
        
        @bot.event
        async def on_invite_create(invite):
            """Track invite creation"""
            await bot.stats_service.log_invite_creation(invite)
        
        @bot.event
        async def on_reaction_add(reaction, user):
            """Handle reactions for giveaways and other features"""
            await bot.giveaway_service.handle_reaction(reaction, user)
        
        @bot.event
        async def on_scheduled_event_create(event):
            """Handle scheduled events for watch parties"""
            await bot.notification_service.handle_scheduled_event(event)
        
        # Setup signal handlers
        setup_signal_handlers()
        
        # Run bot
        async with bot:
            await bot.start(config['DISCORD_BOT_TOKEN'])
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Fatal error running bot", error=str(e))
    finally:
        # Cleanup
        if scheduler:
            scheduler.shutdown(wait=True)
        if db_session:
            db_session.remove()
        logger.info("Bot shutdown complete")


def main():
    """Entry point for the bot application"""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error("Unexpected error", error=str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()