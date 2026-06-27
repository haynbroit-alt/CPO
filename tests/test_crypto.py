import os
import tempfile

from app.crypto import (
    load_private_key,
    node_id,
    public_key_bytes,
    sha256,
    sign,
    verify,
)


def test_sign_verify_roundtrip():
    priv = load_private_key(tempfile.mktemp(suffix=".pem"))
    pub = public_key_bytes(priv)
    payload = '{"claim":"1+1=2"}'
    sig = sign(priv, payload)
    assert verify(pub, payload, sig) is True


def test_verify_fails_on_tampered_payload():
    priv = load_private_key(tempfile.mktemp(suffix=".pem"))
    pub = public_key_bytes(priv)
    sig = sign(priv, "original")
    assert verify(pub, "tampered", sig) is False


def test_node_id_deterministic():
    priv = load_private_key(tempfile.mktemp(suffix=".pem"))
    pub = public_key_bytes(priv)
    assert node_id(pub) == node_id(pub)
    assert len(node_id(pub)) == 64  # sha256 hex


def test_sha256_deterministic():
    assert sha256("hello") == sha256("hello")
    assert sha256("hello") != sha256("world")


def test_keypair_persisted(tmp_path):
    key_file = str(tmp_path / "key.pem")
    priv1 = load_private_key(key_file)
    priv2 = load_private_key(key_file)
    assert public_key_bytes(priv1) == public_key_bytes(priv2)
