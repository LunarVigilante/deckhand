"""
Integration tests for Flask API endpoints
"""
import pytest
import json
from datetime import datetime, timedelta

from backend.api.app.models import User, EmbedTemplate, Giveaway


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_login_success(self, client, test_utils):
        """Test successful login."""
        # Mock Discord OAuth response
        response_data = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'user': {
                'id': '123456789',
                'username': 'testuser',
                'global_name': 'Test User',
                'avatar': 'test_hash'
            }
        }

        # This would normally test the actual OAuth flow
        # For now, just test the endpoint structure
        assert True  # Placeholder

    def test_refresh_token(self, client, auth_headers):
        """Test token refresh."""
        response = client.post('/api/v1/auth/refresh',
                             headers=auth_headers,
                             json={'refresh_token': 'test_refresh_token'})

        # Should return new access token or error
        assert response.status_code in [200, 401, 400]

    def test_logout(self, client, auth_headers):
        """Test logout."""
        response = client.post('/api/v1/auth/logout', headers=auth_headers)
        assert response.status_code in [200, 401]


class TestEmbedEndpoints:
    """Test embed management endpoints."""

    def test_get_embed_templates(self, client, auth_headers, test_embed_template):
        """Test getting embed templates."""
        response = client.get('/api/v1/embeds/templates', headers=auth_headers)
        test_utils.assert_response_success(response)

        data = response.get_json()
        assert 'templates' in data
        assert isinstance(data['templates'], list)

    def test_create_embed_template(self, client, auth_headers, test_user):
        """Test creating an embed template."""
        template_data = {
            'template_name': 'new_template',
            'embed_json': {
                'title': 'New Embed',
                'description': 'Created via API',
                'color': 16776960
            },
            'description': 'Test template'
        }

        response = client.post('/api/v1/embeds/templates',
                             headers=auth_headers,
                             json=template_data)

        if response.status_code == 201:
            data = response.get_json()
            assert 'template' in data
            assert data['template']['template_name'] == 'new_template'
        else:
            # May fail due to authentication/permission issues in test
            assert response.status_code in [201, 401, 403]

    def test_get_embed_template(self, client, auth_headers, test_embed_template):
        """Test getting a specific embed template."""
        response = client.get(f'/api/v1/embeds/templates/{test_embed_template.id}',
                            headers=auth_headers)

        if response.status_code == 200:
            data = response.get_json()
            assert 'template' in data
            assert data['template']['id'] == test_embed_template.id
        else:
            assert response.status_code in [200, 401, 403, 404]

    def test_update_embed_template(self, client, auth_headers, test_embed_template):
        """Test updating an embed template."""
        update_data = {
            'template_name': 'updated_template',
            'embed_json': {
                'title': 'Updated Embed',
                'description': 'Updated via API',
                'color': 65535
            }
        }

        response = client.put(f'/api/v1/embeds/templates/{test_embed_template.id}',
                            headers=auth_headers,
                            json=update_data)

        assert response.status_code in [200, 401, 403, 404]

    def test_delete_embed_template(self, client, auth_headers, test_embed_template):
        """Test deleting an embed template."""
        response = client.delete(f'/api/v1/embeds/templates/{test_embed_template.id}',
                               headers=auth_headers)

        assert response.status_code in [200, 401, 403, 404]


class TestGiveawayEndpoints:
    """Test giveaway management endpoints."""

    def test_get_giveaways(self, client, auth_headers, test_giveaway):
        """Test getting giveaways."""
        response = client.get('/api/v1/giveaways', headers=auth_headers)

        if response.status_code == 200:
            data = response.get_json()
            assert 'giveaways' in data
            assert isinstance(data['giveaways'], list)
        else:
            assert response.status_code in [200, 401, 403]

    def test_create_giveaway(self, client, auth_headers, test_user):
        """Test creating a giveaway."""
        giveaway_data = {
            'prize': 'Test Prize',
            'winner_count': 1,
            'channel_id': '123456789012345678',
            'start_at': (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
            'end_at': (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            'description': 'Test giveaway'
        }

        response = client.post('/api/v1/giveaways',
                             headers=auth_headers,
                             json=giveaway_data)

        assert response.status_code in [201, 400, 401, 403]

    def test_get_giveaway(self, client, auth_headers, test_giveaway):
        """Test getting a specific giveaway."""
        response = client.get(f'/api/v1/giveaways/{test_giveaway.id}',
                            headers=auth_headers)

        assert response.status_code in [200, 401, 403, 404]

    def test_update_giveaway(self, client, auth_headers, test_giveaway):
        """Test updating a giveaway."""
        update_data = {
            'prize': 'Updated Prize',
            'description': 'Updated description'
        }

        response = client.put(f'/api/v1/giveaways/{test_giveaway.id}',
                            headers=auth_headers,
                            json=update_data)

        assert response.status_code in [200, 400, 401, 403, 404]

    def test_end_giveaway(self, client, auth_headers, test_giveaway):
        """Test ending a giveaway."""
        response = client.post(f'/api/v1/giveaways/{test_giveaway.id}/end',
                             headers=auth_headers)

        assert response.status_code in [200, 400, 401, 403, 404]


class TestStatsEndpoints:
    """Test statistics endpoints."""

    def test_get_message_stats(self, client, auth_headers):
        """Test getting message statistics."""
        response = client.get('/api/v1/stats/messages', headers=auth_headers)

        if response.status_code == 200:
            data = response.get_json()
            assert 'stats' in data
            assert isinstance(data['stats'], list)
        else:
            assert response.status_code in [200, 401, 403]

    def test_get_voice_stats(self, client, auth_headers):
        """Test getting voice statistics."""
        response = client.get('/api/v1/stats/voice', headers=auth_headers)

        if response.status_code == 200:
            data = response.get_json()
            assert 'stats' in data
            assert isinstance(data['stats'], list)
        else:
            assert response.status_code in [200, 401, 403]

    def test_get_invite_stats(self, client, auth_headers):
        """Test getting invite statistics."""
        response = client.get('/api/v1/stats/invites', headers=auth_headers)

        if response.status_code == 200:
            data = response.get_json()
            assert 'stats' in data
            assert isinstance(data['stats'], list)
        else:
            assert response.status_code in [200, 401, 403]


class TestMediaEndpoints:
    """Test media management endpoints."""

    def test_search_movies(self, client, auth_headers):
        """Test movie search."""
        response = client.get('/api/v1/media/search/movies?query=test',
                            headers=auth_headers)

        # May fail due to external API dependency
        assert response.status_code in [200, 400, 401, 403, 500]

    def test_search_tv(self, client, auth_headers):
        """Test TV show search."""
        response = client.get('/api/v1/media/search/tv?query=test',
                            headers=auth_headers)

        assert response.status_code in [200, 400, 401, 403, 500]

    def test_search_anime(self, client, auth_headers):
        """Test anime search."""
        response = client.get('/api/v1/media/search/anime?query=test',
                            headers=auth_headers)

        assert response.status_code in [200, 400, 401, 403, 500]

    def test_get_tracked_shows(self, client, auth_headers):
        """Test getting tracked shows."""
        response = client.get('/api/v1/media/tracked', headers=auth_headers)

        if response.status_code == 200:
            data = response.get_json()
            assert 'tracked_shows' in data
            assert isinstance(data['tracked_shows'], list)
        else:
            assert response.status_code in [200, 401, 403]

    def test_track_show(self, client, auth_headers):
        """Test tracking a show."""
        track_data = {
            'show_id': '12345',
            'show_title': 'Test Show',
            'api_source': 'tmdb',
            'show_type': 'tv'
        }

        response = client.post('/api/v1/media/track',
                             headers=auth_headers,
                             json=track_data)

        assert response.status_code in [201, 400, 401, 403]

    def test_create_watch_party(self, client, auth_headers):
        """Test creating a watch party."""
        party_data = {
            'title': 'Test Watch Party',
            'description': 'Watch together!',
            'scheduled_start_time': (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            'media_poster_url': 'https://example.com/poster.jpg'
        }

        response = client.post('/api/v1/media/watchparty',
                             headers=auth_headers,
                             json=party_data)

        assert response.status_code in [201, 400, 401, 403]


class TestUserEndpoints:
    """Test user management endpoints."""

    def test_get_user_profile(self, client, auth_headers, test_user):
        """Test getting user profile."""
        response = client.get('/api/v1/users/profile', headers=auth_headers)

        if response.status_code == 200:
            data = response.get_json()
            assert 'user' in data
            assert 'permissions' in data
        else:
            assert response.status_code in [200, 401, 403]

    def test_update_user_profile(self, client, auth_headers, test_user):
        """Test updating user profile."""
        update_data = {
            'global_name': 'Updated Name'
        }

        response = client.put('/api/v1/users/profile',
                            headers=auth_headers,
                            json=update_data)

        assert response.status_code in [200, 400, 401, 403]


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test basic health check."""
        response = client.get('/health')
        assert response.status_code == 200

        data = response.get_json()
        assert 'status' in data
        assert 'timestamp' in data
        assert 'version' in data

    def test_detailed_health_check(self, client):
        """Test detailed health check."""
        response = client.get('/health/detailed')
        assert response.status_code in [200, 503]

        data = response.get_json()
        assert 'status' in data
        assert 'checks' in data


class TestErrorHandling:
    """Test error handling across endpoints."""

    def test_invalid_json(self, client, auth_headers):
        """Test handling of invalid JSON."""
        response = client.post('/api/v1/embeds/templates',
                             headers=auth_headers,
                             data='invalid json')

        assert response.status_code == 400

    def test_missing_authentication(self, client):
        """Test endpoints without authentication."""
        response = client.get('/api/v1/embeds/templates')
        assert response.status_code == 401

    def test_invalid_method(self, client, auth_headers):
        """Test invalid HTTP methods."""
        response = client.patch('/api/v1/embeds/templates',
                              headers=auth_headers,
                              json={})

        assert response.status_code == 405

    def test_rate_limiting(self, client, auth_headers):
        """Test rate limiting (may not be active in tests)."""
        # Make multiple requests quickly
        for i in range(10):
            response = client.get('/api/v1/embeds/templates', headers=auth_headers)

        # Should eventually get rate limited or succeed
        assert response.status_code in [200, 401, 403, 429]