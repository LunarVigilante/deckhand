"""
Privacy and DSAR endpoints (request, export, erase) and consent management.
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from .models import db, User
from .errors import api_error_response
from .audit import emit_audit
from .crypto import encrypt
import json
import time
import base64

bp = Blueprint('privacy', __name__)


@bp.route('/request', methods=['POST'])
@jwt_required()
def request_dsar():
    uid = int(get_jwt_identity())
    emit_audit('privacy.request', uid, resource_type='user', resource_id=uid, success=True)
    return jsonify({'status': 'accepted', 'request_id': f"dsar-{uid}-{int(time.time())}"}), 202


@bp.route('/export', methods=['GET'])
@jwt_required()
def export_data():
    uid = int(get_jwt_identity())
    user = User.query.get(uid)
    if not user:
        return api_error_response(404, "User not found")
    # Minimal portable JSON export
    export = {
        'user': user.to_dict(),
        'timestamp': int(time.time())
    }
    plaintext = json.dumps(export, separators=(',', ':')).encode()
    try:
        blob = encrypt(plaintext, aad=str(uid).encode())
    except Exception as e:
        current_app.logger.error(f"Export encryption failed: {e}")
        return api_error_response(500, "Failed to prepare export")
    token = base64.b64encode(json.dumps(blob).encode()).decode()
    emit_audit('privacy.export', uid, resource_type='user', resource_id=uid, success=True)
    return jsonify({'export_token': token, 'expires_in': 600}), 200


@bp.route('/erase', methods=['POST'])
@jwt_required()
def erase_data():
    uid = int(get_jwt_identity())
    user = User.query.get(uid)
    if not user:
        return api_error_response(404, "User not found")
    old = user.to_dict()
    # Anonymize minimal attributes; cascading deletes/policy-based purge can be added
    user.username = f"user-{uid}"
    user.global_name = None
    user.avatar_hash = None
    db.session.commit()
    emit_audit('privacy.erase', uid, resource_type='user', resource_id=uid, old_values=old, new_values=user.to_dict(), success=True)
    return jsonify({'status': 'erased'}), 200


@bp.route('/consent', methods=['POST'])
@jwt_required()
def set_consent():
    uid = int(get_jwt_identity())
    body = request.get_json(silent=True) or {}
    purpose = body.get('purpose')
    legal_basis = body.get('legal_basis', 'consent')
    granted = bool(body.get('granted', True))
    if not purpose:
        return api_error_response(400, "purpose required")
    emit_audit('privacy.consent', uid, resource_type='consent', resource_id=uid,
               new_values={'purpose': purpose, 'legal_basis': legal_basis, 'granted': granted}, success=True)
    return jsonify({'status': 'recorded'}), 200


@bp.route('/consent', methods=['DELETE'])
@jwt_required()
def withdraw_consent():
    uid = int(get_jwt_identity())
    purpose = request.args.get('purpose')
    if not purpose:
        return api_error_response(400, "purpose required")
    emit_audit('privacy.consent_withdraw', uid, resource_type='consent', resource_id=uid,
               new_values={'purpose': purpose}, success=True)
    return jsonify({'status': 'withdrawn'}), 200