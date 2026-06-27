# langchain-cpo

**Proof Protocol adapter for LangChain** — attach cryptographic execution proofs to any LLM call, chain, or agent.

Every LLM output becomes a signed, replayable **Computational Proof Object (CPO)** stored on-node. Proofs travel with the result; anyone can re-execute and verify independently.

## Installation

```bash
pip install langchain-cpo
```

> Requires a running [Proof Protocol node](https://github.com/haynbroit-alt/cpo). Start one locally with `uvicorn app.main:app` or point at a hosted instance.

## Quick start

### Option 1 — Callback handler (attach proofs to any existing LLM)

```python
from langchain_openai import ChatOpenAI
from langchain_cpo import CPOCallbackHandler, CPOClient

client = CPOClient("https://your-node.onrender.com")
llm = ChatOpenAI(callbacks=[CPOCallbackHandler(client)])

result = llm.invoke("What is the square root of 144?")
print(result.content)
# → "The square root of 144 is 12."

# Proof metadata attached to every generation
meta = result.response_metadata
print(meta["cpo_hash"])       # sha256 of the CPO payload
print(meta["cpo_id"])         # UUID for retrieval via /cpo/<id>
print(meta["cpo_signature"])  # Ed25519 signature (hex)
```

### Option 2 — CPOAskChain (question → verified answer)

Uses the node's `/ask` endpoint: the node generates code via its LLM, executes it in a sandboxed world, and returns the result as a signed CPO.

```python
from langchain_cpo import CPOAskChain, CPOClient

chain = CPOAskChain(CPOClient("https://your-node.onrender.com"))
out = chain.invoke("What is the 10th Fibonacci number?")

print(out["answer"])      # "55"
print(out["proof_hash"])  # sha256 of CPO payload
print(out["verified"])    # True (exit_code == 0)
print(out["world"])       # "llm"
```

### Option 3 — CPOProveChain (code → verified execution)

Use when you already have code (e.g. from a code-generation LLM) and want a verifiable execution artifact.

```python
from langchain_cpo import CPOProveChain, CPOClient

chain = CPOProveChain(CPOClient("https://your-node.onrender.com"), world="symbolic")
out = chain.invoke(
    claim="Factor x^2 - 1",
    code="from sympy import symbols, factor; x = symbols('x'); print(factor(x**2-1))",
)

print(out["answer"])    # "(x - 1)*(x + 1)"
print(out["verified"])  # True
```

## Async support

Both chain classes expose `ainvoke`:

```python
import asyncio

out = asyncio.run(chain.ainvoke("What is 17 * 23?"))
```

## Supported worlds

| World | Description |
|---|---|
| `llm` | General-purpose LLM execution |
| `symbolic` | Computer algebra (SymPy) |
| `neuro` | Neural / PyTorch computation |
| `bayesian` | Probabilistic inference |
| `evolutionary` | Genetic algorithms |
| `formal` | Formal verification |
| `multimodal` | Vision + language tasks |

## CPOClient API

```python
client = CPOClient(base_url="http://localhost:8000", timeout=30)

client.prove(claim, code, world="llm")  # POST /prove
client.ask(question, world="llm")       # POST /ask
client.verify(content_hash)             # GET /verify/{hash}
client.node_info()                      # GET /node
client.health()                         # GET /health → bool
```

## Verifying a proof

```python
verdict = client.verify(out["proof_hash"])
print(verdict["verified"])       # True
print(verdict["signature_valid"]) # True
print(verdict["stdout_match"])    # True
```

## What is a CPO?

A **Computational Proof Object** is a signed tuple `(world, claim, code, result, timestamp, node_id, rotation_id)` where:

- `code` was executed deterministically inside a Bounded Execution Environment (BEE)
- `result.stdout` is the observable output
- `content_hash = sha256(canonical_json(cpo_fields))`
- `signature = Ed25519.sign(private_key, content_hash)`

Anyone holding the public key can verify the signature and re-execute the code to confirm the result independently.

## License

MIT
