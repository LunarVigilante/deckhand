"""
Media Cog
Handles media search, watch parties, and release notifications
Integrates with TMDB, Anilist, and TheTVDB APIs
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import discord
from discord.ext import commands, tasks
from discord import app_commands
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.database import get_async_session
from bot.utils import DiscordUtils
from bot.config import settings

logger = logging.getLogger(__name__)

class MediaCog(commands.Cog):
    """Media management system with API integrations and watch parties"""

    def __init__(self, bot):
        self.bot = bot
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.max_search_results = settings.MAX_MEDIA_SEARCH_RESULTS
        self.release_check_interval = timedelta(hours=settings.RELEASE_CHECK_INTERVAL_HOURS)

        # API configurations
        self.tmdb_api_key = settings.TMDB_API_KEY
        self.tmdb_base_url = settings.TMDB_BASE_URL
        self.anilist_client_id = settings.ANILIST_CLIENT_ID
        self.anilist_client_secret = settings.ANILIST_CLIENT_SECRET
        self.anilist_base_url = settings.ANILIST_BASE_URL
        self.tvdb_api_key = settings.TVDB_API_KEY
        self.tvdb_pin = settings.TVDB_PIN
        self.tvdb_base_url = settings.TVDB_BASE_URL

        # TVDB authentication token
        self.tvdb_token = None
        self.tvdb_token_expires = None

        # Start background tasks
        self.check_releases.start()
        self.refresh_tvdb_token.start()

        logger.info("Media Cog initialized", max_results=self.max_search_results)

    @app_commands.command(name="media_search", description="Search for movies, TV shows, or anime")
    @app_commands.describe(
        query="Search query",
        media_type="Type of media to search for",
        limit="Maximum number of results (1-10)"
    )
    @app_commands.choices(
        media_type=[
            app_commands.Choice(name="Movies", value="movie"),
            app_commands.Choice(name="TV Shows", value="tv"),
            app_commands.Choice(name="Anime", value="anime")
        ]
    )
    async def media_search_command(self, interaction: discord.Interaction,
                                 query: str, media_type: str, limit: int = 5):
        """
        Slash command to search for media content

        Args:
            interaction: Discord interaction
            query: Search query
            media_type: Type of media (movie, tv, anime)
            limit: Maximum results to return
        """
        # Validate parameters
        limit = max(1, min(limit, 10))

        await interaction.response.defer()

        try:
            # Search based on media type
            if media_type == "movie":
                results = await self.search_tmdb_movies(query, limit)
            elif media_type == "tv":
                results = await self.search_tmdb_tv(query, limit)
            elif media_type == "anime":
                results = await self.search_anilist_anime(query, limit)
            else:
                await interaction.followup.send("❌ Invalid media type.", ephemeral=True)
                return

            if not results:
                await interaction.followup.send(f"❌ No {media_type} results found for '{query}'.", ephemeral=True)
                return

            # Create paginated embeds
            embeds = []
            for i, result in enumerate(results):
                embed = self.create_media_embed(result, media_type, i + 1, len(results))
                embeds.append(embed)

            # Send first embed
            await interaction.followup.send(embed=embeds[0])

            # Log search
            await self.log_media_search(
                user_id=interaction.user.id,
                query=query,
                media_type=media_type,
                results_count=len(results)
            )

            logger.info(
                "Media search executed",
                user_id=interaction.user.id,
                query=query[:50],
                media_type=media_type,
                results=len(results)
            )

        except Exception as e:
            await interaction.followup.send("❌ Failed to search media. Please try again.", ephemeral=True)
            logger.error("Media search failed", user_id=interaction.user.id, error=str(e))

    @app_commands.command(name="watchparty", description="Create a watch party event")
    @app_commands.describe(
        title="Title of the media to watch",
        start_time="When the watch party starts (HH:MM format)",
        description="Optional description",
        media_type="Type of media"
    )
    @app_commands.choices(
        media_type=[
            app_commands.Choice(name="Movie", value="movie"),
            app_commands.Choice(name="TV Show", value="tv"),
            app_commands.Choice(name="Anime", value="anime")
        ]
    )
    async def watchparty_command(self, interaction: discord.Interaction,
                               title: str, start_time: str, description: Optional[str] = None,
                               media_type: str = "movie"):
        """
        Slash command to create a watch party event

        Args:
            interaction: Discord interaction
            title: Media title
            start_time: Start time in HH:MM format
            description: Optional description
            media_type: Type of media
        """
        # Permission check
        if not await self.user_has_permission(interaction.user, 'watchparties.create'):
            await interaction.response.send_message("❌ You don't have permission to create watch parties.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            # Parse start time
            try:
                hours, minutes = map(int, start_time.split(':'))
                if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                    raise ValueError("Invalid time format")
            except ValueError:
                await interaction.followup.send("❌ Invalid time format. Use HH:MM (e.g., 20:30).", ephemeral=True)
                return

            # Calculate start datetime (today or tomorrow)
            now = datetime.utcnow()
            start_datetime = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

            if start_datetime <= now:
                start_datetime += timedelta(days=1)  # Schedule for tomorrow

            # Get media poster if possible
            poster_url = await self.get_media_poster(title, media_type)

            # Create Discord scheduled event
            event_data = {
                'name': f"🎬 Watch Party: {title}",
                'description': description or f"Join us for a watch party of {title}!",
                'scheduled_start_time': start_datetime.isoformat(),
                'scheduled_end_time': (start_datetime + timedelta(hours=2)).isoformat(),
                'privacy_level': 2,  # GUILD_ONLY
                'entity_type': 3,  # EXTERNAL
                'entity_metadata': {
                    'location': f"Discord Voice Channel - {title}"
                }
            }

            # Create the event via Discord API
            event = await interaction.guild.create_scheduled_event(**event_data)

            # Store in database
            await self.create_watch_party_event(
                event_id=event.id,
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                title=title,
                scheduled_start_time=start_datetime,
                description=description,
                creator_id=interaction.user.id,
                media_poster_url=poster_url,
                media_type=media_type
            )

            # Schedule reminder
            await self.schedule_watch_party_reminder(event.id, start_datetime)

            embed = discord.Embed(
                title="🎬 Watch Party Created!",
                description=f"**{title}**\n📅 {start_datetime.strftime('%A, %B %d at %I:%M %p UTC')}\n🎭 {media_type.title()}",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            if description:
                embed.add_field(name="Description", value=description, inline=False)

            if poster_url:
                embed.set_image(url=poster_url)

            embed.set_footer(text=f"Created by {interaction.user.display_name}")

            await interaction.followup.send(embed=embed)

            logger.info(
                "Watch party created",
                creator_id=interaction.user.id,
                title=title,
                start_time=start_datetime.isoformat(),
                media_type=media_type
            )

        except Exception as e:
            await interaction.followup.send("❌ Failed to create watch party. Please try again.", ephemeral=True)
            logger.error("Watch party creation failed", user_id=interaction.user.id, error=str(e))

    @app_commands.command(name="track_show", description="Track a TV show or anime for release notifications")
    @app_commands.describe(
        title="Title of the show to track",
        media_type="Type of media",
        notification_channel="Channel for notifications (optional)"
    )
    @app_commands.choices(
        media_type=[
            app_commands.Choice(name="TV Show", value="tv"),
            app_commands.Choice(name="Anime", value="anime")
        ]
    )
    async def track_show_command(self, interaction: discord.Interaction,
                               title: str, media_type: str,
                               notification_channel: Optional[discord.TextChannel] = None):
        """
        Slash command to track a show for release notifications

        Args:
            interaction: Discord interaction
            title: Show title
            media_type: Type of media (tv or anime)
            notification_channel: Channel for notifications
        """
        await interaction.response.defer()

        try:
            # Search for the show
            if media_type == "tv":
                results = await self.search_tmdb_tv(title, 5)
            elif media_type == "anime":
                results = await self.search_anilist_anime(title, 5)
            else:
                await interaction.followup.send("❌ Invalid media type.", ephemeral=True)
                return

            if not results:
                await interaction.followup.send(f"❌ No {media_type} shows found with title '{title}'.", ephemeral=True)
                return

            # Use the first result
            show = results[0]
            show_id = show.get('id')
            show_title = show.get('title') or show.get('name')

            # Check if already tracking
            existing = await self.get_tracked_show(interaction.user.id, str(show_id), media_type)
            if existing:
                await interaction.followup.send(f"❌ You're already tracking '{show_title}'.", ephemeral=True)
                return

            # Create tracking entry
            await self.create_tracked_show(
                user_id=interaction.user.id,
                show_id=str(show_id),
                show_title=show_title,
                api_source=media_type,
                notification_channel_id=notification_channel.id if notification_channel else None
            )

            embed = discord.Embed(
                title="📺 Show Tracking Started",
                description=f"Now tracking **{show_title}** for new episode notifications!",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(name="Type", value=media_type.title(), inline=True)
            embed.add_field(name="Notifications", value=notification_channel.mention if notification_channel else "DM", inline=True)

            if show.get('poster_path'):
                poster_url = f"https://image.tmdb.org/t/p/w500{show['poster_path']}"
                embed.set_thumbnail(url=poster_url)

            await interaction.followup.send(embed=embed)

            logger.info(
                "Show tracking started",
                user_id=interaction.user.id,
                show_title=show_title,
                media_type=media_type
            )

        except Exception as e:
            await interaction.followup.send("❌ Failed to start tracking. Please try again.", ephemeral=True)
            logger.error("Show tracking failed", user_id=interaction.user.id, error=str(e))

    @app_commands.command(name="untrack_show", description="Stop tracking a show")
    @app_commands.describe(title="Title of the show to stop tracking")
    async def untrack_show_command(self, interaction: discord.Interaction, title: str):
        """
        Slash command to stop tracking a show

        Args:
            interaction: Discord interaction
            title: Show title to stop tracking
        """
        await interaction.response.defer()

        try:
            # Find tracked show
            tracked_shows = await self.get_user_tracked_shows(interaction.user.id)

            # Find matching show (case-insensitive partial match)
            matching_show = None
            for show in tracked_shows:
                if title.lower() in show['show_title'].lower():
                    matching_show = show
                    break

            if not matching_show:
                await interaction.followup.send(f"❌ No tracked show found matching '{title}'.", ephemeral=True)
                return

            # Remove tracking
            await self.remove_tracked_show(matching_show['id'])

            embed = discord.Embed(
                title="📺 Show Tracking Stopped",
                description=f"No longer tracking **{matching_show['show_title']}**.",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )

            await interaction.followup.send(embed=embed)

            logger.info(
                "Show tracking stopped",
                user_id=interaction.user.id,
                show_title=matching_show['show_title']
            )

        except Exception as e:
            await interaction.followup.send("❌ Failed to stop tracking. Please try again.", ephemeral=True)
            logger.error("Show untracking failed", user_id=interaction.user.id, error=str(e))

    @app_commands.command(name="my_tracked_shows", description="List your tracked shows")
    async def my_tracked_shows_command(self, interaction: discord.Interaction):
        """List user's tracked shows"""
        await interaction.response.defer()

        try:
            tracked_shows = await self.get_user_tracked_shows(interaction.user.id)

            if not tracked_shows:
                await interaction.followup.send("📺 You aren't tracking any shows yet. Use `/track_show` to start tracking!", ephemeral=True)
                return

            embed = discord.Embed(
                title="📺 Your Tracked Shows",
                description=f"Tracking {len(tracked_shows)} show(s):",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            show_list = []
            for show in tracked_shows[:10]:  # Limit to 10
                show_list.append(f"• **{show['show_title']}** ({show['api_source'].title()})")

            embed.description += "\n" + "\n".join(show_list)

            if len(tracked_shows) > 10:
                embed.set_footer(text=f"And {len(tracked_shows) - 10} more...")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send("❌ Failed to retrieve tracked shows.", ephemeral=True)
            logger.error("My tracked shows failed", user_id=interaction.user.id, error=str(e))

    # API Integration Methods
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_tmdb_movies(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search TMDB for movies"""
        if not self.tmdb_api_key:
            logger.warning("TMDB API key not configured")
            return []

        try:
            url = f"{self.tmdb_base_url}/search/movie"
            params = {
                'api_key': self.tmdb_api_key,
                'query': query,
                'language': 'en-US',
                'page': 1
            }

            async with self.http_client as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for movie in data.get('results', [])[:limit]:
                results.append({
                    'id': movie['id'],
                    'title': movie['title'],
                    'overview': movie.get('overview', ''),
                    'release_date': movie.get('release_date', ''),
                    'poster_path': movie.get('poster_path'),
                    'vote_average': movie.get('vote_average', 0),
                    'genre_ids': movie.get('genre_ids', [])
                })

            return results

        except Exception as e:
            logger.error("TMDB movie search failed", query=query, error=str(e))
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_tmdb_tv(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search TMDB for TV shows"""
        if not self.tmdb_api_key:
            logger.warning("TMDB API key not configured")
            return []

        try:
            url = f"{self.tmdb_base_url}/search/tv"
            params = {
                'api_key': self.tmdb_api_key,
                'query': query,
                'language': 'en-US',
                'page': 1
            }

            async with self.http_client as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for show in data.get('results', [])[:limit]:
                results.append({
                    'id': show['id'],
                    'name': show['name'],
                    'title': show['name'],  # For compatibility
                    'overview': show.get('overview', ''),
                    'first_air_date': show.get('first_air_date', ''),
                    'poster_path': show.get('poster_path'),
                    'vote_average': show.get('vote_average', 0),
                    'genre_ids': show.get('genre_ids', [])
                })

            return results

        except Exception as e:
            logger.error("TMDB TV search failed", query=query, error=str(e))
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_anilist_anime(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Anilist for anime"""
        if not self.anilist_client_id:
            logger.warning("Anilist credentials not configured")
            return []

        try:
            query_string = """
            query ($search: String, $limit: Int) {
                Page(page: 1, perPage: $limit) {
                    media(search: $search, type: ANIME, sort: POPULARITY_DESC) {
                        id
                        title {
                            romaji
                            english
                        }
                        description
                        startDate {
                            year
                            month
                            day
                        }
                        coverImage {
                            large
                        }
                        averageScore
                        genres
                    }
                }
            }
            """

            variables = {
                'search': query,
                'limit': limit
            }

            async with self.http_client as client:
                response = await client.post(
                    self.anilist_base_url,
                    json={'query': query_string, 'variables': variables}
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for media in data.get('data', {}).get('Page', {}).get('media', []):
                title = media['title']['english'] or media['title']['romaji']
                description = media.get('description', '').replace('<br>', '\n').replace('<i>', '').replace('</i>', '')

                results.append({
                    'id': media['id'],
                    'title': title,
                    'overview': description[:500] + '...' if len(description) > 500 else description,
                    'release_date': f"{media['startDate']['year']}-{media['startDate']['month']:02d}-{media['startDate']['day']:02d}",
                    'poster_path': media['coverImage']['large'],
                    'vote_average': media.get('averageScore', 0),
                    'genres': media.get('genres', [])
                })

            return results

        except Exception as e:
            logger.error("Anilist anime search failed", query=query, error=str(e))
            return []

    async def get_media_poster(self, title: str, media_type: str) -> Optional[str]:
        """Get poster URL for media title"""
        try:
            if media_type in ['movie', 'tv']:
                results = await self.search_tmdb_movies(title, 1) if media_type == 'movie' else await self.search_tmdb_tv(title, 1)
            elif media_type == 'anime':
                results = await self.search_anilist_anime(title, 1)
            else:
                return None

            if results and results[0].get('poster_path'):
                if media_type == 'anime':
                    return results[0]['poster_path']
                else:
                    return f"https://image.tmdb.org/t/p/w500{results[0]['poster_path']}"

        except Exception as e:
            logger.error("Failed to get media poster", title=title, media_type=media_type, error=str(e))

        return None

    def create_media_embed(self, media: Dict[str, Any], media_type: str, index: int, total: int) -> discord.Embed:
        """Create Discord embed for media result"""
        title = media.get('title') or media.get('name', 'Unknown Title')
        overview = media.get('overview', 'No description available.')
        release_date = media.get('release_date') or media.get('first_air_date', 'Unknown')

        embed = discord.Embed(
            title=f"🎬 {title}",
            description=overview[:1000] + '...' if len(overview) > 1000 else overview,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        embed.add_field(name="Type", value=media_type.title(), inline=True)
        embed.add_field(name="Release Date", value=release_date, inline=True)

        if media.get('vote_average'):
            embed.add_field(name="Rating", value=f"⭐ {media['vote_average']}/10", inline=True)

        if media.get('genres') and len(media['genres']) > 0:
            genres = media['genres'][:3]  # Limit to 3 genres
            embed.add_field(name="Genres", value=", ".join(genres), inline=False)

        if media.get('poster_path'):
            if media_type == 'anime':
                embed.set_thumbnail(url=media['poster_path'])
            else:
                embed.set_thumbnail(url=f"https://image.tmdb.org/t/p/w300{media['poster_path']}")

        embed.set_footer(text=f"Result {index}/{total}")

        return embed

    # Database Operations
    async def log_media_search(self, user_id: int, query: str, media_type: str, results_count: int):
        """Log media search to database"""
        async with get_async_session() as session:
            try:
                await session.execute(
                    text("""
                        INSERT INTO MediaSearchHistory (user_id, query, media_type, api_source, results_count, searched_at)
                        VALUES (:user_id, :query, :media_type, :api_source, :results_count, :searched_at)
                    """),
                    {
                        'user_id': user_id,
                        'query': query,
                        'media_type': media_type,
                        'api_source': media_type,
                        'results_count': results_count,
                        'searched_at': datetime.utcnow()
                    }
                )
                await session.commit()
            except SQLAlchemyError as e:
                logger.error("Failed to log media search", user_id=user_id, error=str(e))

    async def create_watch_party_event(self, event_id: int, guild_id: int, channel_id: int,
                                     title: str, scheduled_start_time: datetime,
                                     description: Optional[str], creator_id: int,
                                     media_poster_url: Optional[str], media_type: str):
        """Create watch party event in database"""
        async with get_async_session() as session:
            try:
                await session.execute(
                    text("""
                        INSERT INTO WatchPartyEvents (event_id, guild_id, channel_id, title,
                                                    scheduled_start_time, description, creator_id,
                                                    media_poster_url, status)
                        VALUES (:event_id, :guild_id, :channel_id, :title, :scheduled_start_time,
                               :description, :creator_id, :media_poster_url, 'scheduled')
                    """),
                    {
                        'event_id': event_id,
                        'guild_id': guild_id,
                        'channel_id': channel_id,
                        'title': title,
                        'scheduled_start_time': scheduled_start_time,
                        'description': description,
                        'creator_id': creator_id,
                        'media_poster_url': media_poster_url
                    }
                )
                await session.commit()
            except SQLAlchemyError as e:
                logger.error("Failed to create watch party event", event_id=event_id, error=str(e))
                await session.rollback()

    async def create_tracked_show(self, user_id: int, show_id: str, show_title: str,
                                api_source: str, notification_channel_id: Optional[int]):
        """Create tracked show entry"""
        async with get_async_session() as session:
            try:
                await session.execute(
                    text("""
                        INSERT INTO TrackShows (user_id, show_id, show_title, api_source,
                                              notification_channel_id, is_active)
                        VALUES (:user_id, :show_id, :show_title, :api_source,
                               :notification_channel_id, true)
                    """),
                    {
                        'user_id': user_id,
                        'show_id': show_id,
                        'show_title': show_title,
                        'api_source': api_source,
                        'notification_channel_id': notification_channel_id
                    }
                )
                await session.commit()
            except SQLAlchemyError as e:
                logger.error("Failed to create tracked show", user_id=user_id, show_title=show_title, error=str(e))
                await session.rollback()

    async def get_tracked_show(self, user_id: int, show_id: str, api_source: str) -> Optional[Dict[str, Any]]:
        """Get tracked show entry"""
        async with get_async_session() as session:
            try:
                result = await session.execute(
                    text("""
                        SELECT * FROM TrackShows
                        WHERE user_id = :user_id AND show_id = :show_id AND api_source = :api_source
                    """),
                    {
                        'user_id': user_id,
                        'show_id': show_id,
                        'api_source': api_source
                    }
                )
                row = result.fetchone()
                return dict(row) if row else None
            except SQLAlchemyError as e:
                logger.error("Failed to get tracked show", user_id=user_id, show_id=show_id, error=str(e))
                return None

    async def get_user_tracked_shows(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all tracked shows for user"""
        async with get_async_session() as session:
            try:
                result = await session.execute(
                    text("""
                        SELECT * FROM TrackShows
                        WHERE user_id = :user_id AND is_active = true
                        ORDER BY created_at DESC
                    """),
                    {'user_id': user_id}
                )
                return [dict(row) for row in result.fetchall()]
            except SQLAlchemyError as e:
                logger.error("Failed to get user tracked shows", user_id=user_id, error=str(e))
                return []

    async def remove_tracked_show(self, track_id: int):
        """Remove tracked show"""
        async with get_async_session() as session:
            try:
                await session.execute(
                    text("UPDATE TrackShows SET is_active = false WHERE id = :track_id"),
                    {'track_id': track_id}
                )
                await session.commit()
            except SQLAlchemyError as e:
                logger.error("Failed to remove tracked show", track_id=track_id, error=str(e))
                await session.rollback()

    async def get_all_tracked_shows(self) -> List[Dict[str, Any]]:
        """Get all active tracked shows for release checking"""
        async with get_async_session() as session:
            try:
                result = await session.execute(
                    text("""
                        SELECT * FROM TrackShows
                        WHERE is_active = true
                        ORDER BY last_checked ASC
                    """)
                )
                return [dict(row) for row in result.fetchall()]
            except SQLAlchemyError as e:
                logger.error("Failed to get all tracked shows", error=str(e))
                return []

    # Background Tasks
    @tasks.loop(hours=1)
    async def check_releases(self):
        """Check for new releases of tracked shows"""
        try:
            logger.info("Starting release check")

            tracked_shows = await self.get_all_tracked_shows()

            for show in tracked_shows:
                try:
                    # Check for new episodes based on API source
                    if show['api_source'] == 'tv':
                        new_episodes = await self.check_tmdb_tv_releases(show['show_id'])
                    elif show['api_source'] == 'anime':
                        new_episodes = await self.check_anilist_anime_releases(show['show_id'])
                    else:
                        continue

                    if new_episodes:
                        await self.send_release_notifications(show, new_episodes)

                    # Update last checked timestamp
                    await self.update_last_checked(show['id'])

                except Exception as e:
                    logger.error("Failed to check releases for show", show_id=show['show_id'], error=str(e))

            logger.info("Release check completed", shows_checked=len(tracked_shows))

        except Exception as e:
            logger.error("Release check task failed", error=str(e))

    @tasks.loop(hours=24)
    async def refresh_tvdb_token(self):
        """Refresh TVDB authentication token"""
        if not self.tvdb_api_key or not self.tvdb_pin:
            return

        try:
            async with self.http_client as client:
                response = await client.post(
                    f"{self.tvdb_base_url}/login",
                    json={
                        'apikey': self.tvdb_api_key,
                        'pin': self.tvdb_pin
                    }
                )
                response.raise_for_status()
                data = response.json()

                self.tvdb_token = data['data']['token']
                # Token expires in 24 hours
                self.tvdb_token_expires = datetime.utcnow() + timedelta(hours=24)

                logger.info("TVDB token refreshed")

        except Exception as e:
            logger.error("Failed to refresh TVDB token", error=str(e))

    async def schedule_watch_party_reminder(self, event_id: int, start_time: datetime):
        """Schedule reminder for watch party"""
        try:
            reminder_time = start_time - timedelta(minutes=30)

            if reminder_time > datetime.utcnow():
                # Add to scheduler
                self.bot.scheduler.add_job(
                    self.send_watch_party_reminder,
                    'date',
                    run_date=reminder_time,
                    args=[event_id],
                    id=f"watch_party_reminder_{event_id}",
                    replace_existing=True
                )

                logger.info("Watch party reminder scheduled", event_id=event_id, reminder_time=reminder_time)

        except Exception as e:
            logger.error("Failed to schedule watch party reminder", event_id=event_id, error=str(e))

    async def send_watch_party_reminder(self, event_id: int):
        """Send reminder for watch party"""
        try:
            # Get event details
            async with get_async_session() as session:
                result = await session.execute(
                    text("""
                        SELECT w.*, u.username as creator_name
                        FROM WatchPartyEvents w
                        JOIN Users u ON w.creator_id = u.user_id
                        WHERE w.event_id = :event_id
                    """),
                    {'event_id': event_id}
                )
                event_data = result.fetchone()

            if event_data:
                channel = self.bot.get_channel(event_data.channel_id)
                if channel:
                    embed = discord.Embed(
                        title="⏰ Watch Party Reminder!",
                        description=f"**{event_data.title}** starts in 30 minutes!",
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow()
                    )

                    if event_data.description:
                        embed.add_field(name="Description", value=event_data.description, inline=False)

                    embed.add_field(
                        name="Time",
                        value=f"<t:{int(event_data.scheduled_start_time.timestamp())}:F>",
                        inline=True
                    )

                    embed.set_footer(text=f"Created by {event_data.creator_name}")

                    await channel.send("@everyone", embed=embed)

                    logger.info("Watch party reminder sent", event_id=event_id)

        except Exception as e:
            logger.error("Failed to send watch party reminder", event_id=event_id, error=str(e))

    async def check_tmdb_tv_releases(self, show_id: str) -> List[Dict[str, Any]]:
        """Check for new TV episodes on TMDB"""
        # Implementation for TMDB TV release checking
        # This would query TMDB API for recent episodes
        return []

    async def check_anilist_anime_releases(self, show_id: str) -> List[Dict[str, Any]]:
        """Check for new anime episodes on Anilist"""
        # Implementation for Anilist anime release checking
        # This would query Anilist GraphQL API for recent episodes
        return []

    async def send_release_notifications(self, show: Dict[str, Any], new_episodes: List[Dict[str, Any]]):
        """Send release notifications for new episodes"""
        try:
            # Determine notification channel
            channel_id = show.get('notification_channel_id')
            if not channel_id:
                # Send DM to user
                user = self.bot.get_user(show['user_id'])
                if user:
                    channel = await user.create_dm()
                else:
                    return
            else:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    return

            for episode in new_episodes:
                embed = discord.Embed(
                    title="📺 New Episode Available!",
                    description=f"**{show['show_title']}**\nEpisode {episode.get('episode_number', 'N/A')}: {episode.get('name', 'Unknown')}",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )

                if episode.get('overview'):
                    embed.add_field(name="Overview", value=episode['overview'][:500], inline=False)

                if episode.get('air_date'):
                    embed.add_field(name="Air Date", value=episode['air_date'], inline=True)

                await channel.send(embed=embed)

            logger.info("Release notifications sent", show_title=show['show_title'], episodes=len(new_episodes))

        except Exception as e:
            logger.error("Failed to send release notifications", show_id=show['show_id'], error=str(e))

    async def update_last_checked(self, track_id: int):
        """Update last checked timestamp for tracked show"""
        async with get_async_session() as session:
            try:
                await session.execute(
                    text("UPDATE TrackShows SET last_checked = :now WHERE id = :track_id"),
                    {'track_id': track_id, 'now': datetime.utcnow()}
                )
                await session.commit()
            except SQLAlchemyError as e:
                logger.error("Failed to update last checked", track_id=track_id, error=str(e))

    async def user_has_permission(self, user: discord.User, permission: str) -> bool:
        """Check if user has permission for media operations"""
        # Owner always has all permissions
        if user.id == settings.OWNER_ID:
            return True

        # Check guild roles
        guild = self.bot.get_guild(settings.DISCORD_GUILD_ID)
        if guild:
            member = guild.get_member(user.id)
            if member:
                allowed_roles = {
                    'watchparties.create': ['admin', 'moderator', 'vip'],
                    'media.search': ['everyone']  # Allow everyone to search
                }.get(permission, [])

                user_roles = [role.name.lower() for role in member.roles]
                return any(role in allowed_roles for role in user_roles)

        return permission == 'media.search'  # Allow search by default

    async def cog_load(self):
        """Called when cog is loaded"""
        logger.info("Media Cog loaded")

    async def cog_unload(self):
        """Called when cog is unloaded"""
        await self.http_client.aclose()
        self.check_releases.cancel()
        self.refresh_tvdb_token.cancel()
        logger.info("Media Cog unloaded")


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(MediaCog(bot))
    logger.info("Media Cog registered with bot")