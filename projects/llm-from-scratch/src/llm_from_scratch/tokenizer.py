"""Step 2: the tokenizer.

A model reads integers, not text. Byte-pair encoding (BPE; Sennrich et al., 2016, as used by GPT-2) starts
from the 256 byte values, so any text can be encoded, then repeatedly merges the most frequent adjacent pair
of tokens into a new token until the vocabulary reaches the size we want. Frequent words become one token,
rare words stay as several, and nothing is ever out of vocabulary.

Before counting pairs, text is cut into words with a regular expression (as GPT-2 does) so merges never
cross a word boundary: " dog" and "." stay separate tokens instead of merging into " dog.".
Because training only looks at the counts of distinct words, it runs on tens of megabytes in seconds.

The end-of-text marker is a special token: it is never split and never learned from the text.
"""

import argparse
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from llm_from_scratch.data import EOT

# Contractions, words with an optional leading space, numbers, punctuation runs, and whitespace.
PATTERN = re.compile(
    r"'(?:[sdmt]|ll|ve|re)| ?[^\W\d_]+| ?\d+| ?(?:[^\s\w]|_)+|\s+(?!\S)|\s+"
)

Pair = tuple[int, int]


class Tokenizer:
    def __init__(self, merges: list[Pair]) -> None:
        self.merges = merges
        self.ranks: dict[Pair, int] = {pair: rank for rank, pair in enumerate(merges)}
        self.vocab: dict[int, bytes] = {i: bytes([i]) for i in range(256)}
        for rank, (a, b) in enumerate(merges):
            self.vocab[256 + rank] = self.vocab[a] + self.vocab[b]
        self.eot = 256 + len(merges)
        self._cache: dict[str, list[int]] = {}

    @property
    def vocab_size(self) -> int:
        return self.eot + 1

    def _encode_word(self, word: str) -> list[int]:
        cached = self._cache.get(word)
        if cached is not None:
            return cached
        ids = list(word.encode("utf-8"))
        # Apply the earliest learned merge first, as in training, until none applies.
        while len(ids) > 1:
            pair = min(
                itertools.pairwise(ids),
                key=lambda p: self.ranks.get(p, len(self.ranks)),
            )
            if pair not in self.ranks:
                break
            ids = _merge(ids, pair, 256 + self.ranks[pair])
        self._cache[word] = ids
        return ids

    def encode(self, text: str) -> list[int]:
        out: list[int] = []
        for i, part in enumerate(text.split(EOT)):
            if i:
                out.append(self.eot)
            for word in PATTERN.findall(part):
                out.extend(self._encode_word(word))
        return out

    def decode(self, ids: list[int]) -> str:
        pieces = [EOT.encode() if i == self.eot else self.vocab[i] for i in ids]
        return b"".join(pieces).decode("utf-8", errors="replace")

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"merges": self.merges}))

    @classmethod
    def load(cls, path: Path) -> "Tokenizer":
        return cls([(a, b) for a, b in json.loads(path.read_text())["merges"]])


def _merge(ids: list[int], pair: Pair, new: int) -> list[int]:
    out: list[int] = []
    i = 0
    while i < len(ids):
        if i + 1 < len(ids) and (ids[i], ids[i + 1]) == pair:
            out.append(new)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out


def train(text: str, vocab_size: int) -> Tokenizer:
    """Learn vocab_size - 257 merges (256 bytes and the end-of-text token are given)."""
    if vocab_size < 257:
        raise ValueError("vocab_size must be at least 257")
    counts = Counter(word for part in text.split(EOT) for word in PATTERN.findall(part))
    words = [list(w.encode("utf-8")) for w in counts]
    freqs = list(counts.values())
    # Pair counts, and which words contain each pair, so a merge only revisits the words it changes.
    pair_counts: Counter[Pair] = Counter()
    where: defaultdict[Pair, set[int]] = defaultdict(set)
    for w, ids in enumerate(words):
        for pair in itertools.pairwise(ids):
            pair_counts[pair] += freqs[w]
            where[pair].add(w)
    merges: list[Pair] = []
    while len(merges) < vocab_size - 257 and pair_counts:
        # Most frequent pair; ties go to the larger pair so training is deterministic.
        best = max(pair_counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
        new = 256 + len(merges)
        merges.append(best)
        for w in where.pop(best):
            old = words[w]
            for pair in itertools.pairwise(old):
                pair_counts[pair] -= freqs[w]
                if pair_counts[pair] <= 0:
                    del pair_counts[pair]
            words[w] = _merge(old, best, new)
            for pair in zip(words[w], words[w][1:], strict=False):
                pair_counts[pair] += freqs[w]
                where[pair].add(w)
    return Tokenizer(merges)


def main() -> None:
    from llm_from_scratch import data

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--vocab-size", type=int, default=2048)
    args = parser.parse_args()
    train_stories, _ = data.load()
    tok = train(EOT.join(train_stories), args.vocab_size)
    sample = train_stories[0][:200]
    ids = tok.encode(sample)
    print(
        f"vocabulary: {tok.vocab_size} tokens; the last merges: {[tok.vocab[i] for i in range(tok.eot - 5, tok.eot)]}"
    )
    print(f"{len(sample.encode())} bytes became {len(ids)} tokens:")
    print(" | ".join(tok.decode([i]) for i in ids))


if __name__ == "__main__":
    main()
