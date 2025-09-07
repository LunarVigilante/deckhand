-- ========================================
-- Discord Bot Platform Database Schema
-- PostgreSQL 15+
-- ========================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ========================================
-- USER AND AUTHENTICATION DATA
-- ========================================
CREATE TABLE Users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(32) NOT NULL,
    global_name VARCHAR(32),
    avatar_hash VARCHAR(255),
    is_bot_admin BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient lookups
CREATE INDEX idx_users_last_login ON Users(last_login);
CREATE INDEX idx_users_created_at ON Users(created_at);

-- ========================================
-- APPLICATION CONFIGURATION
-- ========================================
CREATE TABLE AppConfig (
    key VARCHAR(50) PRIMARY KEY,
    value VARCHAR(255) NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================================
-- STATISTICS TRACKING
-- ========================================
CREATE TABLE MessageStats (
    message_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    content_length INTEGER DEFAULT 0,
    has_attachments BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_message_stats_user_id ON MessageStats(user_id);
CREATE INDEX idx_message_stats_channel_id ON MessageStats(channel_id);
CREATE INDEX idx_message_stats_sent_at ON MessageStats(sent_at);

CREATE TABLE VoiceStats (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    channel_id BIGINT NOT NULL,
    session_start TIMESTAMPTZ NOT NULL,
    session_end TIMESTAMPTZ,
    duration_seconds INTEGER GENERATED ALWAYS AS (
        CASE 
            WHEN session_end IS NULL THEN EXTRACT(EPOCH FROM (NOW() - session_start))
            ELSE EXTRACT(EPOCH FROM (session_end - session_start))
        END
    ) STORED,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_voice_stats_user_id ON VoiceStats(user_id);
CREATE INDEX idx_voice_stats_channel_id ON VoiceStats(channel_id);
CREATE INDEX idx_voice_stats_session_start ON VoiceStats(session_start);
CREATE INDEX idx_voice_stats_session_end ON VoiceStats(session_end);

CREATE TABLE InviteStats (
    invite_code VARCHAR(20) PRIMARY KEY,
    creator_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE SET NULL,
    uses INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    max_uses INTEGER,
    is_temporary BOOLEAN DEFAULT FALSE,
    channel_id BIGINT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_invite_stats_creator_id ON InviteStats(creator_id);
CREATE INDEX idx_invite_stats_created_at ON InviteStats(created_at);
CREATE INDEX idx_invite_stats_expires_at ON InviteStats(expires_at);

-- ========================================
-- EMBED MANAGEMENT
-- ========================================
CREATE TABLE EmbedTemplates (
    id SERIAL PRIMARY KEY,
    template_name VARCHAR(100) UNIQUE NOT NULL,
    embed_json JSONB NOT NULL,
    created_by BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    description TEXT
);

-- JSONB indexes for efficient querying of embed properties
CREATE INDEX idx_embed_templates_name ON EmbedTemplates(template_name);
CREATE INDEX idx_embed_templates_created_by ON EmbedTemplates(created_by);
CREATE INDEX idx_embed_templates_created_at ON EmbedTemplates(created_at);
CREATE INDEX idx_embed_templates_embed_json ON EmbedTemplates USING GIN (embed_json);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_embed_templates_updated_at 
    BEFORE UPDATE ON EmbedTemplates 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE PostedMessages (
    id SERIAL PRIMARY KEY,
    message_id BIGINT UNIQUE NOT NULL,
    channel_id BIGINT NOT NULL,
    template_id INTEGER REFERENCES EmbedTemplates(id) ON DELETE SET NULL,
    posted_by BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    posted_at TIMESTAMPTZ NOT NULL,
    last_edited_at TIMESTAMPTZ,
    edit_count INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_posted_messages_channel_id ON PostedMessages(channel_id);
CREATE INDEX idx_posted_messages_template_id ON PostedMessages(template_id);
CREATE INDEX idx_posted_messages_posted_by ON PostedMessages(posted_by);
CREATE INDEX idx_posted_messages_posted_at ON PostedMessages(posted_at);

-- ========================================
-- LLM CHATBOT MEMORY
-- ========================================
CREATE TABLE ConversationHistory (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_tokens INTEGER DEFAULT 0,
    response_tokens INTEGER DEFAULT 0,
    model_used VARCHAR(100),
    conversation_thread VARCHAR(255)
);

CREATE INDEX idx_conversation_history_user_id ON ConversationHistory(user_id);
CREATE INDEX idx_conversation_history_created_at ON ConversationHistory(created_at);
CREATE INDEX idx_conversation_history_role ON ConversationHistory(role);
CREATE INDEX idx_conversation_history_thread ON ConversationHistory(conversation_thread);

-- Cleanup trigger for old conversation history (optional)
CREATE OR REPLACE FUNCTION cleanup_old_conversations()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM ConversationHistory 
    WHERE user_id = NEW.user_id 
    AND role = 'user' 
    AND created_at < NOW() - INTERVAL '30 days';
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ========================================
-- GIVEAWAY SYSTEM
-- ========================================
CREATE TABLE Giveaways (
    id SERIAL PRIMARY KEY,
    message_id BIGINT UNIQUE,
    channel_id BIGINT NOT NULL,
    prize TEXT NOT NULL,
    winner_count INTEGER NOT NULL DEFAULT 1 CHECK (winner_count > 0),
    status VARCHAR(20) NOT NULL CHECK (status IN ('scheduled', 'active', 'ended', 'cancelled')),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL CHECK (end_at > start_at),
    created_by BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    required_role_id BIGINT,
    max_entries_per_user INTEGER DEFAULT 1,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_giveaways_channel_id ON Giveaways(channel_id);
CREATE INDEX idx_giveaways_status ON Giveaways(status);
CREATE INDEX idx_giveaways_start_at ON Giveaways(start_at);
CREATE INDEX idx_giveaways_end_at ON Giveaways(end_at);
CREATE INDEX idx_giveaways_created_by ON Giveaways(created_by);

-- Trigger for updated_at
CREATE TRIGGER update_giveaways_updated_at 
    BEFORE UPDATE ON Giveaways 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE GiveawayEntries (
    id SERIAL PRIMARY KEY,
    giveaway_id INTEGER NOT NULL REFERENCES Giveaways(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    entered_at TIMESTAMPTZ DEFAULT NOW(),
    is_winner BOOLEAN DEFAULT FALSE,
    won_at TIMESTAMPTZ,
    UNIQUE (giveaway_id, user_id)
);

CREATE INDEX idx_giveaway_entries_giveaway_id ON GiveawayEntries(giveaway_id);
CREATE INDEX idx_giveaway_entries_user_id ON GiveawayEntries(user_id);
CREATE INDEX idx_giveaway_entries_is_winner ON GiveawayEntries(is_winner);

CREATE TABLE GiveawayWinners (
    id SERIAL PRIMARY KEY,
    giveaway_id INTEGER NOT NULL REFERENCES Giveaways(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    announced_at TIMESTAMPTZ DEFAULT NOW(),
    prize_received BOOLEAN DEFAULT FALSE,
    UNIQUE (giveaway_id, user_id)
);

CREATE INDEX idx_giveaway_winners_giveaway_id ON GiveawayWinners(giveaway_id);

-- ========================================
-- MEDIA COMMUNITY FEATURES
-- ========================================
CREATE TABLE TrackShows (
    id SERIAL PRIMARY KEY,
    show_id VARCHAR(100) NOT NULL,
    user_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    api_source VARCHAR(20) NOT NULL CHECK (api_source IN ('tmdb', 'anilist', 'tvdb')),
    show_title VARCHAR(255) NOT NULL,
    show_type VARCHAR(20) CHECK (show_type IN ('tv', 'anime')),
    last_checked TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    notification_channel_id BIGINT,
    UNIQUE (show_id, user_id, api_source)
);

CREATE INDEX idx_track_shows_user_id ON TrackShows(user_id);
CREATE INDEX idx_track_shows_api_source ON TrackShows(api_source);
CREATE INDEX idx_track_shows_last_checked ON TrackShows(last_checked);
CREATE INDEX idx_track_shows_active ON TrackShows(is_active) WHERE is_active = true;

CREATE TABLE MediaSearchHistory (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES Users(user_id) ON DELETE SET NULL,
    query TEXT NOT NULL,
    media_type VARCHAR(20) NOT NULL,
    api_source VARCHAR(20) NOT NULL,
    results_count INTEGER DEFAULT 0,
    searched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_media_search_history_user_id ON MediaSearchHistory(user_id);
CREATE INDEX idx_media_search_history_searched_at ON MediaSearchHistory(searched_at);
CREATE INDEX idx_media_search_history_query ON MediaSearchHistory USING GIN (to_tsvector('english', query));

CREATE TABLE WatchPartyEvents (
    id SERIAL PRIMARY KEY,
    event_id BIGINT UNIQUE NOT NULL,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    scheduled_start_time TIMESTAMPTZ NOT NULL,
    privacy_level VARCHAR(20) DEFAULT '2', -- 1=private, 2=server_only, 3=public
    creator_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    media_poster_url VARCHAR(500),
    rsvp_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'active', 'completed', 'cancelled'))
);

CREATE INDEX idx_watchparty_events_guild_id ON WatchPartyEvents(guild_id);
CREATE INDEX idx_watchparty_events_scheduled_start_time ON WatchPartyEvents(scheduled_start_time);
CREATE INDEX idx_watchparty_events_status ON WatchPartyEvents(status);

CREATE TABLE WatchPartyRSVPs (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES WatchPartyEvents(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES Users(user_id) ON DELETE CASCADE,
    rsvp_status VARCHAR(20) DEFAULT 'going' CHECK (rsvp_status IN ('going', 'interested', 'declined')),
    rsvped_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (event_id, user_id)
);

CREATE INDEX idx_watchparty_rsvps_event_id ON WatchPartyRSVPs(event_id);
CREATE INDEX idx_watchparty_rsvps_user_id ON WatchPartyRSVPs(user_id);

-- ========================================
-- AUDIT LOGGING
-- ========================================
CREATE TABLE AuditLogs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES Users(user_id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id BIGINT,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id ON AuditLogs(user_id);
CREATE INDEX idx_audit_logs_action ON AuditLogs(action);
CREATE INDEX idx_audit_logs_created_at ON AuditLogs(created_at);
CREATE INDEX idx_audit_logs_success ON AuditLogs(success);

-- ========================================
-- AGGREGATED STATISTICS (MATERIALIZED VIEWS)
-- ========================================
-- Daily message statistics per user
CREATE MATERIALIZED VIEW DailyUserMessageStats AS
SELECT 
    user_id,
    DATE_TRUNC('day', sent_at) as date,
    COUNT(*) as message_count,
    AVG(content_length) as avg_message_length,
    SUM(CASE WHEN has_attachments THEN 1 ELSE 0 END) as attachments_count
FROM MessageStats 
GROUP BY user_id, DATE_TRUNC('day', sent_at);

CREATE INDEX idx_daily_user_message_stats_user_date ON DailyUserMessageStats(user_id, date);

-- Monthly voice statistics per user
CREATE MATERIALIZED VIEW MonthlyUserVoiceStats AS
SELECT 
    user_id,
    DATE_TRUNC('month', session_start) as month,
    SUM(duration_seconds) as total_voice_time_seconds,
    COUNT(DISTINCT channel_id) as unique_channels,
    AVG(duration_seconds) as avg_session_duration
FROM VoiceStats 
WHERE session_end IS NOT NULL
GROUP BY user_id, DATE_TRUNC('month', session_start);

CREATE INDEX idx_monthly_user_voice_stats_user_month ON MonthlyUserVoiceStats(user_id, month);

-- Refresh materialized views (to be scheduled via cron or APScheduler)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY DailyUserMessageStats;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY MonthlyUserVoiceStats;

-- ========================================
-- INITIAL DATA SETUP
-- ========================================
-- Insert default application configuration
INSERT INTO AppConfig (key, value, description) VALUES 
('version', '1.0.0', 'Application version'),
('max_embed_fields', '25', 'Maximum Discord embed fields allowed'),
('max_embed_chars', '6000', 'Maximum Discord embed character limit'),
('default_notification_channel', 'general', 'Default channel for notifications'),
('stats_retention_days', '365', 'How many days to retain raw statistics data');

-- Create a super admin user placeholder (to be populated by bot)
INSERT INTO Users (user_id, username, is_bot_admin, created_at) 
VALUES (0, 'system', TRUE, NOW()) 
ON CONFLICT (user_id) DO NOTHING;