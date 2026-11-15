import math

import pytest
import torch
from torch.nn import functional as F

from llm_from_scratch.evaluate import bits_per_byte, nll
from llm_from_scratch.model import GPT, Config


def test_sliding_windows_match_one_pass_when_the_text_fits() -> None:
    torch.manual_seed(0)
    model = GPT(Config(vocab_size=30, context=32, layers=1, heads=1, dim=8)).eval()
    ids = torch.randint(0, 30, (20,)).tolist()
    full = F.cross_entropy(
        model(torch.tensor([ids[:-1]]))[0], torch.tensor(ids[1:]), reduction="sum"
    ).item()
    assert nll(model, ids, context=32, stride=5) == pytest.approx(full, rel=1e-5)


def test_every_token_is_scored_once_with_a_short_context() -> None:
    def uniform(ids: torch.Tensor) -> torch.Tensor:
        return torch.zeros(*ids.shape, 8)

    assert nll(
        uniform, [i % 8 for i in range(100)], context=4, stride=3
    ) == pytest.approx(99 * math.log(8))


def test_bits_per_byte_of_a_uniform_byte_model_is_eight() -> None:
    def uniform(ids: torch.Tensor) -> torch.Tensor:
        return torch.zeros(*ids.shape, 256)

    texts = ["hello there", "a much longer story about a cat " * 10]
    assert bits_per_byte(
        uniform, lambda t: list(t.encode()), 0, texts, context=16
    ) == pytest.approx(8.0)
