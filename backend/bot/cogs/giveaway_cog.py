"""
Giveaway System Cog
Handles giveaway creation, reaction tracking, winner selection, and scheduling
"""
import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import discord
from discord.ext import commands, tasks
from discord import app_commands
from sqlalchemy import text, func
from sqlalchemy.exc import SQLAlchemyError
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.database import get_async_session
from bot.utils import DiscordUtils
from bot.config import settings
from bot.services.giveaway_service import GiveawayService

logger = logging.getLogger(__name__)

class GiveawayCog(commands.Cog):
    """Giveaway management system with reaction-based entries and automated winner selection"""
    
    def __init__(self, bot):
        self.bot = bot
        self.giveaway_service = GiveawayService(bot.db_session)
        self.entry_emoji = '🎉'  # Emoji for giveaway entries
        self.max_giveaway_duration = timedelta(seconds=settings.MAX_GIVEAWAY_DURATION)
        self.min_giveaway_duration = timedelta(seconds=settings.MIN_GIVEAWAY_DURATION)
        self.max_winners = settings.MAX_GIVEAWAY_WINNERS
        
        # Track active giveaways (message_id -> giveaway_id)
        self.active_giveaways = {}
        
        # Scheduled giveaway endings
        self.giveaway_scheduler = {}
        
        logger.info("Giveaway Cog initialized", max_winners=self.max_winners)
    
    @app_commands.command(name="giveaway", description="Create a new giveaway")
    @app_commands.describe(
        prize="The prize for the giveaway",
        duration="Duration in minutes (5-43200)",
        winners="Number of winners (1-10)",
        channel="Channel to post giveaway in (optional, defaults to current)",
        description="Additional description for the giveaway"
    )
    async def create_giveaway_command(self, interaction: discord.Interaction, 
                                    prize: str, duration: int, winners: int = 1,
                                    channel: Optional[discord.TextChannel] = None,
                                    description: Optional[str] = None):
        """
        Slash command to create a new giveaway
        
        Args:
            interaction: Discord interaction
            prize: The prize being given away
            duration: Duration in minutes
            winners: Number of winners
            channel: Specific channel to post in (optional)
            description: Additional description
        """
        # Permission check
        if not await self.user_has_permission(interaction.user, 'giveaways.create'):
            await interaction.response.send_message("❌ You don't have permission to create giveaways.", ephemeral=True)
            return
        
        # Validate parameters
        duration = max(5, min(43200, duration))  # 5 min to 30 days
        winners = max(1, min(10, winners))
        
        if duration * 60 < self.min_giveaway_duration.total_seconds():
            await interaction.response.send_message(
                f"❌ Giveaway duration must be at least {self.min_giveaway_duration.total_seconds() // 60} minutes.",
                ephemeral=True
            )
            return
        
        # Defer response for processing
        await interaction.response.defer()
        
        try:
            # Create giveaway in database
            giveaway = await self.giveaway_service.create_giveaway(
                creator_id=interaction.user.id,
                guild_id=interaction.guild.id,
                channel_id=(channel or interaction.channel).id,
                prize=prize,
                winner_count=winners,
                duration_minutes=duration,
                description=description,
                status='scheduled'
            )
            
            if not giveaway:
                await interaction.followup.send("❌ Failed to create giveaway. Please try again.", ephemeral=True)
                return
            
            # Schedule giveaway end
            end_time = datetime.utcnow() + timedelta(minutes=duration)
            await self.schedule_giveaway_end(giveaway.id, end_time)
            
            # Create giveaway message
            embed = self.create_giveaway_embed(giveaway)
            
            # Send giveaway message
            giveaway_message = await DiscordUtils.safe_send_message(
                channel or interaction.channel,
                embed=embed
            )
            
            if giveaway_message:
                # Add reaction for entry
                await giveaway_message.add_reaction(self.entry_emoji)
                
                # Update giveaway with message ID
                giveaway.message_id = giveaway_message.id
                await self.giveaway_service.update_giveaway_message_id(giveaway.id, giveaway_message.id)
                
                # Start reaction listener
                self.active_giveaways[giveaway_message.id] = giveaway.id
                
                await interaction.followup.send(
                    f"✅ Giveaway created successfully! Check it out in {channel.mention if channel else interaction.channel.mention}",
                    ephemeral=True
                )
                
                logger.info(
                    "Giveaway created",
                    giveaway_id=giveaway.id,
                    creator_id=interaction.user.id,
                    prize=prize[:50],
                    duration=duration,
                    winners=winners
                )
            else:
                # Cleanup failed giveaway
                await self.giveaway_service.delete_giveaway(giveaway.id)
                await interaction.followup.send("❌ Failed to post giveaway message. Giveaway cancelled.", ephemeral=True)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid giveaway parameters: {str(e)}", ephemeral=True)
            logger.warning("Invalid giveaway parameters", creator_id=interaction.user.id, error=str(e))
        except SQLAlchemyError as e:
            await interaction.followup.send("❌ Database error occurred while creating giveaway.", ephemeral=True)
            logger.error("Database error creating giveaway", creator_id=interaction.user.id, error=str(e))
        except Exception as e:
            await interaction.followup.send("❌ An unexpected error occurred while creating the giveaway.", ephemeral=True)
            logger.error("Unexpected error creating giveaway", creator_id=interaction.user.id, error=str(e))
    
    @app_commands.command(name="end_giveaway", description="End giveaway early")
    @app_commands.describe(message_id="Message ID of giveaway to end")
    async def end_giveaway_command(self, interaction: discord.Interaction, message_id: str):
        """
        Slash command to end giveaway early
        
        Args:
            interaction: Discord interaction
            message_id: Message ID of the giveaway
        """
        # Permission check
        if not await self.user_has_permission(interaction.user, 'giveaways.manage'):
            await interaction.response.send_message("❌ You don't have permission to end giveaways.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            giveaway_id = self.active_giveaways.get(int(message_id))
            if not giveaway_id:
                await interaction.followup.send("❌ No active giveaway found with that message ID.", ephemeral=True)
                return
            
            # End giveaway
            success = await self.end_giveaway(giveaway_id, manual=True)
            
            if success:
                await interaction.followup.send("✅ Giveaway ended successfully!", ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to end giveaway.", ephemeral=True)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid message ID: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Failed to end giveaway. Please try again.", ephemeral=True)
            logger.error("End giveaway command failed", user_id=interaction.user.id, message_id=message_id, error=str(e))
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """
        Handle reactions for giveaway entries
        
        Args:
            reaction: Discord reaction
            user: User who added reaction
        """
        if user.bot:
            return
        
        # Check if reaction is for a giveaway
        message_id = reaction.message.id
        giveaway_id = self.active_giveaways.get(message_id)
        if not giveaway_id:
            return
        
        # Check if it's the entry emoji
        if str(reaction.emoji) != self.entry_emoji:
            return
        
        try:
            # Add user to giveaway entries
            success = await self.giveaway_service.add_entry(
                giveaway_id=giveaway_id,
                user_id=user.id,
                guild_id=reaction.message.guild.id
            )
            
            if success:
                logger.debug("Giveaway entry added", giveaway_id=giveaway_id, user_id=user.id)
            else:
                # Remove reaction if entry failed (e.g., already entered, giveaway ended)
                await reaction.remove(user)
                logger.debug("Failed to add giveaway entry, removed reaction", giveaway_id=giveaway_id, user_id=user.id)
                
        except SQLAlchemyError as e:
            logger.error("Database error handling giveaway reaction", giveaway_id=giveaway_id, user_id=user.id, error=str(e))
            await reaction.remove(user)
        except Exception as e:
            logger.error("Unexpected error handling giveaway reaction", giveaway_id=giveaway_id, user_id=user.id, error=str(e))
            await reaction.remove(user)
    
    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """
        Handle reaction removal for giveaway entries
        
        Args:
            reaction: Discord reaction
            user: User who removed reaction
        """
        if user.bot:
            return
        
        # Check if reaction is for a giveaway
        message_id = reaction.message.id
        giveaway_id = self.active_giveaways.get(message_id)
        if not giveaway_id:
            return
        
        # Check if it's the entry emoji
        if str(reaction.emoji) != self.entry_emoji:
            return
        
        try:
            # Remove user from giveaway entries (if allowed)
            success = await self.giveaway_service.remove_entry(
                giveaway_id=giveaway_id,
                user_id=user.id
            )
            
            if success:
                logger.debug("Giveaway entry removed", giveaway_id=giveaway_id, user_id=user.id)
            else:
                logger.debug("No entry found to remove", giveaway_id=giveaway_id, user_id=user.id)
                
        except SQLAlchemyError as e:
            logger.error("Database error handling giveaway reaction removal", giveaway_id=giveaway_id, user_id=user.id, error=str(e))
        except Exception as e:
            logger.error("Unexpected error handling giveaway reaction removal", giveaway_id=giveaway_id, user_id=user.id, error=str(e))
    
    async def schedule_giveaway_end(self, giveaway_id: int, end_time: datetime):
        """
        Schedule giveaway end time with APScheduler
        
        Args:
            giveaway_id: Giveaway ID
            end_time: When giveaway should end
        """
        try:
            # Add job to scheduler
            job = self.bot.scheduler.add_job(
                self.end_giveaway,
                'date',
                run_date=end_time,
                args=[giveaway_id],
                id=f"giveaway_end_{giveaway_id}",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=3600  # 1 hour grace period
            )
            
            self.giveaway_scheduler[giveaway_id] = job
            logger.info("Scheduled giveaway end", giveaway_id=giveaway_id, end_time=end_time.isoformat())
            
        except Exception as e:
            logger.error("Failed to schedule giveaway end", giveaway_id=giveaway_id, error=str(e))
    
    async def end_giveaway(self, giveaway_id: int, manual: bool = False):
        """
        End giveaway and select winners
        
        Args:
            giveaway_id: Giveaway ID to end
            manual: Whether this is a manual end (admin action)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get giveaway details
            giveaway = await self.giveaway_service.get_giveaway(giveaway_id)
            if not giveaway:
                logger.error("Giveaway not found for ending", giveaway_id=giveaway_id)
                return False
            
            # Check if already ended
            if giveaway.status != 'active':
                logger.warning("Giveaway already ended", giveaway_id=giveaway_id, status=giveaway.status)
                return False
            
            # Get channel
            channel = self.bot.get_channel(giveaway.channel_id)
            if not channel:
                logger.error("Giveaway channel not found", giveaway_id=giveaway_id, channel_id=giveaway.channel_id)
                return False
            
            # Get message
            message = await channel.fetch_message(giveaway.message_id)
            if not message:
                logger.error("Giveaway message not found", giveaway_id=giveaway_id, message_id=giveaway.message_id)
                return False
            
            # Get entries
            entries = await self.giveaway_service.get_entries(giveaway_id)
            if not entries:
                await channel.send("🏆 **Giveaway Ended** - No entries received :(")
                await self.giveaway_service.update_giveaway_status(giveaway_id, 'ended', 'no_entries')
                return True
            
            # Select winners
            winners = await self.select_winners(entries, giveaway.winner_count)
            
            if winners:
                # Announce winners
                winner_list = []
                for winner in winners:
                    user = self.bot.get_user(winner.user_id)
                    if user:
                        winner_list.append(user.mention)
                    else:
                        winner_list.append(f"<@{winner.user_id}>")
                
                # Create winner announcement embed
                embed = discord.Embed(
                    title="🎉 Giveaway Winners Selected!",
                    description=f"Congratulations to the winners of **{giveaway.prize}**!\n\n" + "\n".join(winner_list),
                    color=discord.Color.gold(),
                    timestamp=datetime.utcnow()
                )
                
                if giveaway.description:
                    embed.add_field(name="Prize Details", value=giveaway.description, inline=False)
                
                embed.add_field(
                    name="Entries Received",
                    value=str(len(entries)),
                    inline=True
                )
                
                embed.add_field(
                    name="Winners",
                    value=str(giveaway.winner_count),
                    inline=True
                )
                
                # Send announcement
                await channel.send("@everyone", embed=embed)
                
                # Mark winners in database
                await self.giveaway_service.mark_winners(giveaway_id, [w.user_id for w in winners])
                
                logger.info(
                    "Giveaway ended with winners",
                    giveaway_id=giveaway_id,
                    winners=[w.user_id for w in winners],
                    total_entries=len(entries),
                    manual=manual
                )
            else:
                await channel.send("🏆 **Giveaway Ended** - No valid winners could be selected.")
                logger.warning("No valid winners selected for giveaway", giveaway_id=giveaway_id, entries=len(entries))
            
            # Update giveaway status
            await self.giveaway_service.update_giveaway_status(giveaway_id, 'ended', 'completed' if winners else 'no_winners')
            
            # Remove from active giveaways
            for msg_id, g_id in list(self.active_giveaways.items()):
                if g_id == giveaway_id:
                    del self.active_giveaways[msg_id]
            
            # Remove from scheduler
            if giveaway_id in self.giveaway_scheduler:
                job = self.giveaway_scheduler.pop(giveaway_id)
                job.remove()
            
            return True
            
        except Exception as e:
            logger.error("Failed to end giveaway", giveaway_id=giveaway_id, error=str(e))
            return False
    
    async def select_winners(self, entries: List[Dict[str, Any]], num_winners: int) -> List[Dict[str, Any]]:
        """
        Select random winners from giveaway entries
        
        Args:
            entries: List of giveaway entries
            num_winners: Number of winners to select
        
        Returns:
            List of winner entries
        """
        if len(entries) < num_winners:
            logger.warning("Not enough entries for winners", entries=len(entries), needed=num_winners)
            return entries  # Return all entries if not enough
        
        # Random selection without replacement
        winner_indices = random.sample(range(len(entries)), num_winners)
        winners = [entries[i] for i in winner_indices]
        
        logger.debug("Winners selected", giveaway_id=entries[0]['giveaway_id'], winners=[w['user_id'] for w in winners])
        return winners
    
    def create_giveaway_embed(self, giveaway: Dict[str, Any]) -> discord.Embed:
        """
        Create Discord embed for giveaway message
        
        Args:
            giveaway: Giveaway data
        
        Returns:
            Discord embed for giveaway
        """
        end_time = datetime.fromisoformat(giveaway['end_at']) if giveaway['end_at'] else None
        remaining_time = end_time - datetime.utcnow() if end_time else None
        
        if remaining_time and remaining_time.total_seconds() > 0:
            hours, remainder = divmod(int(remaining_time.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            time_text = f"{hours}h {minutes}m remaining"
        else:
            time_text = "Ended"
        
        embed = discord.Embed(
            title="🎁 GIVEAWAY!",
            description=f"**Prize:** {giveaway['prize']}\n**Winners:** {giveaway['winner_count']}\n**Ends:** {time_text}",
            color=discord.Color.gold()
        )
        
        if giveaway['description']:
            embed.add_field(name="Details", value=giveaway['description'], inline=False)
        
        embed.add_field(
            name="How to Enter",
            value=f"React with {self.entry_emoji} to enter the giveaway!",
            inline=False
        )
        
        embed.set_footer(text=f"Hosted by {giveaway['creator_username']} | ID: {giveaway['id']}")
        embed.timestamp = datetime.utcnow()
        
        return embed
    
    async def user_has_permission(self, user: discord.User, permission: str) -> bool:
        """
        Check if user has permission for giveaway operations
        
        Args:
            user: Discord user
            permission: Permission type ('giveaways.create', 'giveaways.manage')
        
        Returns:
            True if user has permission
        """
        # Owner always has all permissions
        if user.id == settings.OWNER_ID:
            return True
        
        # Check guild roles
        guild = self.bot.get_guild(settings.DISCORD_GUILD_ID)
        if guild:
            member = guild.get_member(user.id)
            if member:
                allowed_roles = {
                    'giveaways.create': ['admin', 'moderator'],
                    'giveaways.manage': ['admin', 'moderator']
                }.get(permission, [])
                
                user_roles = [role.name.lower() for role in member.roles]
                return any(role in allowed_roles for role in user_roles)
        
        return False
    
    async def cog_load(self):
        """Called when cog is loaded"""
        logger.info("Giveaway Cog loaded", entry_emoji=self.entry_emoji, max_winners=self.max_winners)
    
    async def cog_unload(self):
        """Called when cog is unloaded"""
        # Cancel any running giveaway jobs
        for job in self.giveaway_scheduler.values():
            job.remove()
        self.giveaway_scheduler.clear()
        logger.info("Giveaway Cog unloaded")


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(GiveawayCog(bot))
    logger.info("Giveaway Cog registered with bot")