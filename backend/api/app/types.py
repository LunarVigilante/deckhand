from sqlalchemy.types import TypeDecorator, Text
import json
from .crypto import encrypt, decrypt


class EncryptedText(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for AES-256-GCM encrypted text using app-managed key.
    Stores JSON blob with kid, alg, nonce, ct, ts.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            plaintext = value.encode()
        else:
            plaintext = bytes(value)
        blob = encrypt(plaintext)
        return json.dumps(blob, separators=(",", ":"))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            blob = json.loads(value)
            plain = decrypt(blob)
            return plain.decode()
        except Exception:
            # If decryption fails (e.g., key changed), return None to avoid leaking data
            return None