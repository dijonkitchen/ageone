"""Step 7: compare with a published model of similar size.

TinyStories-1M (Eldan and Li, 2023) is a GPT-Neo model trained by the dataset's authors on the full
TinyStories training set (about 2 GB of text, against our 21 MB), with GPT-Neo's 50,257-token vocabulary.
Its eight blocks hold about 0.4M parameters, but its embedding table alone holds 3.2M, so it has about
3.7M in all; ours has 1.5M, most of them in its six blocks.

Both models score the same held-out stories in bits per byte, which does not depend on the tokenizer, and
complete the same prompts with the same sampling settings. The model is pinned to a revision.

This step needs the optional `compare` dependencies: `uv run --group compare python -m llm_from_scratch.compare`.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from llm_from_scratch import data
from llm_from_scratch.evaluate import bits_per_byte
from llm_from_scratch.generate import PROMPTS, complete

MODEL = "roneneldan/TinyStories-1M"
REVISION = "77f1b168e219585646439073245fe87e56b3023e"
CONTEXT = 256  # the model's local attention window; scoring both models with the same history keeps it fair


def main() -> None:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from llm_from_scratch.train import load_run

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "run", type=Path, help="a run folder written by llm_from_scratch.train"
    )
    parser.add_argument(
        "--stories", type=int, default=200, help="validation stories to score"
    )
    parser.add_argument("--tokens", type=int, default=200)
    args = parser.parse_args()

    ours, tok, record = load_run(args.run)
    _, val = data.load(record["seed"])
    texts = val[: args.stories]
    seed = record["seed"]

    theirs = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION).eval()
    their_tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    eos = their_tok.eos_token_id

    def their_logits(ids: torch.Tensor) -> torch.Tensor:
        return theirs(ids).logits  # type: ignore[no-any-return]

    def their_encode(text: str) -> list[int]:
        return their_tok(text)["input_ids"]  # type: ignore[no-any-return]

    def their_complete(prompt: str) -> str:
        torch.manual_seed(seed)
        ids = torch.tensor([[eos, *their_encode(prompt)]])
        out = theirs.generate(
            ids,
            attention_mask=torch.ones_like(ids),
            max_new_tokens=args.tokens,
            do_sample=True,
            temperature=0.8,
            top_k=40,
            eos_token_id=eos,
            pad_token_id=eos,
        )
        return their_tok.decode([i for i in out[0, 1:].tolist() if i != eos])  # type: ignore[no-any-return]

    result: dict[str, Any] = {
        "stories": len(texts),
        "bytes": sum(len(t.encode("utf-8")) for t in texts),
        "context": CONTEXT,
        "ours": {
            "run": str(args.run),
            "parameters": ours.parameters_count(),
            "vocab_size": tok.vocab_size,
            "bits_per_byte": round(
                bits_per_byte(ours, tok.encode, tok.eot, texts, CONTEXT), 4
            ),
            "samples": [complete(ours, tok, p, seed, args.tokens) for p in PROMPTS],
        },
        "theirs": {
            "model": MODEL,
            "revision": REVISION,
            "parameters": sum(p.numel() for p in theirs.parameters()),
            "vocab_size": len(their_tok),
            "bits_per_byte": round(
                bits_per_byte(their_logits, their_encode, eos, texts, CONTEXT), 4
            ),
            "samples": [their_complete(p) for p in PROMPTS],
        },
    }
    (args.run / "compare.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("ours", "theirs")}))
    for name in ("ours", "theirs"):
        side = result[name]
        print(
            f"\n{name}: {side['parameters']:,} parameters, {side['bits_per_byte']} bits per byte"
        )
        for sample in side["samples"]:
            print(f"\n{sample}")


if __name__ == "__main__":
    main()
