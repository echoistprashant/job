import base64
import hashlib
import html
import logging
import re
import time
from collections import defaultdict
from typing import Dict, List, Optional
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, status
from backend.app.config import settings

logger = logging.getLogger(__name__)


def _get_encryption_key() -> bytes:
    """
    Derive a 32-byte urlsafe base64 Fernet key from the secret key or application configuration.
    Guarantees deterministic encryption without hardcoding sensitive production secrets.
    """
    secret = getattr(settings, "APP_SECRET_KEY", None) or getattr(settings, "SECRET_KEY", None) or "ai-job-agent-default-dev-secret-key-32b"
    key_hash = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(key_hash)


_FERNET_KEY = _get_encryption_key()
_cipher = Fernet(_FERNET_KEY)
ENCRYPTION_PREFIX = "enc:"


def encrypt_text(plaintext: Optional[str]) -> Optional[str]:
    """
    Phase 46: Encrypt sensitive strings (contact info, tokens) at rest.
    Prepends 'enc:' prefix so decryptor can distinguish encrypted from legacy plaintext.
    """
    if not plaintext:
        return plaintext
    try:
        encrypted_bytes = _cipher.encrypt(plaintext.encode("utf-8"))
        return f"{ENCRYPTION_PREFIX}{encrypted_bytes.decode('utf-8')}"
    except Exception as e:
        logger.error(f"[Security] Encryption failed: {e}")
        return plaintext


def decrypt_text(ciphertext: Optional[str]) -> Optional[str]:
    """
    Phase 46: Decrypt cipher text. Transparently returns plaintext if unencrypted
    for seamless backward compatibility.
    """
    if not ciphertext or not isinstance(ciphertext, str):
        return ciphertext
    if not ciphertext.startswith(ENCRYPTION_PREFIX):
        return ciphertext
    raw_token = ciphertext[len(ENCRYPTION_PREFIX):]
    try:
        decrypted_bytes = _cipher.decrypt(raw_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        logger.warning("[Security] Invalid encryption token or changed encryption key.")
        return ciphertext
    except Exception as e:
        logger.error(f"[Security] Decryption error: {e}")
        return ciphertext


def sanitize_input(text: Optional[str]) -> Optional[str]:
    """
    Phase 46: Sanitize text inputs against XSS and injection vectors while
    preserving technical resume keywords.
    """
    if not text:
        return text
    # Remove executable script tags and event handlers
    cleaned = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"on\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"javascript:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


class InMemoryRateLimiter:
    """
    Phase 46: Sliding window in-memory rate limiter per IP address.
    """

    def __init__(self, requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self._access_records: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(self, client_ip: str):
        now = time.time()
        window_start = now - 60.0
        # Filter timestamps outside window
        timestamps = [t for t in self._access_records[client_ip] if t > window_start]
        if len(timestamps) >= self.requests_per_minute:
            logger.warning(f"[Security] Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again in a minute."
            )
        timestamps.append(now)
        self._access_records[client_ip] = timestamps


rate_limiter = InMemoryRateLimiter(requests_per_minute=120)
