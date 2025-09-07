"""
Embed Management Cog
Handles embed template creation, posting, and editing via Discord commands
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import discord
from discord.ext import commands
from discord import app_commands
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from bot.database import get_async_session
from bot.utils import DiscordUtils
from bot.config import settings

logger = logging.getLogger(__name__)

class EmbedCog(commands.Cog):
    """Embed management system for Discord bot"""

    def __init__(self, bot):
        self.bot = bot
        self.max_embed_fields = settings.MAX_EMBED_FIELDS
        self.max_embed_chars = settings.MAX_EMBED_CHARS

    @app_commands.command(name="post_embed", description="Post an embed from a saved template")
    @app_commands.describe(
        template_name="Name of the embed template to post",
        channel="Channel to post in (optional, defaults to current)"
    )
    async def post_embed_command(self, interaction: discord.Interaction,
                               template_name: str,
                               channel: Optional[discord.TextChannel] = None):
        """
        Slash command to post an embed from a saved template

        Args:
            interaction: Discord interaction
            template_name: Name of the template to post
            channel: Target channel (optional)
        """
        # Permission check
        if not await self.user_has_permission(interaction.user, 'embeds.post'):
            await interaction.response.send_message("❌ You don't have permission to post embeds.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            # Get embed template
            template = await self.get_embed_template(template_name, interaction.user.id)
            if not template:
                await interaction.followup.send(f"❌ Embed template '{template_name}' not found.", ephemeral=True)
                return

            # Validate embed data
            embed_data = template['embed_json']
            if not self.validate_embed_data(embed_data):
                await interaction.followup.send("❌ Invalid embed template data.", ephemeral=True)
                return

            # Create Discord embed
            embed = self.create_discord_embed(embed_data)

            # Post embed
            target_channel = channel or interaction.channel
            message = await DiscordUtils.safe_send_message(target_channel, embed=embed)

            if message:
                # Store posted message info
                await self.store_posted_message(
                    message_id=message.id,
                    channel_id=target_channel.id,
                    template_id=template['id'],
                    posted_by=interaction.user.id
                )

                await interaction.followup.send(
                    f"✅ Embed posted successfully in {target_channel.mention}!",
                    ephemeral=True
                )

                logger.info(
                    "Embed posted",
                    template_name=template_name,
                    user_id=interaction.user.id,
                    channel_id=target_channel.id,
                    message_id=message.id
                )
            else:
                await interaction.followup.send("❌ Failed to post embed message.", ephemeral=True)

        except json.JSONDecodeError as e:
            await interaction.followup.send("❌ Invalid JSON in embed template.", ephemeral=True)
            logger.warning("Invalid JSON in embed template", template_name=template_name, error=str(e))
        except Exception as e:
            await interaction.followup.send("❌ Failed to post embed. Please try again.", ephemeral=True)
            logger.error("Embed posting failed", template_name=template_name, user_id=interaction.user.id, error=str(e))

    @app_commands.command(name="edit_embed", description="Edit a previously posted embed")
    @app_commands.describe(
        message_id="Message ID of the embed to edit",
        template_name="Name of the new embed template to use"
    )
    async def edit_embed_command(self, interaction: discord.Interaction,
                               message_id: str, template_name: str):
        """
        Slash command to edit a previously posted embed

        Args:
            interaction: Discord interaction
            message_id: ID of the message to edit
            template_name: Name of the new template to use
        """
        # Permission check
        if not await self.user_has_permission(interaction.user, 'embeds.edit'):
            await interaction.response.send_message("❌ You don't have permission to edit embeds.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            # Get the posted message info
            posted_message = await self.get_posted_message(int(message_id))
            if not posted_message:
                await interaction.followup.send("❌ Posted embed message not found in database.", ephemeral=True)
                return

            # Check if user can edit this embed
            if posted_message['posted_by'] != interaction.user.id:
                if not await self.user_has_permission(interaction.user, 'embeds.edit_others'):
                    await interaction.followup.send("❌ You can only edit embeds you posted.", ephemeral=True)
                    return

            # Get new template
            template = await self.get_embed_template(template_name, interaction.user.id)
            if not template:
                await interaction.followup.send(f"❌ Embed template '{template_name}' not found.", ephemeral=True)
                return

            # Validate embed data
            embed_data = template['embed_json']
            if not self.validate_embed_data(embed_data):
                await interaction.followup.send("❌ Invalid embed template data.", ephemeral=True)
                return

            # Get the message and edit it
            channel = self.bot.get_channel(posted_message['channel_id'])
            if not channel:
                await interaction.followup.send("❌ Channel not found.", ephemeral=True)
                return

            try:
                message = await channel.fetch_message(int(message_id))
                embed = self.create_discord_embed(embed_data)

                await message.edit(embed=embed)

                # Update posted message record
                await self.update_posted_message(
                    message_id=int(message_id),
                    template_id=template['id'],
                    last_edited_at=datetime.utcnow()
                )

                await interaction.followup.send("✅ Embed updated successfully!", ephemeral=True)

                logger.info(
                    "Embed edited",
                    message_id=message_id,
                    template_name=template_name,
                    user_id=interaction.user.id
                )

            except discord.NotFound:
                await interaction.followup.send("❌ Message not found. It may have been deleted.", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("❌ I don't have permission to edit that message.", ephemeral=True)

        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid message ID: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Failed to edit embed. Please try again.", ephemeral=True)
            logger.error("Embed editing failed", message_id=message_id, user_id=interaction.user.id, error=str(e))

    @app_commands.command(name="list_embed_templates", description="List your saved embed templates")
    async def list_embed_templates_command(self, interaction: discord.Interaction):
        """List user's saved embed templates"""
        await interaction.response.defer()

        try:
            templates = await self.get_user_embed_templates(interaction.user.id)

            if not templates:
                await interaction.followup.send(
                    "📝 You don't have any saved embed templates yet. Create one using the web interface!",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📝 Your Embed Templates",
                description=f"You have {len(templates)} saved template(s):",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            template_list = []
            for template in templates[:10]:  # Limit to 10
                created_date = template['created_at'].strftime('%Y-%m-%d')
                template_list.append(f"• **{template['template_name']}** - Created {created_date}")

            embed.description += "\n" + "\n".join(template_list)

            if len(templates) > 10:
                embed.set_footer(text=f"And {len(templates) - 10} more...")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send("❌ Failed to retrieve templates.", ephemeral=True)
            logger.error("List templates failed", user_id=interaction.user.id, error=str(e))

    @app_commands.command(name="delete_embed_template", description="Delete a saved embed template")
    @app_commands.describe(template_name="Name of the template to delete")
    async def delete_embed_template_command(self, interaction: discord.Interaction, template_name: str):
        """
        Delete a saved embed template

        Args:
            interaction: Discord interaction
            template_name: Name of template to delete
        """
        await interaction.response.defer()

        try:
            # Get template to verify ownership
            template = await self.get_embed_template(template_name, interaction.user.id)
            if not template:
                await interaction.followup.send(f"❌ Template '{template_name}' not found.", ephemeral=True)
                return

            # Delete template
            success = await self.delete_embed_template(template['id'])
            if success:
                await interaction.followup.send(f"✅ Template '{template_name}' deleted successfully!", ephemeral=True)
                logger.info("Template deleted", template_name=template_name, user_id=interaction.user.id)
            else:
                await interaction.followup.send("❌ Failed to delete template.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send("❌ Failed to delete template. Please try again.", ephemeral=True)
            logger.error("Delete template failed", template_name=template_name, user_id=interaction.user.id, error=str(e))

    def validate_embed_data(self, embed_data: Dict[str, Any]) -> bool:
        """
        Validate embed JSON data against Discord limits

        Args:
            embed_data: Embed data dictionary

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check total character count
            total_chars = 0
            if 'title' in embed_data:
                total_chars += len(str(embed_data['title']))
            if 'description' in embed_data:
                total_chars += len(str(embed_data['description']))
            if 'fields' in embed_data:
                for field in embed_data['fields']:
                    total_chars += len(str(field.get('name', '')))
                    total_chars += len(str(field.get('value', '')))

            if total_chars > self.max_embed_chars:
                logger.warning(f"Embed exceeds character limit: {total_chars}/{self.max_embed_chars}")
                return False

            # Check field count
            if 'fields' in embed_data and len(embed_data['fields']) > self.max_embed_fields:
                logger.warning(f"Embed exceeds field limit: {len(embed_data['fields'])}/{self.max_embed_fields}")
                return False

            # Validate URL formats
            url_fields = ['url', 'image', 'thumbnail', 'footer', 'author']
            for field in url_fields:
                if field in embed_data and embed_data[field]:
                    if field == 'url':
                        url = embed_data[field]
                    elif field in ['image', 'thumbnail'] and isinstance(embed_data[field], dict):
                        url = embed_data[field].get('url')
                    elif field == 'footer' and isinstance(embed_data[field], dict):
                        url = embed_data[field].get('icon_url')
                    elif field == 'author' and isinstance(embed_data[field], dict):
                        url = embed_data[field].get('icon_url')
                    else:
                        continue

                    if url and not (url.startswith('http://') or url.startswith('https://')):
                        logger.warning(f"Invalid URL format for {field}: {url}")
                        return False

            return True

        except Exception as e:
            logger.error("Embed validation failed", error=str(e))
            return False

    def create_discord_embed(self, embed_data: Dict[str, Any]) -> discord.Embed:
        """
        Create a Discord embed from JSON data

        Args:
            embed_data: Embed data dictionary

        Returns:
            Discord embed object
        """
        embed = discord.Embed()

        # Set basic properties
        if 'title' in embed_data:
            embed.title = str(embed_data['title'])[:256]  # Discord title limit

        if 'description' in embed_data:
            embed.description = str(embed_data['description'])[:4096]  # Discord description limit

        if 'url' in embed_data:
            embed.url = embed_data['url']

        if 'color' in embed_data:
            try:
                if isinstance(embed_data['color'], str):
                    # Handle hex color
                    if embed_data['color'].startswith('#'):
                        embed.color = int(embed_data['color'][1:], 16)
                    else:
                        embed.color = int(embed_data['color'], 16)
                else:
                    embed.color = embed_data['color']
            except (ValueError, TypeError):
                embed.color = discord.Color.blue()  # Default color

        # Set timestamp
        if 'timestamp' in embed_data:
            try:
                if isinstance(embed_data['timestamp'], str):
                    embed.timestamp = datetime.fromisoformat(embed_data['timestamp'].replace('Z', '+00:00'))
                else:
                    embed.timestamp = embed_data['timestamp']
            except (ValueError, TypeError):
                pass

        # Set author
        if 'author' in embed_data and isinstance(embed_data['author'], dict):
            author_data = embed_data['author']
            embed.set_author(
                name=str(author_data.get('name', ''))[:256],
                url=author_data.get('url'),
                icon_url=author_data.get('icon_url')
            )

        # Set thumbnail
        if 'thumbnail' in embed_data and isinstance(embed_data['thumbnail'], dict):
            embed.set_thumbnail(url=embed_data['thumbnail'].get('url'))

        # Set image
        if 'image' in embed_data and isinstance(embed_data['image'], dict):
            embed.set_image(url=embed_data['image'].get('url'))

        # Add fields
        if 'fields' in embed_data and isinstance(embed_data['fields'], list):
            for field_data in embed_data['fields'][:self.max_embed_fields]:
                if isinstance(field_data, dict):
                    name = str(field_data.get('name', ''))[:256]
                    value = str(field_data.get('value', ''))[:1024]
                    inline = bool(field_data.get('inline', False))

                    if name and value:  # Only add non-empty fields
                        embed.add_field(name=name, value=value, inline=inline)

        # Set footer
        if 'footer' in embed_data and isinstance(embed_data['footer'], dict):
            footer_data = embed_data['footer']
            embed.set_footer(
                text=str(footer_data.get('text', ''))[:2048],
                icon_url=footer_data.get('icon_url')
            )

        return embed

    # Database Operations
    async def get_embed_template(self, template_name: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Get embed template by name and user"""
        async with get_async_session() as session:
            try:
                result = await session.execute(
                    text("""
                        SELECT * FROM EmbedTemplates
                        WHERE template_name = :template_name
                        AND (created_by = :user_id OR is_active = true)
                        ORDER BY created_at DESC
                        LIMIT 1
                    """),
                    {'template_name': template_name, 'user_id': user_id}
                )
                row = result.fetchone()
                return dict(row) if row else None
            except SQLAlchemyError as e:
                logger.error("Failed to get embed template", template_name=template_name, user_id=user_id, error=str(e))
                return None

    async def get_user_embed_templates(self, user_id: int) -> list:
        """Get all embed templates for user"""
        async with get_async_session() as session:
            try:
                result = await session.execute(
                    text("""
                        SELECT id, template_name, created_at, updated_at, description
                        FROM EmbedTemplates
                        WHERE created_by = :user_id AND is_active = true
                        ORDER BY updated_at DESC
                    """),
                    {'user_id': user_id}
                )
                return [dict(row) for row in result.fetchall()]
            except SQLAlchemyError as e:
                logger.error("Failed to get user embed templates", user_id=user_id, error=str(e))
                return []

    async def store_posted_message(self, message_id: int, channel_id: int,
                                 template_id: int, posted_by: int):
        """Store information about posted embed message"""
        async with get_async_session() as session:
            try:
                await session.execute(
                    text("""
                        INSERT INTO PostedMessages (message_id, channel_id, template_id, posted_by, posted_at)
                        VALUES (:message_id, :channel_id, :template_id, :posted_by, :posted_at)
                    """),
                    {
                        'message_id': message_id,
                        'channel_id': channel_id,
                        'template_id': template_id,
                        'posted_by': posted_by,
                        'posted_at': datetime.utcnow()
                    }
                )
                await session.commit()
            except SQLAlchemyError as e:
                logger.error("Failed to store posted message", message_id=message_id, error=str(e))
                await session.rollback()

    async def get_posted_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Get posted message information"""
        async with get_async_session() as session:
            try:
                result = await session.execute(
                    text("SELECT * FROM PostedMessages WHERE message_id = :message_id"),
                    {'message_id': message_id}
                )
                row = result.fetchone()
                return dict(row) if row else None
            except SQLAlchemyError as e:
                logger.error("Failed to get posted message", message_id=message_id, error=str(e))
                return None

    async def update_posted_message(self, message_id: int, template_id: int, last_edited_at: datetime):
        """Update posted message information after edit"""
        async with get_async_session() as session:
            try:
                await session.execute(
                    text("""
                        UPDATE PostedMessages
                        SET template_id = :template_id,
                            last_edited_at = :last_edited_at,
                            edit_count = edit_count + 1
                        WHERE message_id = :message_id
                    """),
                    {
                        'message_id': message_id,
                        'template_id': template_id,
                        'last_edited_at': last_edited_at
                    }
                )
                await session.commit()
            except SQLAlchemyError as e:
                logger.error("Failed to update posted message", message_id=message_id, error=str(e))
                await session.rollback()

    async def delete_embed_template(self, template_id: int) -> bool:
        """Soft delete embed template"""
        async with get_async_session() as session:
            try:
                await session.execute(
                    text("UPDATE EmbedTemplates SET is_active = false WHERE id = :template_id"),
                    {'template_id': template_id}
                )
                await session.commit()
                return True
            except SQLAlchemyError as e:
                logger.error("Failed to delete embed template", template_id=template_id, error=str(e))
                await session.rollback()
                return False

    async def user_has_permission(self, user: discord.User, permission: str) -> bool:
        """
        Check if user has permission for embed operations

        Args:
            user: Discord user
            permission: Permission type ('embeds.post', 'embeds.edit', 'embeds.edit_others')

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
                    'embeds.post': ['admin', 'moderator', 'vip'],
                    'embeds.edit': ['admin', 'moderator', 'vip'],
                    'embeds.edit_others': ['admin', 'moderator']
                }.get(permission, [])

                user_roles = [role.name.lower() for role in member.roles]
                return any(role in allowed_roles for role in user_roles)

        return False

    async def cog_load(self):
        """Called when cog is loaded"""
        logger.info("Embed Cog loaded")

    async def cog_unload(self):
        """Called when cog is unloaded"""
        logger.info("Embed Cog unloaded")


async def setup(bot):
    """Setup function for cog loading"""
    await bot.add_cog(EmbedCog(bot))
    logger.info("Embed Cog registered with bot")