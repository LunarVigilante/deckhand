"""
Centralized API error helpers
"""

from flask import jsonify, request, current_app, g
from typing import Any, Dict, Optional


def api_error_response(status_code: int, message: str, errors: Optional[Dict[str, Any]] = None):
    """
    Build a standardized JSON API error response (privacy-preserving).
    """
    payload = {
        "status": "error",
        "message": message,
        "path": request.path if request else None,
        "request_id": getattr(g, "request_id", None),
    }
    # Do not include detailed errors in production to avoid data leakage
    if errors and (not current_app or current_app.config.get("ENV") != "production"):
        payload["errors"] = errors

    response = jsonify(payload)
    response.status_code = status_code
    # Ensure sensitive responses are never cached
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response