import pytest
from pydantic import ValidationError

from app.models import CPO, ExecutionSpec, ExecutionResult


def test_cpo_default_world():
    cpo = CPO(claim="1+1=2", code="print(1+1)")
    assert cpo.world == "llm"


def test_cpo_valid_worlds():
    worlds = ["llm", "symbolic", "neuro", "bayesian", "evolutionary", "formal", "multimodal"]
    for w in worlds:
        cpo = CPO(claim="test", code="pass", world=w)
        assert cpo.world == w


def test_cpo_invalid_world():
    with pytest.raises(ValidationError):
        CPO(claim="test", code="pass", world="quantum")


def test_execution_spec_defaults():
    spec = ExecutionSpec()
    assert spec.runtime == "python"
    assert spec.image is None
    assert spec.constraints["timeout"] == 10
    assert spec.constraints["memory_mb"] == 128


def test_execution_result():
    r = ExecutionResult(stdout="hello", stderr="", exit_code=0, runtime_ms=12.5)
    assert r.exit_code == 0
    assert r.runtime_ms == 12.5
