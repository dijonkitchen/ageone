# LLM from scratch

A small GPT built step by step to learn how language models work: a byte-pair tokenizer, a transformer with attention written out by hand, a training loop, sampling, and evaluation.
It trains on [TinyStories](https://arxiv.org/abs/2305.07759) on a CPU in about half an hour and writes short stories like these.

> Once upon a time, there was a little girl named Lily. Lily was always sad and alone. She wanted to find a modern toy. She asked her friend, Sam, for help.
> "Sam, can you help me find a modern toy?" asked Lily. Sam looked and looked, but a big, shiny thing could talk. He thought about it and decided to take a box. He found a big, shiny ball in the front of Lily.

Restarts [dijonkitchen/llm](https://github.com/dijonkitchen/llm); see the [spec](specs/SPEC-2026-09-30-llm-from-scratch.md) and the [stack decision](docs/decisions/2026-10-23-llm-from-scratch-stack.md).

## The steps

Each step is a module that opens by explaining what it does and why, and runs on its own from this folder (inside the root `make shell`, or anywhere with [uv](https://docs.astral.sh/uv/)).

| Step | Module | Run it |
| --- | --- | --- |
| 1. Corpus: download the pinned file, check its hash, split by seed | [`data.py`](src/llm_from_scratch/data.py) | `uv run python -m llm_from_scratch.data` |
| 2. Tokenizer: byte-level BPE with 2,048 tokens | [`tokenizer.py`](src/llm_from_scratch/tokenizer.py) | `uv run python -m llm_from_scratch.tokenizer` |
| 3. Model: embeddings, causal self-attention, MLP blocks | [`model.py`](src/llm_from_scratch/model.py) | (used by training) |
| 4. Training: AdamW, warmup and cosine decay, run record | [`train.py`](src/llm_from_scratch/train.py) | `uv run python -m llm_from_scratch.train --out runs/mine` |
| 5. Evaluation: bits per byte on held-out stories | [`evaluate.py`](src/llm_from_scratch/evaluate.py) | `uv run python -m llm_from_scratch.evaluate runs/mine` |
| 6. Generation: temperature and top-k sampling | [`generate.py`](src/llm_from_scratch/generate.py) | `uv run python -m llm_from_scratch.generate runs/mine "Tom found a box."` |
| 7. Comparison with TinyStories-1M | [`compare.py`](src/llm_from_scratch/compare.py) | `uv run --group compare python -m llm_from_scratch.compare runs/mine` |

Every hyperparameter is a flag (`--help` lists them); `--steps 300` gives a rough model in about 3 minutes.
Training uses an NVIDIA or Apple GPU when there is one, and the CPU otherwise.

## Results

The run in [`runs/tinystories-1.5m/`](runs/tinystories-1.5m/) used the defaults: seed 0, 6 blocks 128 wide with 4 heads, a 256-token context, and 3,000 steps of 32 windows (24.6M tokens, about 4.3 passes over the 5.7M training tokens).
It took 29 minutes on 4 CPU threads of a cloud container (x86-64, no GPU, PyTorch 2.14), the kind of CPU a laptop has; [`run.json`](runs/tinystories-1.5m/run.json) records the seeds, dataset hash, hyperparameters, environment, and loss curve.

Validation loss fell from 7.64 (a uniform guess over 2,048 tokens is 7.62) to 2.01 nats per token, and was still falling slowly at the end, with no sign of overfitting:

| Step | 0 | 250 | 500 | 1,000 | 1,500 | 2,000 | 2,500 | 3,000 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Validation loss | 7.64 | 3.46 | 2.91 | 2.48 | 2.27 | 2.13 | 2.05 | 2.01 |
| Minutes | 0.3 | 3.7 | 6.1 | 10.8 | 15.6 | 20.2 | 24.8 | 29.1 |

## Comparison with TinyStories-1M

[TinyStories-1M](https://huggingface.co/roneneldan/TinyStories-1M) is the smallest model the dataset's authors published: GPT-Neo, 8 blocks 64 wide, GPT-Neo's 50,257-token vocabulary, trained on the full training set (about 2 GB, against our 21 MB).
Both models scored the same 200 held-out stories (158,664 bytes) with a 256-token window, and completed the same prompts with temperature 0.8 and top-k 40 ([`compare.json`](runs/tinystories-1.5m/compare.json) has every number and sample).

| | Ours | TinyStories-1M |
| --- | --- | --- |
| Parameters | 1.48M | 3.75M |
| in token embeddings | 0.26M | 3.22M |
| in position embeddings | 0.03M | 0.13M |
| in blocks | 1.19M | 0.40M |
| Vocabulary | 2,048 | 50,257 |
| Training text | 21 MB, 4.3 passes | about 2 GB |
| Bits per byte on held-out stories (lower is better) | **0.755** | 0.780 |

Our model scores slightly better, and its samples read about as well: both keep characters and a setting, use dialogue, and drift in logic, as models this small do (ours: "Lily and Sam learned a new toy"; theirs: "They ate bread and ate the food").
Three things favor ours and keep this from being a fair race:

- The held-out stories come from the same file as our training stories (TinyStories v2, written by GPT-4 only), while TinyStories-1M trained on version 1, which mixes GPT-3.5 stories in.
- Our small vocabulary spends parameters on blocks rather than embeddings: we have three times its parameters in blocks.
- It has seen far more text, but at 0.4M parameters of blocks it may not be able to use it.

So the result says a from-scratch model of this size, trained for half an hour on a CPU, reaches the quality of the smallest published TinyStories model on GPT-4-written stories; it does not say ours is the better model.

The spec asked for this comparison through the repo's [model harness](../../harness/README.md), but the harness reaches models through OpenRouter, which hosts nothing this small and returns text rather than the token probabilities a loss comparison needs; the [stack decision](docs/decisions/2026-10-23-llm-from-scratch-stack.md) records the change to a local run.

## Reproducing

`uv run python -m llm_from_scratch.train --out runs/again` downloads the 22 MB file once into `.cache/`, checks its SHA-256, and reproduces the run; on the same machine and thread count the numbers match exactly, and elsewhere they differ slightly in the last digits.
Weights (`model.pt`, 6 MB) are not committed.
