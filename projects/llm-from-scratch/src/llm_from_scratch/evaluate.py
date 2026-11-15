"""Step 5: evaluation.

Validation loss (cross-entropy per token) is what training watches, but it depends on the tokenizer: a
model with bigger tokens has fewer, harder predictions to make. To compare models with different
tokenizers we convert to bits per byte: the total negative log-likelihood of a text, in bits, divided by
its length in UTF-8 bytes. Lower is better; it is the number of bits the model would need to compress
the text.

Every story is scored on its own, starting from the end-of-text token, the way the model sees a story
begin during training. A story longer than the context is scored with a sliding window, so each token
still has (most of) a context's worth of history.
"""

import argparse
import json
import math
from collections.abc import Callable
from pathlib import Path

import torch
from torch.nn import functional as F

Logits = Callable[[torch.Tensor], torch.Tensor]


@torch.no_grad()
def nll(
    logits_fn: Logits, ids: list[int], context: int, stride: int | None = None
) -> float:
    """Total negative log-likelihood, in nats, of ids[1:] given what came before (ids[0] is the start token)."""
    stride = stride or context // 2
    total = 0.0
    scored = 1  # ids[0] is given, never predicted
    while scored < len(ids):
        end = min(scored + stride, len(ids))
        start = max(0, end - context - 1)
        window = torch.tensor([ids[start:end]])
        logits = logits_fn(window[:, :-1])[0]
        targets = window[0, 1:]
        new = end - scored  # only the tokens not scored by an earlier window
        total += F.cross_entropy(logits[-new:], targets[-new:], reduction="sum").item()
        scored = end
    return total


def bits_per_byte(
    logits_fn: Logits,
    encode: Callable[[str], list[int]],
    start: int,
    texts: list[str],
    context: int,
) -> float:
    """Bits per UTF-8 byte over texts, each scored on its own after the start token."""
    nats = sum(nll(logits_fn, [start, *encode(t)], context) for t in texts)
    return nats / math.log(2) / sum(len(t.encode("utf-8")) for t in texts)


def main() -> None:
    from llm_from_scratch import data
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
    args = parser.parse_args()
    model, tok, record = load_run(args.run)
    _, val = data.load(record["seed"])
    bpb = bits_per_byte(
        model, tok.encode, tok.eot, val[: args.stories], model.cfg.context
    )
    print(json.dumps({"stories": args.stories, "bits_per_byte": round(bpb, 4)}))


if __name__ == "__main__":
    main()
