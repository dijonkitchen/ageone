"""Step 6: generation.

The model gives a probability for every next token; we sample one, append it, and repeat. Temperature
below 1 sharpens the distribution toward likely tokens, and top-k sampling ignores all but the k most
likely ones, which together trade a little variety for much more coherent text. Generation stops at the
end-of-text token, where a story ends.
"""

import argparse
from pathlib import Path

import torch

from llm_from_scratch.model import GPT
from llm_from_scratch.tokenizer import Tokenizer

PROMPTS = [
    "Once upon a time, there was a little girl named Lily.",
    "Tom and his dog went to the park.",
    "The sun was hot, so Ben",
]


def complete(
    model: GPT,
    tok: Tokenizer,
    prompt: str,
    seed: int,
    tokens: int = 200,
    temperature: float = 0.8,
    top_k: int = 40,
) -> str:
    generator = torch.Generator().manual_seed(seed)
    ids = torch.tensor([[tok.eot, *tok.encode(prompt)]])
    model.eval()
    out = model.generate(
        ids,
        tokens,
        temperature=temperature,
        top_k=top_k,
        stop=tok.eot,
        generator=generator,
    )
    return tok.decode([i for i in out[0, 1:].tolist() if i != tok.eot])


def main() -> None:
    from llm_from_scratch.train import load_run

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "run", type=Path, help="a run folder written by llm_from_scratch.train"
    )
    parser.add_argument("prompt", nargs="?", default=PROMPTS[0])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--tokens", type=int, default=200)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=40)
    args = parser.parse_args()
    model, tok, _ = load_run(args.run)
    print(
        complete(
            model,
            tok,
            args.prompt,
            args.seed,
            args.tokens,
            args.temperature,
            args.top_k,
        )
    )


if __name__ == "__main__":
    main()
