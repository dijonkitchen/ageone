# SPEC-0017: LLM from Scratch

Restarts [dijonkitchen/llm](https://github.com/dijonkitchen/llm) in `projects/llm-from-scratch/`, per [Projects in ageone](../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `docs/decisions/llm-from-scratch/`.

A small language model built from scratch to learn how LLMs work; the old repo stopped at checking PyTorch and the GPU.

## Functional requirements

- Notebooks or scripts that build, step by step: a tokenizer, a GPT-style transformer, a training loop, and text generation.
- Train on a small public corpus on a laptop (Apple GPU or CPU) in under an hour.
- Evaluate with validation loss and sample outputs, and compare against a tiny open-weight model of similar size run through the SPEC-0002 runner.

## Non-functional requirements

- Reproducible: seeds, dataset version, and hyperparameters are recorded with each run.
- Readable: each step explains what it does and why, and runs on its own.

## Definition of done

1. The first decision record in `docs/decisions/llm-from-scratch/` chooses the stack (old: Python, PyTorch, micromamba, notebooks).
2. `projects/llm-from-scratch/` is set up by `make`, and its CI job passes on `main`.
3. A training run from scratch finishes on a laptop and generates coherent-looking text.
4. The comparison with a tiny open-weight model is written up in the project README.
