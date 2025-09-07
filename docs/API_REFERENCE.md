# Discord Bot Control Panel API Reference

## Overview

The Discord Bot Control Panel provides a REST API for managing Discord bot features including embeds, giveaways, statistics, media tracking, and user authentication.

## Base URL

```
https://your-domain.com/api/v1
```

## Authentication

All API endpoints require authentication using JWT tokens obtained through Discord OAuth2.

### Headers

```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

## Response Format

### Success Response

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful"
}
```

### Error Response

```json
{
  "success": false,
  "error": "Error message",
  "code": "ERROR_CODE"
}
```

## Endpoints

### Authentication

#### POST /auth/login
Initiate Discord OAuth2 login flow.

**Response:**
```json
{
  "auth_url": "https://discord.com/oauth2/authorize?...",
  "state": "random_state_string"
}
```

#### POST /auth/callback
Handle Discord OAuth2 callback.

**Request Body:**
```json
{
  "code": "authorization_code",
  "state": "state_string"
}
```

**Response:**
```json
{
  "access_token": "jwt_token",
  "refresh_token": "refresh_token",
  "user": {
    "user_id": "123456789",
    "username": "testuser",
    "global_name": "Test User",
    "avatar_hash": "avatar_hash"
  }
}
```

#### POST /auth/refresh
Refresh access token.

**Request Body:**
```json
{
  "refresh_token": "refresh_token"
}
```

### Embed Management

#### GET /embeds/templates
Get all embed templates.

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `per_page` (integer): Items per page (default: 20)
- `search` (string): Search in template names

**Response:**
```json
{
  "templates": [
    {
      "id": 1,
      "template_name": "welcome_message",
      "embed_json": { ... },
      "created_by": 123456789,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z",
      "is_active": true,
      "version": 1
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}
```

#### POST /embeds/templates
Create a new embed template.

**Request Body:**
```json
{
  "template_name": "my_template",
  "embed_json": {
    "title": "Welcome!",
    "description": "Welcome to our server!",
    "color": 3447003
  },
  "description": "Welcome message template"
}
```

#### GET /embeds/templates/{id}
Get a specific embed template.

#### PUT /embeds/templates/{id}
Update an embed template.

#### DELETE /embeds/templates/{id}
Delete an embed template.

#### POST /embeds/templates/{id}/post
Post an embed template to a Discord channel.

**Request Body:**
```json
{
  "channel_id": "123456789012345678"
}
```

### Statistics

#### GET /stats/messages
Get message statistics.

**Query Parameters:**
- `start_date` (string): Start date (YYYY-MM-DD)
- `end_date` (string): End date (YYYY-MM-DD)
- `channel_id` (string): Filter by channel
- `user_id` (string): Filter by user

**Response:**
```json
{
  "stats": [
    {
      "date": "2024-01-01",
      "messages": 150,
      "users": 25,
      "channels": 5
    }
  ],
  "total_messages": 150,
  "total_users": 25,
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-01-07"
  }
}
```

#### GET /stats/voice
Get voice channel statistics.

#### GET /stats/invites
Get invite link statistics.

### Giveaway Management

#### GET /giveaways
Get all giveaways.

**Query Parameters:**
- `status` (string): Filter by status (scheduled, active, ended, cancelled)
- `page` (integer): Page number
- `per_page` (integer): Items per page

#### POST /giveaways
Create a new giveaway.

**Request Body:**
```json
{
  "prize": "Discord Nitro",
  "winner_count": 1,
  "channel_id": "123456789012345678",
  "start_at": "2024-01-01T12:00:00Z",
  "end_at": "2024-01-07T12:00:00Z",
  "description": "Monthly giveaway",
  "required_role_id": "987654321098765432",
  "max_entries_per_user": 1
}
```

#### GET /giveaways/{id}
Get a specific giveaway.

#### PUT /giveaways/{id}
Update a giveaway.

#### DELETE /giveaways/{id}
Delete a giveaway.

#### POST /giveaways/{id}/end
End a giveaway early.

### Media Features

#### GET /media/search/movies
Search for movies.

**Query Parameters:**
- `query` (string): Search query (required)
- `page` (integer): Page number (default: 1)

#### GET /media/search/tv
Search for TV shows.

#### GET /media/search/anime
Search for anime.

#### GET /media/tracked
Get user's tracked shows.

#### POST /media/track
Track a show for notifications.

**Request Body:**
```json
{
  "show_id": "12345",
  "show_title": "Attack on Titan",
  "api_source": "tmdb",
  "show_type": "anime"
}
```

#### DELETE /media/tracked/{id}
Stop tracking a show.

#### POST /media/watchparty
Create a watch party event.

**Request Body:**
```json
{
  "title": "Movie Night: Inception",
  "description": "Let's watch Inception together!",
  "scheduled_start_time": "2024-01-01T20:00:00Z",
  "media_poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg"
}
```

### User Management

#### GET /users/profile
Get current user profile.

**Response:**
```json
{
  "user": {
    "user_id": "123456789",
    "username": "testuser",
    "global_name": "Test User",
    "avatar_hash": "avatar_hash",
    "is_bot_admin": false,
    "last_login": "2024-01-01T00:00:00Z",
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  },
  "permissions": [
    "embeds.create",
    "giveaways.manage",
    "stats.view"
  ]
}
```

#### PUT /users/profile
Update user profile.

**Request Body:**
```json
{
  "global_name": "Updated Name"
}
```

### Health Check

#### GET /health
Basic health check.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0",
  "environment": "production"
}
```

#### GET /health/detailed
Detailed health check with component status.

## Error Codes

- `VALIDATION_ERROR`: Input validation failed
- `AUTHENTICATION_ERROR`: Authentication required or failed
- `AUTHORIZATION_ERROR`: Insufficient permissions
- `NOT_FOUND`: Resource not found
- `RATE_LIMITED`: Too many requests
- `EXTERNAL_API_ERROR`: External API error
- `DATABASE_ERROR`: Database operation failed
- `INTERNAL_ERROR`: Internal server error

## Rate Limits

- General endpoints: 60 requests per minute
- Authentication endpoints: 10 requests per minute
- File upload endpoints: 5 requests per minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1640995200
```

## WebSocket Support

Real-time updates are available via WebSocket for:
- Giveaway status changes
- Live statistics updates
- Bot status notifications

**WebSocket URL:** `wss://your-domain.com/ws`

## SDKs and Libraries

### JavaScript/TypeScript

```javascript
import { DiscordBotAPI } from 'discord-bot-api-sdk';

const api = new DiscordBotAPI({
  baseURL: 'https://your-domain.com/api/v1',
  token: 'your_jwt_token'
});

// Get embed templates
const templates = await api.embeds.getTemplates();

// Create a giveaway
const giveaway = await api.giveaways.create({
  prize: 'Discord Nitro',
  winner_count: 1,
  channel_id: '123456789',
  end_at: '2024-01-07T12:00:00Z'
});
```

### Python

```python
from discord_bot_api import DiscordBotAPI

api = DiscordBotAPI(
    base_url='https://your-domain.com/api/v1',
    token='your_jwt_token'
)

# Get statistics
stats = api.stats.get_messages()

# Create embed template
template = api.embeds.create_template({
    'template_name': 'welcome',
    'embed_json': {
        'title': 'Welcome!',
        'description': 'Welcome to our server!'
    }
})
```

## Changelog

### Version 1.0.0
- Initial release
- Basic CRUD operations for all features
- Discord OAuth2 authentication
- Rate limiting and security features
- Comprehensive error handling

## Support

For API support, please contact the development team or create an issue in the project repository.