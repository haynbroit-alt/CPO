"""SIOS connectors — pull real financial data from external APIs."""

from __future__ import annotations

__all__ = ["AWSConnector", "StripeConnector"]


def _lazy_import(module: str, name: str):
    def _get():
        import importlib
        mod = importlib.import_module(module)
        return getattr(mod, name)
    return _get


AWSConnector = _lazy_import("sios.connectors.aws", "AWSConnector")
StripeConnector = _lazy_import("sios.connectors.stripe", "StripeConnector")
