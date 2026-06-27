"""CPOModule — wraps any DSPy Module so every forward() call emits a CPO."""

from __future__ import annotations

from typing import Any, Optional

from .client import CPOClient


class CPOModule:
    """Wraps an existing ``dspy.Module`` and attaches a CPO to its output.

    Pass any compiled or uncompiled DSPy module and CPOModule will intercept
    ``forward()`` calls, attest the final prediction, and attach proof metadata.

    Example::

        import dspy
        from dspy_cpo import CPOModule, CPOClient

        class MyRAG(dspy.Module):
            def __init__(self):
                self.retrieve = dspy.Retrieve(k=3)
                self.generate = dspy.ChainOfThought("context, question -> answer")

            def forward(self, question):
                ctx = self.retrieve(question).passages
                return self.generate(context=ctx, question=question)

        client = CPOClient("https://your-node.onrender.com")
        rag = CPOModule(MyRAG(), client)
        pred = rag(question="Who invented the telephone?")
        print(pred.answer)
        print(pred.cpo_hash)
    """

    def __init__(
        self,
        module: Any,
        client: CPOClient,
        world: str = "llm",
        answer_field: str = "answer",
    ) -> None:
        self.module = module
        self.client = client
        self.world = world
        self.answer_field = answer_field

    def __call__(self, **kwargs: Any) -> Any:
        pred = self.module(**kwargs)
        answer = str(getattr(pred, self.answer_field, pred))
        question = " ".join(str(v) for v in kwargs.values())
        claim = f"DSPy module output: {question[:120]}"
        code = f"output = {answer!r}\nprint(output)"
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

    def forward(self, **kwargs: Any) -> Any:
        return self(**kwargs)
