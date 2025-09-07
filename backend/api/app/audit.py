"""
Immutable audit event emission using existing AuditLogs table.
"""
from typing import Optional, Dict, Any
from flask import request, current_app, g
from .models import db, AuditLog


def emit_audit(action: str, user_id: Optional[int], resource_type: Optional[str] = None,
               resource_id: Optional[int] = None, old_values: Optional[Dict[str, Any]] = None,
               new_values: Optional[Dict[str, Any]] = None, success: bool = True):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent')
    rid = getattr(g, 'request_id', None)
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip,
        user_agent=user_agent,
        success=success
    )
    db.session.add(entry)
    db.session.commit()
    # Structured log with minimal data (no PII)
    current_app.logger.info("audit_event", action=action, uid=user_id, rid=rid, success=success)
    return entry