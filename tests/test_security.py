"""
Unit tests for security utilities and input validation
"""
import pytest
from werkzeug.exceptions import BadRequest

from backend.api.app.security import (
    sanitize_input,
    validate_json_input,
    validate_embed_data,
    EMBED_TEMPLATE_SCHEMA,
    GIVEAWAY_SCHEMA,
    MEDIA_TRACK_SCHEMA
)


class TestInputSanitization:
    """Test input sanitization functions."""

    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        input_text = "Hello <script>alert('xss')</script> World"
        result = sanitize_input(input_text)
        assert "<script>" not in result
        assert "alert" not in result
        assert "Hello World" in result

    def test_sanitize_input_sql_injection(self):
        """Test SQL injection detection."""
        with pytest.raises(BadRequest):
            sanitize_input("SELECT * FROM users; --")

        with pytest.raises(BadRequest):
            sanitize_input("'; DROP TABLE users; --")

    def test_sanitize_input_xss_patterns(self):
        """Test XSS pattern detection."""
        with pytest.raises(BadRequest):
            sanitize_input("<script>alert('xss')</script>")

        with pytest.raises(BadRequest):
            sanitize_input("javascript:alert('xss')")

    def test_sanitize_input_allow_html(self):
        """Test HTML sanitization when allowed."""
        input_text = "<p>Hello <strong>world</strong></p><script>alert('xss')</script>"
        result = sanitize_input(input_text, allow_html=True)
        assert "<p>" in result
        assert "<strong>" in result
        assert "<script>" not in result

    def test_sanitize_input_length_limit(self):
        """Test input length limiting."""
        long_input = "a" * 10000
        result = sanitize_input(long_input)
        assert len(result) <= 10000


class TestJSONValidation:
    """Test JSON input validation."""

    def test_validate_json_input_required_fields(self):
        """Test validation of required fields."""
        schema = {
            'name': {'type': str, 'required': True},
            'age': {'type': int, 'required': False}
        }

        # Missing required field
        with pytest.raises(BadRequest):
            validate_json_input({'age': 25}, schema)

        # Valid input
        result = validate_json_input({'name': 'John', 'age': 25}, schema)
        assert result['name'] == 'John'
        assert result['age'] == 25

    def test_validate_json_input_type_validation(self):
        """Test type validation."""
        schema = {
            'count': {'type': int, 'required': True},
            'price': {'type': float, 'required': True}
        }

        # Invalid type
        with pytest.raises(BadRequest):
            validate_json_input({'count': 'not_a_number', 'price': 10.5}, schema)

        # Valid input
        result = validate_json_input({'count': '42', 'price': '10.5'}, schema)
        assert result['count'] == 42
        assert result['price'] == 10.5

    def test_validate_json_input_length_validation(self):
        """Test length validation."""
        schema = {
            'name': {'type': str, 'min_length': 2, 'max_length': 10, 'required': True}
        }

        # Too short
        with pytest.raises(BadRequest):
            validate_json_input({'name': 'A'}, schema)

        # Too long
        with pytest.raises(BadRequest):
            validate_json_input({'name': 'This is way too long'}, schema)

        # Valid length
        result = validate_json_input({'name': 'John'}, schema)
        assert result['name'] == 'John'

    def test_validate_json_input_pattern_validation(self):
        """Test pattern validation."""
        schema = {
            'email': {'type': str, 'pattern': r'^[^@]+@[^@]+\.[^@]+$', 'required': True}
        }

        # Invalid pattern
        with pytest.raises(BadRequest):
            validate_json_input({'email': 'not-an-email'}, schema)

        # Valid pattern
        result = validate_json_input({'email': 'test@example.com'}, schema)
        assert result['email'] == 'test@example.com'

    def test_validate_json_input_range_validation(self):
        """Test numeric range validation."""
        schema = {
            'rating': {'type': int, 'min_value': 1, 'max_value': 5, 'required': True}
        }

        # Below minimum
        with pytest.raises(BadRequest):
            validate_json_input({'rating': 0}, schema)

        # Above maximum
        with pytest.raises(BadRequest):
            validate_json_input({'rating': 6}, schema)

        # Valid range
        result = validate_json_input({'rating': 3}, schema)
        assert result['rating'] == 3


class TestEmbedValidation:
    """Test Discord embed validation."""

    def test_validate_embed_data_basic(self):
        """Test basic embed validation."""
        embed_data = {
            'title': 'Test Embed',
            'description': 'This is a test embed',
            'color': 3447003
        }

        result = validate_embed_data(embed_data)
        assert result['title'] == 'Test Embed'
        assert result['description'] == 'This is a test embed'
        assert result['color'] == 3447003

    def test_validate_embed_data_title_too_long(self):
        """Test embed title length validation."""
        long_title = 'A' * 300
        embed_data = {'title': long_title}

        with pytest.raises(BadRequest):
            validate_embed_data(embed_data)

    def test_validate_embed_data_description_too_long(self):
        """Test embed description length validation."""
        long_desc = 'A' * 5000
        embed_data = {'description': long_desc}

        with pytest.raises(BadRequest):
            validate_embed_data(embed_data)

    def test_validate_embed_data_fields_validation(self):
        """Test embed fields validation."""
        embed_data = {
            'fields': [
                {'name': 'Field 1', 'value': 'Value 1', 'inline': True},
                {'name': 'Field 2', 'value': 'Value 2', 'inline': False}
            ]
        }

        result = validate_embed_data(embed_data)
        assert len(result['fields']) == 2
        assert result['fields'][0]['name'] == 'Field 1'

    def test_validate_embed_data_too_many_fields(self):
        """Test embed fields count limit."""
        fields = [{'name': f'Field {i}', 'value': f'Value {i}'} for i in range(30)]
        embed_data = {'fields': fields}

        with pytest.raises(BadRequest):
            validate_embed_data(embed_data)

    def test_validate_embed_data_invalid_color(self):
        """Test embed color validation."""
        embed_data = {'color': 99999999}  # Invalid color value

        with pytest.raises(BadRequest):
            validate_embed_data(embed_data)

    def test_validate_embed_data_url_validation(self):
        """Test embed URL validation."""
        embed_data = {'url': 'not-a-valid-url'}

        with pytest.raises(BadRequest):
            validate_embed_data(embed_data)

        # Valid URL
        embed_data = {'url': 'https://example.com'}
        result = validate_embed_data(embed_data)
        assert result['url'] == 'https://example.com'


class TestSchemaValidation:
    """Test predefined schema validation."""

    def test_embed_template_schema(self):
        """Test embed template schema validation."""
        valid_data = {
            'template_name': 'my_template',
            'embed_json': {
                'title': 'Test',
                'description': 'Description'
            }
        }

        result = validate_json_input(valid_data, EMBED_TEMPLATE_SCHEMA)
        assert result['template_name'] == 'my_template'

    def test_embed_template_schema_invalid_name(self):
        """Test embed template name validation."""
        invalid_data = {
            'template_name': 'invalid@name!',
            'embed_json': {'title': 'Test'}
        }

        with pytest.raises(BadRequest):
            validate_json_input(invalid_data, EMBED_TEMPLATE_SCHEMA)

    def test_giveaway_schema(self):
        """Test giveaway schema validation."""
        valid_data = {
            'prize': 'Discord Nitro',
            'winner_count': 1,
            'channel_id': '123456789012345678',
            'start_at': '2024-01-01T00:00:00Z',
            'end_at': '2024-01-02T00:00:00Z'
        }

        result = validate_json_input(valid_data, GIVEAWAY_SCHEMA)
        assert result['prize'] == 'Discord Nitro'
        assert result['winner_count'] == 1

    def test_giveaway_schema_invalid_channel(self):
        """Test giveaway channel ID validation."""
        invalid_data = {
            'prize': 'Prize',
            'winner_count': 1,
            'channel_id': 'not-a-number',
            'start_at': '2024-01-01T00:00:00Z',
            'end_at': '2024-01-02T00:00:00Z'
        }

        with pytest.raises(BadRequest):
            validate_json_input(invalid_data, GIVEAWAY_SCHEMA)

    def test_media_track_schema(self):
        """Test media tracking schema validation."""
        valid_data = {
            'show_id': '12345',
            'show_title': 'Attack on Titan',
            'api_source': 'tmdb',
            'show_type': 'anime'
        }

        result = validate_json_input(valid_data, MEDIA_TRACK_SCHEMA)
        assert result['show_id'] == '12345'
        assert result['api_source'] == 'tmdb'

    def test_media_track_schema_invalid_source(self):
        """Test media tracking source validation."""
        invalid_data = {
            'show_id': '12345',
            'show_title': 'Test Show',
            'api_source': 'invalid_source',
            'show_type': 'tv'
        }

        with pytest.raises(BadRequest):
            validate_json_input(invalid_data, MEDIA_TRACK_SCHEMA)