from app.canon import canonicalize


def test_key_order_deterministic():
    a = canonicalize({"z": 1, "a": 2})
    b = canonicalize({"a": 2, "z": 1})
    assert a == b


def test_nested_deterministic():
    obj = {"b": {"y": 10, "x": 20}, "a": [3, 1, 2]}
    out = canonicalize(obj)
    assert out == '{"a":[3,1,2],"b":{"x":20,"y":10}}'


def test_unicode_preserved():
    out = canonicalize({"emoji": "café"})
    assert "café" in out
