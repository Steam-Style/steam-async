from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Hash import SHA1, HMAC
from Crypto.PublicKey.RSA import import_key
from Crypto.Util.Padding import pad, unpad
from os import urandom
from base64 import b64decode


class UniverseKey:
    """
    Public keys for Universes.
    """

    Public = import_key(b64decode("""
MIGdMA0GCSqGSIb3DQEBAQUAA4GLADCBhwKBgQDf7BrWLBBmLBc1OhSwfFkRf53T
2Ct64+AVzRkeRuh7h3SiGEYxqQMUeYKO6UWiSRKpI2hzic9pobFhRr3Bvr/WARvY
gdTckPv+T1JzZsuVcNfFjrocejN1oWI0Rrtgt4Bo+hOneoo3S57G9F1fOpn5nsQ6
6WOiu4gZKODnFMBCiQIBEQ==
"""))


def generate_session_key(hmac_secret: bytes = b"") -> tuple[bytes, bytes]:
    """
    Generates a session key and its encrypted form using the Universe public key.

    Args:
        hmac_secret: Optional HMAC secret to append to the session key before encryption.

    Returns:
        A tuple containing the session key and its encrypted form.
    """
    session_key = urandom(32)
    encrypted_session_key = PKCS1_OAEP.new(
        UniverseKey.Public, SHA1).encrypt(session_key + hmac_secret)

    return (session_key, encrypted_session_key)


def symmetric_encrypt(message: bytes, key: bytes) -> bytes:
    """
    Encrypts a message using AES-CBC with an ECB-encrypted IV.

    Args:
        message: The message to encrypt.
        key: The AES key.

    Returns:
        The encrypted message as bytes.
    """
    iv = urandom(16)
    return symmetric_encrypt_with_iv(message, key, iv)


def symmetric_encrypt_HMAC(message: bytes, key: bytes, hmac_secret: bytes) -> bytes:
    """
    Encrypts a message using AES-CBC with HMAC-based IV.

    Args:
        message: The message to encrypt.
        key: The AES key.
        hmac_secret: The HMAC secret.

    Returns:
        The encrypted message as bytes.
    """
    prefix = urandom(3)
    hmac = hmac_sha1(hmac_secret, prefix + message)
    iv = hmac[:13] + prefix
    return symmetric_encrypt_with_iv(message, key, iv)


def symmetric_encrypt_with_iv(message: bytes, key: bytes, iv: bytes) -> bytes:
    """
    Encrypts a message using AES-CBC with the provided IV.

    Args:
        message: The message to encrypt.
        key: The AES key.
        iv: The initialization vector.

    Returns:
        The encrypted message as bytes.
    """
    encrypted_iv = AES.new(key, AES.MODE_ECB).encrypt(iv)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return encrypted_iv + cipher.encrypt(pad(message, 16))


def symmetric_decrypt(message: bytes, key: bytes) -> bytes:
    """
    Decrypts a message using AES-CBC with an ECB-encrypted IV.

    Args:
        message: The message to decrypt.
        key: The AES key.

    Returns:
        The decrypted message as bytes.
    """
    iv = symmetric_decrypt_iv(message, key)
    return symmetric_decrypt_with_iv(message, key, iv)


def symmetric_decrypt_HMAC(message: bytes, key: bytes, hmac_secret: bytes) -> bytes:
    """
    Decrypts a message using AES-CBC with HMAC verification.

    Args:
        message: The message to decrypt.
        key: The AES key.
        hmac_secret: The HMAC secret.

    Returns:
        The decrypted message as bytes.
    """
    iv = symmetric_decrypt_iv(message, key)
    decrypted_message = symmetric_decrypt_with_iv(message, key, iv)

    hmac = hmac_sha1(hmac_secret, iv[-3:] + decrypted_message)

    if iv[:13] != hmac[:13]:
        raise RuntimeError("Unable to decrypt message. HMAC does not match.")

    return decrypted_message


def symmetric_decrypt_iv(message: bytes, key: bytes) -> bytes:
    """
    Decrypts the IV from the beginning of the message using AES-ECB.

    Args:
        message: The message containing the encrypted IV.
        key: The AES key.

    Returns:
        The decrypted IV as bytes."""
    return AES.new(key, AES.MODE_ECB).decrypt(message[:16])


def symmetric_decrypt_with_iv(message: bytes, key: bytes, iv: bytes) -> bytes:
    """
    Decrypts a message using AES-CBC with the provided IV.

    Args:
        message: The message to decrypt.
        key: The AES key.
        iv: The initialization vector.

    Returns:
        The decrypted message as bytes.
    """
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(message[16:]), 16)


def hmac_sha1(secret: bytes, data: bytes) -> bytes:
    """
    Computes the HMAC-SHA1 of the given data using the provided secret.

    Args:
        secret: The HMAC secret.
        data: The data to hash.

    Returns:
        The HMAC-SHA1 digest as bytes.
    """
    return HMAC.new(secret, data, SHA1).digest()
