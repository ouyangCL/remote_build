"""Security utilities for authentication and encryption."""
import bcrypt
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches
    """
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    """Hash a password.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token.

    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and verify a JWT access token.

    Args:
        token: JWT token

    Returns:
        Decoded token data or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


def get_fernet() -> Any:
    """Get a Fernet instance for encryption/decryption.

    Returns:
        Fernet instance
    """
    from cryptography.fernet import Fernet
    import base64

    # Ensure the key is 32 bytes, url-safe base64 encoded
    key = settings.encryption_key
    if len(key) < 32:
        key = key.ljust(32, "0")[:32]

    # Convert to bytes and encode as base64
    key_bytes = key.encode("utf-8")[:32]
    key_b64 = base64.urlsafe_b64encode(key_bytes)

    return Fernet(key_b64)


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data.

    Args:
        data: Plain text data

    Returns:
        Encrypted data (base64 encoded)
    """
    fernet = get_fernet()
    return fernet.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data.

    Args:
        encrypted_data: Encrypted data (base64 encoded)

    Returns:
        Decrypted plain text
    """
    fernet = get_fernet()
    return fernet.decrypt(encrypted_data.encode()).decode()
