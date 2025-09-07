"""
Extended middleware: request ID injection and log redaction
"""
from typing import List
from flask import Flask, request, g
import uuid


def init_request_id(app: Flask, header_name: str = 'X-Request-ID'):
    @app.before_request
    def _inject_request_id():
        rid = request.headers.get(header_name) or str(uuid.uuid4())
        g.request_id = rid

    @app.after_request
    def _propagate_request_id(resp):
        if hasattr(g, 'request_id'):
            resp.headers[header_name] = g.request_id
        return resp


def _redact(headers: dict, fields: List[str]) -> dict:
    redacted = {}
    for k, v in headers.items():
        if k.lower() in fields:
            redacted[k] = 'REDACTED'
        else:
            redacted[k] = v
    return redacted


def init_redaction_filters(app: Flask, fields: List[str]):
    fields = [f.lower() for f in fields]

    @app.before_request
    def _redact_incoming():
        redacted = _redact(dict(request.headers), fields)
        # Use structured log fields; request_id added by init_request_id
        app.logger.debug("request_received", path=request.path, headers=redacted)

    @app.after_request
    def _redact_outgoing(resp):
        redacted = _redact(dict(resp.headers), fields)
        app.logger.debug("response_headers", path=request.path, headers=redacted, status=resp.status_code)
        return resp