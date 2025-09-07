"""
AES-256-GCM encryption helpers with key IDs and rotation support.
"""
import os
import base64
from typing import Tuple, Dict
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _load_key() -> Tuple[str, bytes]:
    key_id = os.environ.get("ENCRYPTION_KEY_ID", "local-default-v1")
    key_b64 = os.environ.get("PII_ENCRYPTION_KEY")
    if not key_b64:
        raise RuntimeError("PII_ENCRYPTION_KEY not configured")
    key = base64.b64decode(key_b64)
    if len(key) != 32:
        raise RuntimeError("PII_ENCRYPTION_KEY must be 32 bytes (AES-256) base64-encoded")
    return key_id, key


def encrypt(plaintext: bytes, aad: bytes = b"") -> Dict[str, str]:
    key_id, key = _load_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, aad)
    return {
        "kid": key_id,
        "alg": "AES-256-GCM",
        "nonce": base64.b64encode(nonce).decode(),
        "ct": base64.b64encode(ct).decode(),
        "ts": datetime.utcnow().isoformat()
    }


def decrypt(blob: Dict[str, str], aad: bytes = b"") -> bytes:
    # For multi-key rotation, select by blob['kid']; here we use env key
    _key_id, key = _load_key()
    aesgcm = AESGCM(key)
    nonce = base64.b64decode(blob["nonce"])
    ct = base64.b64decode(blob["ct"])
    return aesgcm.decrypt(nonce, ct, aad)