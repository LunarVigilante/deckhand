"""
Embed Management API Endpoints
Handles CRUD operations for embed templates and posted messages
"""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, ValidationError, validator
from marshmallow import Schema, fields, validate, ValidationError as MarshmallowValidationError

from . import db
from .models import EmbedTemplate, PostedMessage, User, AuditLog
from .middleware import rbac_required
from .utils import APIResponse, PaginationHelper

# Create blueprint
embeds_bp = Blueprint('embeds', __name__)

# Pydantic models for request validation
class EmbedFieldSchema(BaseModel):
    name: str
    value: str
    inline: bool = False

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Field name cannot be empty')
        return v

    @validator('value')
    def value_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Field value cannot be empty')
        return v

class EmbedAuthorSchema(BaseModel):
    name: str
    url: Optional[str] = None
    icon_url: Optional[str] = None

class EmbedFooterSchema(BaseModel):
    text: str
    icon_url: Optional[str] = None

class EmbedImageSchema(BaseModel):
    url: str

class EmbedDataSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    color: Optional[int] = None
    timestamp: Optional[str] = None
    author: Optional[EmbedAuthorSchema] = None
    thumbnail: Optional[EmbedImageSchema] = None
    image: Optional[EmbedImageSchema] = None
    footer: Optional[EmbedFooterSchema] = None
    fields: List[EmbedFieldSchema] = []

    @validator('color')
    def color_must_be_valid(cls, v):
        if v is not None and (v < 0 or v > 0xFFFFFF):
            raise ValueError('Color must be between 0 and 16777215')
        return v

    @validator('fields')
    def fields_must_not_exceed_limit(cls, v):
        if len(v) > current_app.config['MAX_EMBED_FIELDS']:
            raise ValueError(f'Cannot have more than {current_app.config["MAX_EMBED_FIELDS"]} fields')
        return v

class EmbedTemplateCreateSchema(BaseModel):
    template_name: str
    embed_json: EmbedDataSchema
    description: Optional[str] = None

    @validator('template_name')
    def template_name_must_be_valid(cls, v):
        if not v.strip():
            raise ValueError('Template name cannot be empty')
        if len(v) > 100:
            raise ValueError('Template name cannot exceed 100 characters')
        return v.strip()

class EmbedTemplateUpdateSchema(BaseModel):
    template_name: Optional[str] = None
    embed_json: Optional[EmbedDataSchema] = None
    description: Optional[str] = None

# Marshmallow schemas for response serialization
class EmbedTemplateResponseSchema(Schema):
    id = fields.Int()
    template_name = fields.Str()
    embed_json = fields.Raw()
    created_by = fields.Int()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    is_active = fields.Bool()
    version = fields.Int()
    description = fields.Str()

class PostedMessageResponseSchema(Schema):
    id = fields.Int()
    message_id = fields.Int()
    channel_id = fields.Int()
    template_id = fields.Int()
    posted_by = fields.Int()
    posted_at = fields.DateTime()
    last_edited_at = fields.DateTime()
    edit_count = fields.Int()
    is_deleted = fields.Bool()

# Initialize schemas
embed_template_schema = EmbedTemplateResponseSchema()
posted_message_schema = PostedMessageResponseSchema()

@embeds_bp.route('/templates', methods=['GET'])
@jwt_required()
@rbac_required(['embeds.read'])
def get_embed_templates():
    """
    Get user's embed templates with pagination

    Query Parameters:
        page: Page number (default: 1)
        per_page: Items per page (default: 20, max: 100)
        search: Search in template names and descriptions
    """
    try:
        user_id = get_jwt_identity()
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        search = request.args.get('search', '').strip()

        # Build query
        query = EmbedTemplate.query.filter_by(created_by=user_id, is_active=True)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    EmbedTemplate.template_name.ilike(search_term),
                    EmbedTemplate.description.ilike(search_term)
                )
            )

        # Paginate
        pagination = query.order_by(EmbedTemplate.updated_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Serialize results
        templates = embed_template_schema.dump(pagination.items, many=True)

        response = APIResponse.success({
            'templates': templates,
            'pagination': PaginationHelper.get_pagination_info(pagination)
        })

        return jsonify(response), 200

    except Exception as e:
        current_app.logger.error(f"Failed to get embed templates: {str(e)}")
        return jsonify(APIResponse.error("Failed to retrieve embed templates")), 500

@embeds_bp.route('/templates', methods=['POST'])
@jwt_required()
@rbac_required(['embeds.create'])
def create_embed_template():
    """
    Create a new embed template

    Request Body:
        template_name: str (required)
        embed_json: dict (required) - Discord embed JSON
        description: str (optional)
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        if not data:
            return jsonify(APIResponse.error("Request body is required")), 400

        # Validate input
        try:
            validated_data = EmbedTemplateCreateSchema(**data)
        except ValidationError as e:
            return jsonify(APIResponse.error("Validation failed", details=e.errors())), 400

        # Check for duplicate template name
        existing = EmbedTemplate.query.filter_by(
            template_name=validated_data.template_name,
            created_by=user_id,
            is_active=True
        ).first()

        if existing:
            return jsonify(APIResponse.error("Template name already exists")), 409

        # Validate embed JSON
        if not validate_embed_json(validated_data.embed_json.dict()):
            return jsonify(APIResponse.error("Invalid embed JSON data")), 400

        # Create template
        template = EmbedTemplate(
            template_name=validated_data.template_name,
            embed_json=validated_data.embed_json.dict(),
            created_by=user_id,
            description=validated_data.description,
            version=1
        )

        db.session.add(template)
        db.session.commit()

        # Log audit event
        AuditLog.log_action(
            user_id=user_id,
            action='embed_template.created',
            resource_type='embed_template',
            resource_id=template.id,
            new_values={'template_name': template.template_name}
        )

        result = embed_template_schema.dump(template)
        response = APIResponse.success(result, "Embed template created successfully")

        current_app.logger.info(f"Embed template created: {template.template_name} by user {user_id}")
        return jsonify(response), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error creating embed template: {str(e)}")
        return jsonify(APIResponse.error("Database error occurred")), 500
    except Exception as e:
        current_app.logger.error(f"Failed to create embed template: {str(e)}")
        return jsonify(APIResponse.error("Failed to create embed template")), 500

@embeds_bp.route('/templates/<int:template_id>', methods=['GET'])
@jwt_required()
@rbac_required(['embeds.read'])
def get_embed_template(template_id):
    """
    Get a specific embed template by ID

    Path Parameters:
        template_id: Template ID
    """
    try:
        user_id = get_jwt_identity()

        template = EmbedTemplate.query.filter_by(
            id=template_id,
            created_by=user_id,
            is_active=True
        ).first()

        if not template:
            return jsonify(APIResponse.error("Embed template not found")), 404

        result = embed_template_schema.dump(template)
        return jsonify(APIResponse.success(result)), 200

    except Exception as e:
        current_app.logger.error(f"Failed to get embed template {template_id}: {str(e)}")
        return jsonify(APIResponse.error("Failed to retrieve embed template")), 500

@embeds_bp.route('/templates/<int:template_id>', methods=['PUT'])
@jwt_required()
@rbac_required(['embeds.update'])
def update_embed_template(template_id):
    """
    Update an embed template

    Path Parameters:
        template_id: Template ID

    Request Body:
        template_name: str (optional)
        embed_json: dict (optional)
        description: str (optional)
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        if not data:
            return jsonify(APIResponse.error("Request body is required")), 400

        # Get existing template
        template = EmbedTemplate.query.filter_by(
            id=template_id,
            created_by=user_id,
            is_active=True
        ).first()

        if not template:
            return jsonify(APIResponse.error("Embed template not found")), 404

        # Validate input
        try:
            validated_data = EmbedTemplateUpdateSchema(**data)
        except ValidationError as e:
            return jsonify(APIResponse.error("Validation failed", details=e.errors())), 400

        # Store old values for audit
        old_values = {
            'template_name': template.template_name,
            'embed_json': template.embed_json,
            'description': template.description
        }

        # Update fields
        if validated_data.template_name is not None:
            # Check for duplicate name if changing
            if validated_data.template_name != template.template_name:
                existing = EmbedTemplate.query.filter_by(
                    template_name=validated_data.template_name,
                    created_by=user_id,
                    is_active=True
                ).first()
                if existing:
                    return jsonify(APIResponse.error("Template name already exists")), 409
            template.template_name = validated_data.template_name

        if validated_data.embed_json is not None:
            # Validate embed JSON
            if not validate_embed_json(validated_data.embed_json.dict()):
                return jsonify(APIResponse.error("Invalid embed JSON data")), 400
            template.embed_json = validated_data.embed_json.dict()

        if validated_data.description is not None:
            template.description = validated_data.description

        template.version += 1
        db.session.commit()

        # Log audit event
        AuditLog.log_action(
            user_id=user_id,
            action='embed_template.updated',
            resource_type='embed_template',
            resource_id=template.id,
            old_values=old_values,
            new_values={
                'template_name': template.template_name,
                'embed_json': template.embed_json,
                'description': template.description
            }
        )

        result = embed_template_schema.dump(template)
        response = APIResponse.success(result, "Embed template updated successfully")

        current_app.logger.info(f"Embed template updated: {template.template_name} by user {user_id}")
        return jsonify(response), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error updating embed template {template_id}: {str(e)}")
        return jsonify(APIResponse.error("Database error occurred")), 500
    except Exception as e:
        current_app.logger.error(f"Failed to update embed template {template_id}: {str(e)}")
        return jsonify(APIResponse.error("Failed to update embed template")), 500

@embeds_bp.route('/templates/<int:template_id>', methods=['DELETE'])
@jwt_required()
@rbac_required(['embeds.delete'])
def delete_embed_template(template_id):
    """
    Soft delete an embed template

    Path Parameters:
        template_id: Template ID
    """
    try:
        user_id = get_jwt_identity()

        template = EmbedTemplate.query.filter_by(
            id=template_id,
            created_by=user_id,
            is_active=True
        ).first()

        if not template:
            return jsonify(APIResponse.error("Embed template not found")), 404

        # Store old values for audit
        old_values = {
            'template_name': template.template_name,
            'is_active': template.is_active
        }

        # Soft delete
        template.is_active = False
        db.session.commit()

        # Log audit event
        AuditLog.log_action(
            user_id=user_id,
            action='embed_template.deleted',
            resource_type='embed_template',
            resource_id=template.id,
            old_values=old_values,
            new_values={'is_active': False}
        )

        current_app.logger.info(f"Embed template deleted: {template.template_name} by user {user_id}")
        return jsonify(APIResponse.success(message="Embed template deleted successfully")), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error deleting embed template {template_id}: {str(e)}")
        return jsonify(APIResponse.error("Database error occurred")), 500
    except Exception as e:
        current_app.logger.error(f"Failed to delete embed template {template_id}: {str(e)}")
        return jsonify(APIResponse.error("Failed to delete embed template")), 500

@embeds_bp.route('/templates/<template_name>/validate', methods=['POST'])
@jwt_required()
@rbac_required(['embeds.read'])
def validate_embed_template(template_name):
    """
    Validate an embed template without saving

    Path Parameters:
        template_name: Template name to validate

    Request Body:
        embed_json: dict - Discord embed JSON to validate
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        if not data or 'embed_json' not in data:
            return jsonify(APIResponse.error("embed_json is required")), 400

        # Check if template name is available
        existing = EmbedTemplate.query.filter_by(
            template_name=template_name,
            created_by=user_id,
            is_active=True
        ).first()

        name_available = existing is None

        # Validate embed JSON
        is_valid = validate_embed_json(data['embed_json'])

        result = {
            'template_name': template_name,
            'name_available': name_available,
            'embed_valid': is_valid,
            'errors': []
        }

        if not name_available:
            result['errors'].append('Template name already exists')

        if not is_valid:
            result['errors'].append('Invalid embed JSON structure')

        return jsonify(APIResponse.success(result)), 200

    except Exception as e:
        current_app.logger.error(f"Failed to validate embed template: {str(e)}")
        return jsonify(APIResponse.error("Failed to validate embed template")), 500

@embeds_bp.route('/posted-messages', methods=['GET'])
@jwt_required()
@rbac_required(['embeds.read'])
def get_posted_messages():
    """
    Get user's posted embed messages

    Query Parameters:
        page: Page number (default: 1)
        per_page: Items per page (default: 20, max: 100)
        channel_id: Filter by channel ID
    """
    try:
        user_id = get_jwt_identity()
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        channel_id = request.args.get('channel_id')

        # Build query
        query = PostedMessage.query.filter_by(posted_by=user_id, is_deleted=False)

        if channel_id:
            query = query.filter_by(channel_id=int(channel_id))

        # Paginate
        pagination = query.order_by(PostedMessage.posted_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Serialize results
        messages = posted_message_schema.dump(pagination.items, many=True)

        response = APIResponse.success({
            'messages': messages,
            'pagination': PaginationHelper.get_pagination_info(pagination)
        })

        return jsonify(response), 200

    except ValueError as e:
        return jsonify(APIResponse.error("Invalid channel ID")), 400
    except Exception as e:
        current_app.logger.error(f"Failed to get posted messages: {str(e)}")
        return jsonify(APIResponse.error("Failed to retrieve posted messages")), 500

@embeds_bp.route('/preview', methods=['POST'])
@jwt_required()
@rbac_required(['embeds.read'])
def preview_embed():
    """
    Generate a preview of embed JSON

    Request Body:
        embed_json: dict - Discord embed JSON to preview
    """
    try:
        data = request.get_json()

        if not data or 'embed_json' not in data:
            return jsonify(APIResponse.error("embed_json is required")), 400

        embed_json = data['embed_json']

        # Validate embed JSON
        if not validate_embed_json(embed_json):
            return jsonify(APIResponse.error("Invalid embed JSON data")), 400

        # Generate preview data
        preview = {
            'embed_json': embed_json,
            'character_count': calculate_embed_character_count(embed_json),
            'field_count': len(embed_json.get('fields', [])),
            'is_valid': True
        }

        return jsonify(APIResponse.success(preview)), 200

    except Exception as e:
        current_app.logger.error(f"Failed to generate embed preview: {str(e)}")
        return jsonify(APIResponse.error("Failed to generate embed preview")), 500

def validate_embed_json(embed_json: Dict[str, Any]) -> bool:
    """
    Validate embed JSON against Discord limits

    Args:
        embed_json: Embed JSON data

    Returns:
        True if valid, False otherwise
    """
    try:
        # Check total character count
        total_chars = calculate_embed_character_count(embed_json)

        if total_chars > current_app.config['MAX_EMBED_CHARS']:
            current_app.logger.warning(f"Embed exceeds character limit: {total_chars}/{current_app.config['MAX_EMBED_CHARS']}")
            return False

        # Check field count
        fields = embed_json.get('fields', [])
        if len(fields) > current_app.config['MAX_EMBED_FIELDS']:
            current_app.logger.warning(f"Embed exceeds field limit: {len(fields)}/{current_app.config['MAX_EMBED_FIELDS']}")
            return False

        # Validate URL formats
        url_fields = ['url']
        if 'author' in embed_json and isinstance(embed_json['author'], dict):
            url_fields.extend(['author.url', 'author.icon_url'])
        if 'thumbnail' in embed_json and isinstance(embed_json['thumbnail'], dict):
            url_fields.append('thumbnail.url')
        if 'image' in embed_json and isinstance(embed_json['image'], dict):
            url_fields.append('image.url')
        if 'footer' in embed_json and isinstance(embed_json['footer'], dict):
            url_fields.append('footer.icon_url')

        for field_path in url_fields:
            url = get_nested_value(embed_json, field_path)
            if url and not (str(url).startswith('http://') or str(url).startswith('https://')):
                current_app.logger.warning(f"Invalid URL format for {field_path}: {url}")
                return False

        return True

    except Exception as e:
        current_app.logger.error(f"Embed validation failed: {str(e)}")
        return False

def calculate_embed_character_count(embed_json: Dict[str, Any]) -> int:
    """
    Calculate total character count of embed

    Args:
        embed_json: Embed JSON data

    Returns:
        Total character count
    """
    total_chars = 0

    # Title
    if 'title' in embed_json:
        total_chars += len(str(embed_json['title']))

    # Description
    if 'description' in embed_json:
        total_chars += len(str(embed_json['description']))

    # Author name
    if 'author' in embed_json and isinstance(embed_json['author'], dict):
        total_chars += len(str(embed_json['author'].get('name', '')))

    # Footer text
    if 'footer' in embed_json and isinstance(embed_json['footer'], dict):
        total_chars += len(str(embed_json['footer'].get('text', '')))

    # Fields
    if 'fields' in embed_json and isinstance(embed_json['fields'], list):
        for field in embed_json['fields']:
            if isinstance(field, dict):
                total_chars += len(str(field.get('name', '')))
                total_chars += len(str(field.get('value', '')))

    return total_chars

def get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """
    Get nested value from dictionary using dot notation

    Args:
        data: Dictionary to search
        path: Dot-separated path (e.g., 'author.icon_url')

    Returns:
        Value at path or None
    """
    keys = path.split('.')
    current = data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None

    return current