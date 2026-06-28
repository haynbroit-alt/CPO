"""CPOPredict — a DSPy Predict replacement that attests every forward pass."""

from __future__ import annotations

from typing import Any, Optional

from .client import CPOClient


class CPOPredict:
    """Drop-in wrapper around ``dspy.Predict`` that attaches a CPO to every call.

    If DSPy is not installed, falls back to calling the Proof Protocol ``/ask``
    endpoint directly, acting as a standalone verified-prediction primitive.

    Example with DSPy::

        import dspy
        from dspy_cpo import CPOPredict, CPOClient

        client = CPOClient("https://your-node.onrender.com")
        qa = CPOPredict("question -> answer", client=client)
        pred = qa(question="What is the boiling point of water?")
        print(pred.answer)
        print(pred.cpo_hash)
        print(pred.cpo_verified)

    Example standalone (no DSPy)::

        from dspy_cpo import CPOPredict, CPOClient

        client = CPOClient("https://your-node.onrender.com")
        pred = CPOPredict(client=client)
        result = pred.ask("What is 2^10?")
        print(result["answer"])    # "1024"
        print(result["verified"])  # True
    """

    def __init__(
        self,
        signature: Optional[str] = None,
        client: Optional[CPOClient] = None,
        world: str = "llm",
        **kwargs: Any,
    ) -> None:
        self.client = client
        self.world = world
        self._dspy_predict: Any = None

        if signature is not None:
            try:
                import dspy  # type: ignore[import]

                self._dspy_predict = dspy.Predict(signature, **kwargs)
            except ImportError:
                pass

    # ------------------------------------------------------------------
    # DSPy-mode: intercept __call__
    # ------------------------------------------------------------------

    def __call__(self, **kwargs: Any) -> Any:
        if self._dspy_predict is None:
            raise RuntimeError(
                "DSPy is not installed. Use CPOPredict.ask() for standalone use."
            )

        pred = self._dspy_predict(**kwargs)

        if self.client is not None:
            question = " ".join(str(v) for v in kwargs.values())
            answer = str(getattr(pred, list(vars(pred).keys())[0], pred))
            code = f"output = {answer!r}\nprint(output)"
            claim = f"DSPy prediction: {question[:120]}"
            try:
                result = self.client.prove(claim=claim, code=code, world=self.world)
                pred.cpo_hash = result.get("content_hash")
                pred.cpo_id = result.get("cpo_id")
                pred.cpo_signature = result.get("signature")
                pred.cpo_verified = result.get("exit_code", -1) == 0
            except Exception as exc:
                pred.cpo_error = str(exc)
                pred.cpo_verified = False

        return pred

    # ------------------------------------------------------------------
    # Standalone mode
    # ------------------------------------------------------------------

    def ask(self, question: str) -> dict:
        """Ask the Proof Protocol node directly (no DSPy required)."""
        if self.client is None:
            raise ValueError("CPOClient required for standalone use.")
        result = self.client.ask(question, world=self.world)
        return {
            "answer": result.get("answer", ""),
            "proof_hash": result.get("proof_hash", ""),
            "cpo_id": result.get("cpo_id", ""),
            "signature": result.get("signature", ""),
            "world": result.get("world", self.world),
            "exit_code": result.get("exit_code", -1),
            "verified": result.get("exit_code", -1) == 0,
        }
