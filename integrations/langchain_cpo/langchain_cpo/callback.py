"""LangChain callback handler that attests every LLM output as a CPO."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from .client import CPOClient


class CPOCallbackHandler(BaseCallbackHandler):
    """Attach a signed Computational Proof Object to every LLM generation.

    Add this handler to any LangChain LLM or chain and every output will
    carry a ``cpo_hash``, ``cpo_id``, and ``cpo_signature`` in its
    ``generation_info`` metadata.  Attestation failures are silently
    recorded in ``cpo_error`` — they never interrupt the LLM call.

    Example::

        from langchain_openai import ChatOpenAI
        from langchain_cpo import CPOCallbackHandler, CPOClient

        client = CPOClient("https://your-node.onrender.com")
        llm = ChatOpenAI(callbacks=[CPOCallbackHandler(client)])
        result = llm.invoke("What is the square root of 144?")
        print(result.response_metadata.get("cpo_hash"))
    """

    def __init__(
        self,
        client: CPOClient,
        world: str = "llm",
        max_claim_length: int = 120,
    ) -> None:
        super().__init__()
        self.client = client
        self.world = world
        self.max_claim_length = max_claim_length
        self._prompts: List[str] = []

    # ------------------------------------------------------------------
    # LangChain callback hooks
    # ------------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        self._prompts = prompts

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        for i, generations in enumerate(response.generations):
            prompt = self._prompts[i] if i < len(self._prompts) else ""
            claim = f"LLM output: {prompt[: self.max_claim_length]}"
            for gen in generations:
                text = getattr(gen, "text", str(gen))
                # Wrap the raw output in an executable print() so it is
                # valid Python that the sandbox can replay deterministically.
                code = f"output = {text!r}\nprint(output)"
                meta: Dict[str, Any] = gen.generation_info or {}
                try:
                    result = self.client.prove(claim=claim, code=code, world=self.world)
                    meta["cpo_hash"] = result.get("content_hash")
                    meta["cpo_id"] = result.get("cpo_id")
                    meta["cpo_signature"] = result.get("signature")
                    meta["cpo_node"] = result.get("node_id")
                except Exception as exc:
                    meta["cpo_error"] = str(exc)
                gen.generation_info = meta
