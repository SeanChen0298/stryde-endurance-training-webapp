"""
AES-256-GCM encryption for user-provided Gemini API keys.

The GEMINI_ENCRYPTION_KEY is a 32-byte hex string stored in .env.
User API keys are encrypted before storage and decrypted on use.
The ciphertext is never equal to the plaintext.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import settings


def _get_aes_key() -> bytes:
    """Decode the hex encryption key from settings."""
    return bytes.fromhex(settings.GEMINI_ENCRYPTION_KEY)


def encrypt_api_key(plaintext: str) -> str:
    """
    Encrypt a Gemini API key using AES-256-GCM.
    Returns a base64-encoded string of: nonce (12 bytes) + ciphertext + tag.
    """
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)                         # 96-bit nonce, random per encryption
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    payload = nonce + ciphertext
    return base64.b64encode(payload).decode()


def decrypt_api_key(encrypted: str) -> str:
    """
    Decrypt a previously encrypted Gemini API key.
    Raises ValueError if decryption fails (wrong key or corrupted data).
    """
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    payload = base64.b64decode(encrypted.encode())
    nonce = payload[:12]
    ciphertext = payload[12:]
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()
    except Exception as exc:
        raise ValueError("Failed to decrypt API key — wrong key or corrupted data") from exc
