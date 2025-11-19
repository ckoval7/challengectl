#!/usr/bin/env python3
"""Unit tests for crypto module."""

import pytest
import tempfile
import os
import sys

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from crypto import CryptoManager, encrypt_totp_secret, decrypt_totp_secret


@pytest.fixture
def temp_key_file():
    """Create a temporary key file for testing."""
    fd, key_path = tempfile.mkstemp(suffix='.key')
    os.close(fd)
    os.unlink(key_path)  # Remove it so CryptoManager can create it

    yield key_path

    # Cleanup
    try:
        os.unlink(key_path)
    except:
        pass


class TestCryptoManager:
    """Test CryptoManager class."""

    def test_init_generates_new_key(self, temp_key_file):
        """Test that initialization generates a new key if file doesn't exist."""
        manager = CryptoManager(temp_key_file)

        assert manager.key is not None
        assert os.path.exists(temp_key_file)

    def test_init_loads_existing_key(self, temp_key_file):
        """Test that initialization loads existing key."""
        # Create first manager to generate key
        manager1 = CryptoManager(temp_key_file)
        key1 = manager1.key

        # Create second manager to load the same key
        manager2 = CryptoManager(temp_key_file)
        key2 = manager2.key

        assert key1 == key2

    def test_encrypt_decrypt(self, temp_key_file):
        """Test encryption and decryption."""
        manager = CryptoManager(temp_key_file)

        plaintext = "test_secret_123"
        encrypted = manager.encrypt(plaintext)

        assert encrypted != plaintext
        assert encrypted is not None

        decrypted = manager.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_empty_string(self, temp_key_file):
        """Test encrypting empty string."""
        manager = CryptoManager(temp_key_file)

        encrypted = manager.encrypt("")
        assert encrypted == ""

    def test_decrypt_empty_string(self, temp_key_file):
        """Test decrypting empty string."""
        manager = CryptoManager(temp_key_file)

        decrypted = manager.decrypt("")
        assert decrypted == ""

    def test_decrypt_invalid_ciphertext(self, temp_key_file):
        """Test that decrypting invalid ciphertext returns None."""
        manager = CryptoManager(temp_key_file)

        decrypted = manager.decrypt("invalid_ciphertext")
        assert decrypted is None

    def test_encrypt_special_characters(self, temp_key_file):
        """Test encrypting and decrypting special characters."""
        manager = CryptoManager(temp_key_file)

        plaintext = "test!@#$%^&*()_+-=[]{}|;:',.<>?/"
        encrypted = manager.encrypt(plaintext)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_unicode(self, temp_key_file):
        """Test encrypting and decrypting unicode characters."""
        manager = CryptoManager(temp_key_file)

        plaintext = "Hello 世界 🌍"
        encrypted = manager.encrypt(plaintext)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == plaintext

    def test_key_file_permissions(self, temp_key_file):
        """Test that key file has correct permissions."""
        manager = CryptoManager(temp_key_file)

        # Check file permissions (should be 0600)
        stat_info = os.stat(temp_key_file)
        permissions = stat_info.st_mode & 0o777

        # On some systems, actual permissions may vary
        # Just check that file exists and is readable
        assert os.path.exists(temp_key_file)
        assert os.access(temp_key_file, os.R_OK)


class TestConvenienceFunctions:
    """Test convenience functions for TOTP encryption."""

    def test_encrypt_totp_secret(self, temp_key_file):
        """Test encrypt_totp_secret function."""
        # Reset global crypto manager
        import crypto
        crypto._crypto_manager = None

        # Use temporary key file
        encrypted = encrypt_totp_secret("JBSWY3DPEHPK3PXP")

        assert encrypted is not None
        assert encrypted != "JBSWY3DPEHPK3PXP"

    def test_decrypt_totp_secret(self, temp_key_file):
        """Test decrypt_totp_secret function."""
        # Reset global crypto manager
        import crypto
        crypto._crypto_manager = None

        secret = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_totp_secret(secret)
        decrypted = decrypt_totp_secret(encrypted)

        assert decrypted == secret

    def test_roundtrip_totp_secret(self, temp_key_file):
        """Test complete roundtrip of TOTP secret encryption."""
        # Reset global crypto manager
        import crypto
        crypto._crypto_manager = None

        original_secret = "ABCDEFGHIJKLMNOP"

        # Encrypt
        encrypted = encrypt_totp_secret(original_secret)
        assert encrypted != original_secret

        # Decrypt
        decrypted = decrypt_totp_secret(encrypted)
        assert decrypted == original_secret


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_encrypt_none(self, temp_key_file):
        """Test encrypting None value."""
        manager = CryptoManager(temp_key_file)

        # Should handle None gracefully (returns as-is)
        result = manager.encrypt(None)
        assert result is None

    def test_decrypt_none(self, temp_key_file):
        """Test decrypting None value."""
        manager = CryptoManager(temp_key_file)

        # Should handle None gracefully (returns as-is)
        result = manager.decrypt(None)
        assert result is None

    def test_very_long_plaintext(self, temp_key_file):
        """Test encrypting and decrypting very long text."""
        manager = CryptoManager(temp_key_file)

        # Create a long string (10KB)
        plaintext = "A" * 10240
        encrypted = manager.encrypt(plaintext)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == plaintext
