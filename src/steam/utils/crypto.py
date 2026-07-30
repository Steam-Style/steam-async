from base64 import b64decode
from os import urandom

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_der_public_key


def load_universe_public_key() -> RSAPublicKey:
    key = load_der_public_key(b64decode("""
MIGdMA0GCSqGSIb3DQEBAQUAA4GLADCBhwKBgQDf7BrWLBBmLBc1OhSwfFkRf53T
2Ct64+AVzRkeRuh7h3SiGEYxqQMUeYKO6UWiSRKpI2hzic9pobFhRr3Bvr/WARvY
gdTckPv+T1JzZsuVcNfFjrocejN1oWI0Rrtgt4Bo+hOneoo3S57G9F1fOpn5nsQ6
6WOiu4gZKODnFMBCiQIBEQ==
"""))
    if not isinstance(key, RSAPublicKey):
        raise TypeError("Expected the Universe key to be an RSA public key")
    return key


def generate_session_key(hmac_secret: bytes = b"") -> tuple[bytes, bytes]:
    """
    Generates a session key and its encrypted form using the Universe public key.

    Args:
        hmac_secret: Optional HMAC secret to append to the session key before encryption.

    Returns:
        A tuple containing the session key and its encrypted form.
    """
    session_key = urandom(32)
    encrypted_session_key = load_universe_public_key().encrypt(
        session_key + hmac_secret,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None,
        ),
    )

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
    tag = hmac_sha1(hmac_secret, prefix + message)
    iv = tag[:13] + prefix
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
    ecb_encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    encrypted_iv = ecb_encryptor.update(iv) + ecb_encryptor.finalize()

    padder = sym_padding.PKCS7(128).padder()
    padded_message = padder.update(message) + padder.finalize()

    cbc_encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = cbc_encryptor.update(
        padded_message) + cbc_encryptor.finalize()

    return encrypted_iv + ciphertext


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

    tag = hmac_sha1(hmac_secret, iv[-3:] + decrypted_message)

    if iv[:13] != tag[:13]:
        raise RuntimeError("Unable to decrypt message. HMAC does not match.")

    return decrypted_message


def symmetric_decrypt_iv(message: bytes, key: bytes) -> bytes:
    """
    Decrypts the IV from the beginning of the message using AES-ECB.

    Args:
        message: The message containing the encrypted IV.
        key: The AES key.

    Returns:
        The decrypted IV as bytes.
    """
    ecb_decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return ecb_decryptor.update(message[:16]) + ecb_decryptor.finalize()


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
    cbc_decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded_message = cbc_decryptor.update(
        message[16:]) + cbc_decryptor.finalize()

    unpadder = sym_padding.PKCS7(128).unpadder()
    return unpadder.update(padded_message) + unpadder.finalize()


def hmac_sha1(secret: bytes, data: bytes) -> bytes:
    """
    Computes the HMAC-SHA1 of the given data using the provided secret.

    Args:
        secret: The HMAC secret.
        data: The data to hash.

    Returns:
        The HMAC-SHA1 digest as bytes.
    """
    h = hmac.HMAC(secret, hashes.SHA1())
    h.update(data)
    return h.finalize()
