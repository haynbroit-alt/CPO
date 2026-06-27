"""LLM brain: converts a natural-language question into executable Python code."""
import os
import re

import anthropic

from config import BRAIN_MODEL

_SYSTEM_PROMPT = """\
You are a Python code generator for a sandboxed execution environment.
Given a question or task, output ONLY executable Python code — no markdown fences,
no prose, no comments, no explanations. The code must print its answer to stdout.
The sandbox has no network access and limited libraries (stdlib is always available;
NumPy, SymPy, and Pillow may be available depending on the world).
Output nothing except valid Python code."""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def _strip_fences(code: str) -> str:
    """Remove accidental markdown code fences if the model added them."""
    code = re.sub(r"^```(?:python)?\n?", "", code.strip())
    code = re.sub(r"\n?```$", "", code)
    return code.strip()


def generate_code(question: str, world: str = "llm") -> str:
    """Ask the LLM to produce Python code that answers *question*.

    Returns the raw source code as a string (no markdown fences).
    """
    world_hint = f" The target sandbox world is '{world}'." if world != "llm" else ""
    user_message = f"{question}{world_hint}"

    response = _get_client().messages.create(
        model=BRAIN_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text if response.content else ""
    return _strip_fences(raw)
