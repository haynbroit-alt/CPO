import hashlib
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

from config import PRIVATE_KEY_FILE


def _generate_keypair() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def _save_private_key(private: Ed25519PrivateKey, path: str) -> None:
    pem = private.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    with open(path, "wb") as f:
        f.write(pem)


def load_private_key(path: str = PRIVATE_KEY_FILE) -> Ed25519PrivateKey:
    if not os.path.exists(path):
        private = _generate_keypair()
        _save_private_key(private, path)
        return private
    with open(path, "rb") as f:
        return load_pem_private_key(f.read(), password=None)


def public_key_bytes(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def node_id(pub_bytes: bytes) -> str:
    return hashlib.sha256(pub_bytes).hexdigest()


def sign(private: Ed25519PrivateKey, payload: str) -> bytes:
    return private.sign(payload.encode("utf-8"))


def verify(pub_bytes: bytes, payload: str, sig_bytes: bytes) -> bool:
    try:
        pub: Ed25519PublicKey = Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub.verify(sig_bytes, payload.encode("utf-8"))
        return True
    except Exception:
        return False


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
