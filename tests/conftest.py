"""
Pytest configuration and fixtures for the Discord Bot API
"""
import pytest
import os
import tempfile
from flask import Flask
from flask.testing import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.app import create_app, db
from backend.api.config import TestingConfig


@pytest.fixture(scope='session')
def app():
    """Create and configure a test app instance."""
    # Create a temporary database for testing
    db_fd, db_path = tempfile.mkstemp()

    # Configure test app
    test_config = TestingConfig()
    test_config.SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
    test_config.TESTING = True

    app = create_app('testing')
    app.config.from_object(test_config)

    # Create database tables
    with app.app_context():
        db.create_all()

    yield app

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='session')
def client(app: Flask):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture(scope='function')
def session(app: Flask):
    """Create a new database session for a test."""
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()

        # Create a session bound to the transaction
        session = db.session

        yield session

        # Rollback the transaction
        transaction.rollback()
        connection.close()
        session.remove()


@pytest.fixture
def auth_headers():
    """Return authorization headers for authenticated requests."""
    return {
        'Authorization': 'Bearer test_token',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def test_user(session):
    """Create a test user."""
    from backend.api.app.models import User

    user = User(
        user_id=123456789,
        username='testuser',
        global_name='Test User',
        avatar_hash='test_hash',
        is_bot_admin=False
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def test_embed_template(session, test_user):
    """Create a test embed template."""
    from backend.api.app.models import EmbedTemplate

    template = EmbedTemplate(
        template_name='test_template',
        embed_json={
            'title': 'Test Embed',
            'description': 'This is a test embed',
            'color': 3447003
        },
        created_by=test_user.user_id
    )
    session.add(template)
    session.commit()
    return template


@pytest.fixture
def test_giveaway(session, test_user):
    """Create a test giveaway."""
    from backend.api.app.models import Giveaway
    from datetime import datetime, timedelta

    giveaway = Giveaway(
        prize='Test Prize',
        winner_count=1,
        channel_id='123456789',
        start_at=datetime.utcnow(),
        end_at=datetime.utcnow() + timedelta(hours=24),
        created_by=test_user.user_id,
        status='scheduled'
    )
    session.add(giveaway)
    session.commit()
    return giveaway


# Test data factories
def create_test_user(session, **kwargs):
    """Factory function to create test users."""
    from backend.api.app.models import User

    defaults = {
        'user_id': 987654321,
        'username': 'factory_user',
        'global_name': 'Factory User',
        'avatar_hash': 'factory_hash',
        'is_bot_admin': False
    }
    defaults.update(kwargs)

    user = User(**defaults)
    session.add(user)
    session.commit()
    return user


def create_test_embed_template(session, user_id, **kwargs):
    """Factory function to create test embed templates."""
    from backend.api.app.models import EmbedTemplate

    defaults = {
        'template_name': 'factory_template',
        'embed_json': {
            'title': 'Factory Embed',
            'description': 'Created by factory',
            'color': 16776960
        },
        'created_by': user_id
    }
    defaults.update(kwargs)

    template = EmbedTemplate(**defaults)
    session.add(template)
    session.commit()
    return template


# Custom pytest markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


# Test utilities
class TestUtils:
    """Utility functions for tests."""

    @staticmethod
    def create_auth_token(user_id: int = 123456789) -> str:
        """Create a mock JWT token for testing."""
        import jwt
        from backend.api.config import TestingConfig

        config = TestingConfig()
        payload = {
            'sub': str(user_id),
            'exp': 9999999999,  # Far future
            'iat': 1000000000,
            'type': 'access'
        }

        token = jwt.encode(
            payload,
            config.JWT_SECRET_KEY,
            algorithm=config.JWT_ALGORITHM
        )
        return token

    @staticmethod
    def get_auth_headers(user_id: int = 123456789) -> dict:
        """Get authorization headers with a test token."""
        token = TestUtils.create_auth_token(user_id)
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    @staticmethod
    def assert_response_success(response, status_code: int = 200):
        """Assert that a response is successful."""
        assert response.status_code == status_code
        data = response.get_json()
        assert 'error' not in data or data.get('error') is None

    @staticmethod
    def assert_response_error(response, status_code: int, error_message: str = None):
        """Assert that a response contains an error."""
        assert response.status_code == status_code
        data = response.get_json()
        assert 'error' in data
        if error_message:
            assert error_message in data['error']

    @staticmethod
    def assert_validation_error(response, field: str = None):
        """Assert that a response contains validation errors."""
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        if field:
            assert field in data['error'].lower()


# Make TestUtils available as a fixture
@pytest.fixture
def test_utils():
    """Provide test utilities."""
    return TestUtils()