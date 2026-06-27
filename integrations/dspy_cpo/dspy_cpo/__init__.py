"""dspy-cpo — Proof Protocol adapter for DSPy.

Wrap any DSPy module so every forward pass produces a signed CPO.
"""

from .module import CPOModule
from .predict import CPOPredict
from .client import CPOClient

__all__ = [
    "CPOClient",
    "CPOModule",
    "CPOPredict",
]
