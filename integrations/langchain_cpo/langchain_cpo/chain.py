"""High-level chains that replace LLM calls with Proof Protocol-backed execution."""

from __future__ import annotations

from typing import Optional, TypedDict

from .client import CPOClient


class CPOVerifiedOutput(TypedDict):
    """The result of a CPO-backed question-answer call."""

    answer: str
    proof_hash: str
    signature: str
    cpo_id: str
    world: str
    exit_code: int
    runtime_ms: float
    verified: bool


class CPOAskChain:
    """Drop-in replacement for a code-generation LangChain chain.

    Sends a natural-language question to the Proof Protocol ``/ask``
    endpoint: the node generates Python code via its LLM brain, executes
    it in a sandboxed world, and returns the result as a signed CPO.

    Example::

        from langchain_cpo import CPOAskChain, CPOClient

        chain = CPOAskChain(CPOClient("https://your-node.onrender.com"))
        out = chain.invoke("What is the 10th Fibonacci number?")
        print(out["answer"])       # "55"
        print(out["proof_hash"])   # sha256 of the CPO payload
        print(out["verified"])     # True
    """

    def __init__(self, client: CPOClient, world: str = "llm") -> None:
        self.client = client
        self.world = world

    def invoke(self, question: str) -> CPOVerifiedOutput:
        result = self.client.ask(question, world=self.world)
        return CPOVerifiedOutput(
            answer=result.get("answer", ""),
            proof_hash=result.get("proof_hash", ""),
            signature=result.get("signature", ""),
            cpo_id=result.get("cpo_id", ""),
            world=result.get("world", self.world),
            exit_code=result.get("exit_code", -1),
            runtime_ms=result.get("runtime_ms", 0.0),
            verified=result.get("exit_code", -1) == 0,
        )

    async def ainvoke(self, question: str) -> CPOVerifiedOutput:
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(None, self.invoke, question)


class CPOProveChain:
    """Execute arbitrary code through the Proof Protocol sandbox and return a CPO.

    Useful when you already have the code (e.g. from a code-generation LLM)
    and want to produce a verifiable execution artifact before returning the
    result to the user.

    Example::

        from langchain_cpo import CPOProveChain, CPOClient

        chain = CPOProveChain(CPOClient("https://your-node.onrender.com"), world="symbolic")
        out = chain.invoke(
            claim="Factor x^2 - 1",
            code="from sympy import symbols, factor; x = symbols('x'); print(factor(x**2-1))",
        )
        print(out["answer"])     # "(x - 1)*(x + 1)"
        print(out["verified"])   # True
    """

    def __init__(self, client: CPOClient, world: str = "llm") -> None:
        self.client = client
        self.world = world

    def invoke(self, claim: str, code: str, world: Optional[str] = None) -> CPOVerifiedOutput:
        w = world or self.world
        result = self.client.prove(claim=claim, code=code, world=w)
        # Fetch the stored CPO to read stdout
        cpo_id = result.get("cpo_id", "")
        answer = ""
        if cpo_id:
            try:
                import requests

                resp = requests.get(
                    f"{self.client.base_url}/cpo/{cpo_id}", timeout=self.client.timeout
                )
                if resp.ok:
                    cpo = resp.json()
                    answer = (cpo.get("result") or {}).get("stdout", "").strip()
            except Exception:
                pass

        return CPOVerifiedOutput(
            answer=answer,
            proof_hash=result.get("content_hash", ""),
            signature=result.get("signature", ""),
            cpo_id=cpo_id,
            world=result.get("world", w),
            exit_code=result.get("exit_code", -1),
            runtime_ms=result.get("runtime_ms", 0.0),
            verified=result.get("exit_code", -1) == 0,
        )
