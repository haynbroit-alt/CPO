# dspy-cpo

**Proof Protocol adapter for DSPy** — every forward pass produces a signed, replayable Computational Proof Object (CPO).

## Installation

```bash
pip install dspy-cpo
# with DSPy:
pip install "dspy-cpo[dspy]"
```

## Quick start

### Wrap a DSPy module

```python
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
print(pred.cpo_hash)    # sha256 of CPO payload
print(pred.cpo_verified) # True
```

### Verified Predict

```python
from dspy_cpo import CPOPredict, CPOClient

client = CPOClient("https://your-node.onrender.com")
qa = CPOPredict("question -> answer", client=client)

pred = qa(question="What is the boiling point of water?")
print(pred.answer)
print(pred.cpo_hash)
print(pred.cpo_verified)
```

### Standalone (no DSPy required)

```python
from dspy_cpo import CPOPredict, CPOClient

client = CPOClient("https://your-node.onrender.com")
pred = CPOPredict(client=client)

result = pred.ask("What is 2^10?")
print(result["answer"])    # "1024"
print(result["verified"])  # True
```

## What gets attested

For every forward pass, `dspy-cpo` calls the Proof Protocol `/prove` endpoint with:
- `claim`: the input question/context (truncated to 120 chars)
- `code`: `print(repr(answer))` — a deterministic, replayable Python snippet
- `world`: configurable (default `"llm"`)

The node executes the code in a Bounded Execution Environment (BEE), signs the result with Ed25519, and returns a `content_hash` and `signature` attached to the prediction object as `cpo_hash`, `cpo_id`, `cpo_signature`, `cpo_verified`.

## License

MIT
