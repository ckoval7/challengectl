#!/usr/bin/env python3
"""
Cryptographic utilities for ChallengeCtl.
Handles encryption and decryption of sensitive data like TOTP secrets.
"""

import os
import logging
from cryptography.fernet import Fernet
from typing import Optional

logger = logging.getLogger(__name__)


class CryptoManager:
    """Manages encryption and decryption of sensitive data."""

    def __init__(self, key_file: str = 'server/.encryption_key'):
        """
        Initialize the crypto manager with an encryption key.

        Args:
            key_file: Path to the file containing the encryption key.
                     If the file doesn't exist, a new key will be generated.
        """
        self.key_file = key_file
        self.key = self._load_or_generate_key()
        self.cipher = Fernet(self.key)

    def _load_or_generate_key(self) -> bytes:
        """
        Load encryption key from file or generate a new one.

        Returns:
            The encryption key as bytes.
        """
        # Ensure the server directory exists
        os.makedirs(os.path.dirname(self.key_file) if os.path.dirname(self.key_file) else '.', exist_ok=True)

        if os.path.exists(self.key_file):
            # Load existing key
            try:
                with open(self.key_file, 'rb') as f:
                    key = f.read()
                logger.info(f"Loaded encryption key from {self.key_file}")
                return key
            except Exception as e:
                logger.error(f"Failed to load encryption key from {self.key_file}: {e}")
                raise
        else:
            # Generate new key
            key = Fernet.generate_key()
            try:
                # Write key to file with restricted permissions
                with open(self.key_file, 'wb') as f:
                    f.write(key)
                # Set file permissions to 600 (owner read/write only)
                os.chmod(self.key_file, 0o600)
                logger.info(f"Generated new encryption key and saved to {self.key_file}")
                return key
            except Exception as e:
                logger.error(f"Failed to save encryption key to {self.key_file}: {e}")
                raise

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt.

        Returns:
            The encrypted string as a base64-encoded string.
        """
        if not plaintext:
            return plaintext

        try:
            encrypted_bytes = self.cipher.encrypt(plaintext.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Decrypt a ciphertext string.

        Args:
            ciphertext: The encrypted string (base64-encoded).

        Returns:
            The decrypted plaintext string, or None if decryption fails.
        """
        if not ciphertext:
            return ciphertext

        try:
            decrypted_bytes = self.cipher.decrypt(ciphertext.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            # Return None to indicate decryption failure
            # This allows for graceful handling of legacy unencrypted data
            return None


# Global crypto manager instance
_crypto_manager: Optional[CryptoManager] = None


def get_crypto_manager(key_file: str = 'server/.encryption_key') -> CryptoManager:
    """
    Get the global crypto manager instance.

    Args:
        key_file: Path to the encryption key file.

    Returns:
        The global CryptoManager instance.
    """
    global _crypto_manager
    if _crypto_manager is None:
        _crypto_manager = CryptoManager(key_file)
    return _crypto_manager


def encrypt_totp_secret(secret: str) -> str:
    """
    Encrypt a TOTP secret.

    Args:
        secret: The TOTP secret to encrypt.

    Returns:
        The encrypted secret.
    """
    return get_crypto_manager().encrypt(secret)


def decrypt_totp_secret(encrypted_secret: str) -> Optional[str]:
    """
    Decrypt a TOTP secret.

    Args:
        encrypted_secret: The encrypted TOTP secret.

    Returns:
        The decrypted secret, or None if decryption fails.
    """
    return get_crypto_manager().decrypt(encrypted_secret)
