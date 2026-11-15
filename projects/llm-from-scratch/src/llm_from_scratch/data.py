"""Step 1: the corpus.

TinyStories is a set of short stories written by GPT-3.5 and GPT-4 in the vocabulary of a young child,
made so that very small models can learn to write fluent English (Eldan and Li, 2023, arXiv:2305.07759).
We use the GPT-4 validation file of version 2 (about 22 MB, 27,630 stories): it is small enough to download
and tokenize in seconds, and big enough for a model of a few million parameters to train on for an hour.

The file is pinned to a dataset revision and checked against its SHA-256, so every run sees the same bytes.
The stories are split into train and validation sets by a seeded shuffle, so the split is reproducible too.
"""

import argparse
import hashlib
import random
import urllib.request
from pathlib import Path

REVISION = "f54c09fd23315a6f9c86f9dc80f725de7d8f9c64"
FILE = "TinyStoriesV2-GPT4-valid.txt"
URL = (
    f"https://huggingface.co/datasets/roneneldan/TinyStories/resolve/{REVISION}/{FILE}"
)
SHA256 = "6874bae9a4c1a4e7edcf0e53b86c17817e9cf881fc75ff2368da457b80c0585d"
EOT = "<|endoftext|>"
CACHE = Path(".cache")


def download(cache: Path = CACHE) -> Path:
    """Download the pinned file once and verify it; later calls reuse the cached copy."""
    path = cache / FILE
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(".part")
        urllib.request.urlretrieve(URL, part)
        part.rename(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SHA256:
        raise ValueError(
            f"{path} has SHA-256 {digest}, expected {SHA256}; delete it and download again"
        )
    return path


def stories(text: str) -> list[str]:
    """Split the file on the end-of-text marker and drop blank entries."""
    return [s.strip() for s in text.split(EOT) if s.strip()]


def split(
    items: list[str], val_fraction: float, seed: int
) -> tuple[list[str], list[str]]:
    """Shuffle with a fixed seed and hold out a fraction for validation."""
    shuffled = items[:]
    random.Random(seed).shuffle(shuffled)
    n_val = max(1, round(len(shuffled) * val_fraction))
    return shuffled[n_val:], shuffled[:n_val]


def load(
    seed: int = 0, val_fraction: float = 0.05, cache: Path = CACHE
) -> tuple[list[str], list[str]]:
    """The train and validation stories for a seed."""
    return split(
        stories(download(cache).read_text(encoding="utf-8")), val_fraction, seed
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    train, val = load(args.seed)
    print(f"{len(train)} train stories, {len(val)} validation stories")
    print(f"first train story:\n{train[0]}")


if __name__ == "__main__":
    main()
