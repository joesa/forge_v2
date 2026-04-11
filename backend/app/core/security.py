import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_key_bytes = bytes.fromhex(settings.FORGE_ENCRYPTION_KEY)
_aesgcm = AESGCM(_key_bytes)


def encrypt_api_key(plaintext: str) -> tuple[bytes, bytes, bytes]:
    """Encrypt an API key with AES-256-GCM. Returns (ciphertext, iv, tag)."""
    iv = os.urandom(12)
    # AESGCM.encrypt returns ciphertext || tag (tag is last 16 bytes)
    ct_with_tag = _aesgcm.encrypt(iv, plaintext.encode(), None)
    ciphertext = ct_with_tag[:-16]
    tag = ct_with_tag[-16:]
    return ciphertext, iv, tag


def decrypt_api_key(ciphertext: bytes, iv: bytes, tag: bytes) -> str:
    """Decrypt an API key from AES-256-GCM components."""
    ct_with_tag = ciphertext + tag
    plaintext = _aesgcm.decrypt(iv, ct_with_tag, None)
    return plaintext.decode()
