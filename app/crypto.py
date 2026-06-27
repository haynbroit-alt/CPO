"""Stateless cryptographic core — ENV-based node identity, zero filesystem writes.

Key loading priority:
  1. NODE_PRIVATE_KEY_B64 (base64-encoded PEM) — production / Render / K8s
  2. PRIVATE_KEY_FILE path — local dev fallback
  3. Auto-generated ephemeral key — dev-only, stderr warning, not persistent

Key rotation: increment NODE_KEY_ROTATION_ID (e.g. "v1" → "v2") to label a
new epoch. Old CPOs remain verifiable because pk is embedded in each CPO.
"""
import base64
import hashlib
import os
import sys

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

_NODE_KEY_ENV = "NODE_PRIVATE_KEY_B64"
_ROTATION_ID_ENV = "NODE_KEY_ROTATION_ID"


# ---------------------------------------------------------------------------
# Key loading (ENV-first, file fallback, ephemeral last-resort)
# ---------------------------------------------------------------------------

def load_private_key() -> Ed25519PrivateKey:
    # 1. Production path: key injected as base64 PEM via secret manager / env var
    key_b64 = os.getenv(_NODE_KEY_ENV)
    if key_b64:
        pem = base64.b64decode(key_b64.encode())
        return load_pem_private_key(pem, password=None)

    # 2. Dev path: key file on disk
    if os.path.exists(PRIVATE_KEY_FILE):
        with open(PRIVATE_KEY_FILE, "rb") as f:
            return load_pem_private_key(f.read(), password=None)

    # 3. Generate a new key and try to persist it; fall through to ephemeral on failure
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    try:
        with open(PRIVATE_KEY_FILE, "wb") as f:
            f.write(pem)
    except OSError:
        print(
            f"[WARNING] Cannot write {PRIVATE_KEY_FILE}; using ephemeral key. "
            f"Set {_NODE_KEY_ENV} for a persistent node identity.",
            file=sys.stderr,
        )
    return private


# ---------------------------------------------------------------------------
# Public key helpers
# ---------------------------------------------------------------------------

def public_key_bytes(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def node_id(pub_bytes: bytes) -> str:
    return hashlib.sha256(pub_bytes).hexdigest()[:16]


def get_rotation_id() -> str:
    return os.getenv(_ROTATION_ID_ENV, "v1")


# ---------------------------------------------------------------------------
# Cryptographic primitives
# ---------------------------------------------------------------------------

def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sign(private: Ed25519PrivateKey, payload: str) -> bytes:
    return private.sign(payload.encode("utf-8"))


def verify(pub_bytes: bytes, payload: str, sig_bytes: bytes) -> bool:
    try:
        pub: Ed25519PublicKey = Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub.verify(sig_bytes, payload.encode("utf-8"))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Key generation utility (called by scripts/generate_node_key.py)
# ---------------------------------------------------------------------------

def generate_key_b64() -> str:
    """Generate a new Ed25519 key and return it as base64-encoded PEM."""
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    return base64.b64encode(pem).decode()
