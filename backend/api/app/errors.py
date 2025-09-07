"""
Centralized API error helpers
"""

from flask import jsonify, request
from typing import Any, Dict, Optional


def api_error_response(status_code: int, message: str, errors: Optional[Dict[str, Any]] = None):
    """
    Build a standardized JSON API error response.
    """
    payload = {
        "status": "error",
        "message": message,
        "path": request.path if request else None,
    }
    if errors:
        payload["errors"] = errors
    response = jsonify(payload)
    response.status_code = status_code
    # Ensure sensitive responses are never cached
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response