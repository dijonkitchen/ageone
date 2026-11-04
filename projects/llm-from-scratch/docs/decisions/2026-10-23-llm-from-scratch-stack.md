# Decision Record 2026-10-23: llm-from-scratch Stack

## Status timeline

2026-10-23: Proposed by Claude, from the spec, in the scheduled spec job JC approved

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-llm-from-scratch.md) that builds a tokenizer, a GPT-style transformer, a training loop, and text generation step by step, trains on a laptop's CPU or Apple GPU in under an hour, and compares the result with a tiny open-weight model.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
Reproducible: seeds, the dataset revision and hash, and every hyperparameter are recorded with each run.
Readable: each step explains what it does and why, and runs on its own.

### Nice to haves

#### Functional

Bigger runs on a GPU with the same code, by flags alone.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Chasing state-of-the-art tricks (rotary embeddings, flash attention, mixed precision, KV caching) before the plain model is understood.
Training on the full 2 GB TinyStories set, which takes a laptop far longer than an hour to tokenize and learn.

#### Non-functional

## Decision

Started from the python project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
The old repo, [dijonkitchen/llm](https://github.com/dijonkitchen/llm), chose Python, PyTorch, micromamba, and notebooks, and stopped after checking PyTorch and the GPU.
Python and PyTorch still hold; micromamba and notebooks give way to uv and scripts.

- **Python 3.12 and PyTorch 2.14**, installed by uv. On Linux, uv takes PyTorch's CPU wheels from `download.pytorch.org/whl/cpu`, because the default Linux wheels pull in gigabytes of CUDA libraries that CI and a laptop without an NVIDIA GPU never use; on macOS the PyPI wheels include the Apple GPU (MPS) backend, which training picks up on its own.
- **Scripts, not notebooks**: one module per step (`data`, `tokenizer`, `model`, `train`, `generate`, `evaluate`, `compare`), each opening with a docstring that explains the step and runnable on its own with `python -m`. They pass ruff, strict mypy, and pytest in CI, which notebooks would not without extra tooling, and diffs stay readable.
- **Everything from scratch except tensors and autograd**: a byte-level BPE tokenizer in plain Python, attention written out by hand rather than with `scaled_dot_product_attention`, and our own training loop. PyTorch supplies tensors, gradients, `nn.Linear`, `nn.LayerNorm`, and AdamW.
- **Data: TinyStories v2, GPT-4 validation file** (`roneneldan/TinyStories` at revision `f54c09fd`, 22 MB, 27,630 stories, checked by SHA-256), split 95/5 by a seeded shuffle. It is the corpus made for models this small, and one file downloads and tokenizes in seconds.
- **Comparison: TinyStories-1M** (`roneneldan/TinyStories-1M` at revision `77f1b168`), run locally with Hugging Face `transformers` from an optional `compare` dependency group, scored in bits per byte on the same held-out stories.

### High-level C4(context/container/component/code) diagram

```
TinyStories file (pinned, hashed) --> stories --seeded split--> train / validation
train stories --> BPE tokenizer (2,048 tokens) --> token stream
token stream --> GPT (6 blocks, 128 wide, 256 context) --AdamW, cosine LR--> model.pt + run.json
model.pt --> generate (samples) / evaluate (bits per byte)
TinyStories-1M (pinned) --> compare: same stories, same prompts --> compare.json --> README
```

### Choices and Tradeoffs/Risks

- The spec asked for the comparison to run through the [vendor-neutral harness](../../../../harness/README.md) runner. That runner calls models through OpenRouter, which hosts no model anywhere near this size, and its interface returns text rather than the per-token probabilities a loss comparison needs; so the comparison runs locally through `transformers`. A local backend for the harness can come later if other projects need one.
- Bits per byte rather than validation loss for the comparison: the two models use different tokenizers (2,048 against 50,257 tokens), so their per-token losses are not comparable, while bits per byte is.
- The validation file rather than the 2 GB training file: our 1.5M-parameter model sees about 25M tokens in under an hour, a few passes over the 5.7M-token file, so more data would not change the result much, and the held-out 5% is never trained on. TinyStories-1M was trained on the training file, so neither model has seen the held-out stories.
- A 2,048-token vocabulary: with GPT-2's 50,257 the embedding table alone would hold 6.4M parameters at width 128, dwarfing the rest of the model; 2,048 covers TinyStories' small vocabulary at about 3.7 bytes per token.
- Run records (`run.json`, `compare.json`) are committed and the weights are not: the weights are 6 MB, and the record holds the seeds, dataset hash, and hyperparameters to train them again in under an hour.
- CPU threads make training deterministic on one machine, not across machines or between CPU and GPU, so run.json records the device, thread count, and library versions alongside the seeds.

### Dependencies

`torch` and `numpy` at run time; `transformers` only in the optional `compare` group, so `make check` and CI never install it.

### Interfaces

- `uv run python -m llm_from_scratch.train --out runs/<name>` with any hyperparameter as a flag writes `model.pt`, `tokenizer.json`, and `run.json`.
- `uv run python -m llm_from_scratch.generate runs/<name> "<prompt>"` prints a completion.
- `uv run python -m llm_from_scratch.evaluate runs/<name>` prints bits per byte.
- `uv run --group compare python -m llm_from_scratch.compare runs/<name>` writes `compare.json`.

## Key Results and retrospective feedback

2026-10-23: the first run (3,000 steps, 1.48M parameters) took 29 minutes on 4 CPU threads, reached 2.01 validation loss and 0.755 bits per byte, and writes coherent-looking stories; TinyStories-1M scored 0.780 on the same stories ([README](../../README.md#comparison-with-tinystories-1m)).
