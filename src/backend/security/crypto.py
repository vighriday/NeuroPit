"""Symmetric encryption helpers for at rest biometric payloads.

The PRD requires encrypted biometrics at rest and privacy enforcement loops
that wipe sensitive raw biometrics after a configured retention window.
This module provides the small primitives the cognitive pipeline needs to
honour both requirements.

We use Fernet, which is AES 128 in CBC mode with a HMAC integrity tag. The
key comes from the `ENCRYPTION_KEY` environment variable. When the variable
is empty a key is derived on the fly from a deterministic local salt so the
developer experience does not require ceremony, but the boot log clearly
warns the operator that the key is not production grade.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import time
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from src.backend.config import get_settings

logger = logging.getLogger(__name__)


_LOCAL_SALT = b"neuropit-local-dev-salt"
_dev_key_warning_emitted = False


def _derive_local_key() -> bytes:
    digest = hashlib.sha256(_LOCAL_SALT).digest()
    return base64.urlsafe_b64encode(digest)


def _resolve_key(encryption_key: Optional[str]) -> bytes:
    global _dev_key_warning_emitted
    if encryption_key:
        return encryption_key.encode("utf-8") if isinstance(encryption_key, str) else encryption_key
    if not _dev_key_warning_emitted:
        logger.warning("ENCRYPTION_KEY is empty, using deterministic developer key. Do not use this in production.")
        _dev_key_warning_emitted = True
    return _derive_local_key()


def get_cipher(encryption_key: Optional[str] = None) -> Fernet:
    if encryption_key is None:
        encryption_key = get_settings().encryption_key
    return Fernet(_resolve_key(encryption_key))


def encrypt(plaintext: str, encryption_key: Optional[str] = None) -> str:
    cipher = get_cipher(encryption_key)
    return cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str, encryption_key: Optional[str] = None) -> str:
    cipher = get_cipher(encryption_key)
    try:
        return cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Ciphertext could not be decrypted with the active key") from exc


def is_expired(issued_at_seconds: float, retention_hours: Optional[int] = None) -> bool:
    """True when an issued biometric record is past its retention window."""
    if retention_hours is None:
        retention_hours = get_settings().biometric_retention_hours
    return (time.time() - issued_at_seconds) > retention_hours * 3600
