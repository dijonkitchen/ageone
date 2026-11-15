import math

import pytest
import torch

from llm_from_scratch.model import GPT, Config

TINY = Config(vocab_size=50, context=16, layers=2, heads=2, dim=16)


def test_logits_have_one_score_per_vocabulary_entry() -> None:
    torch.manual_seed(0)
    assert GPT(TINY)(torch.randint(0, 50, (3, 10))).shape == (3, 10, 50)


def test_a_position_never_sees_the_future() -> None:
    torch.manual_seed(0)
    model = GPT(TINY).eval()
    ids = torch.randint(0, 50, (1, 12))
    changed = ids.clone()
    changed[0, 8:] = (changed[0, 8:] + 1) % 50
    assert torch.allclose(model(ids)[0, :8], model(changed)[0, :8])
    assert not torch.allclose(model(ids)[0, 8:], model(changed)[0, 8:])


def test_an_untrained_model_guesses_uniformly() -> None:
    torch.manual_seed(0)
    ids = torch.randint(0, 50, (4, 16))
    assert GPT(TINY).loss(ids[:, :-1], ids[:, 1:]).item() == pytest.approx(
        math.log(50), rel=0.05
    )


def test_rejects_sequences_longer_than_the_context() -> None:
    with pytest.raises(ValueError, match="context"):
        GPT(TINY)(torch.zeros(1, 17, dtype=torch.long))


def test_learns_to_repeat_a_sequence() -> None:
    torch.manual_seed(0)
    model = GPT(TINY)
    ids = torch.arange(17).unsqueeze(0) % 7
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-2)
    for _ in range(100):
        loss = model.loss(ids[:, :-1], ids[:, 1:])
        optimizer.zero_grad()
        loss.backward()  # type: ignore[no-untyped-call]
        optimizer.step()
    assert loss.item() < 0.1
    out = model.eval().generate(ids[:, :8], 8, temperature=0.01)
    assert out[0, 8:].tolist() == ids[0, 8:16].tolist()


def test_generation_stops_at_the_stop_token_and_slides_past_the_context() -> None:
    torch.manual_seed(0)
    model = GPT(TINY).eval()
    gen = torch.Generator().manual_seed(0)
    long = model.generate(torch.zeros(1, 1, dtype=torch.long), 40, generator=gen)
    assert long.shape == (1, 41)
    first = int(
        model.generate(
            torch.zeros(1, 1, dtype=torch.long),
            1,
            generator=torch.Generator().manual_seed(1),
        )[0, 1]
    )
    short = model.generate(
        torch.zeros(1, 1, dtype=torch.long),
        40,
        stop=first,
        generator=torch.Generator().manual_seed(1),
    )
    assert short.shape == (1, 2)
