"""
Tests for AES-256-GCM encryption of user Gemini API keys.

Spec requirement:
- Round-trip: decrypt(encrypt(key)) == key
- Ciphertext is never equal to the plaintext
- Two encryptions of the same plaintext produce different ciphertexts (random nonce)
"""

import os
import pytest


@pytest.fixture(autouse=True)
def set_test_encryption_key(monkeypatch):
    """Provide a deterministic 32-byte test key."""
    import importlib
    monkeypatch.setenv("GEMINI_ENCRYPTION_KEY", "a" * 64)  # 32 bytes hex
    # Also patch all required settings env vars to avoid validation error
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("JWT_SECRET", "testsecret")
    monkeypatch.setenv("STRAVA_CLIENT_ID", "test_id")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "test_secret")


def test_round_trip():
    """Decrypting an encrypted key returns the original plaintext."""
    from utils.encryption import encrypt_api_key, decrypt_api_key

    original = "AIzaSyTest_Key_123456789abcdefghijk"
    encrypted = encrypt_api_key(original)
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == original


def test_ciphertext_not_equal_to_plaintext():
    """Encrypted output must never equal the plaintext."""
    from utils.encryption import encrypt_api_key

    key = "AIzaSyTest_Key_123456789abcdefghijk"
    encrypted = encrypt_api_key(key)
    assert encrypted != key


def test_different_ciphertexts_for_same_plaintext():
    """Each encryption must produce a different ciphertext (random nonce)."""
    from utils.encryption import encrypt_api_key

    key = "AIzaSyTest_Key_123456789abcdefghijk"
    enc1 = encrypt_api_key(key)
    enc2 = encrypt_api_key(key)
    assert enc1 != enc2


def test_decrypt_wrong_key_raises():
    """Decryption with wrong key must raise ValueError."""
    import importlib
    from utils.encryption import encrypt_api_key

    original = "AIzaSyTest_Key_123456789abcdefghijk"
    encrypted = encrypt_api_key(original)

    # Patch settings to use a different key
    from unittest.mock import patch
    with patch("utils.encryption.settings") as mock_settings:
        mock_settings.GEMINI_ENCRYPTION_KEY = "b" * 64
        from utils.encryption import decrypt_api_key
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_api_key(encrypted)
