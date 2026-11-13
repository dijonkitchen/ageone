import json
from pathlib import Path

import pytest

from llm_from_scratch import data, train
from llm_from_scratch.model import Config


def test_learning_rate_warms_up_then_decays_to_a_tenth() -> None:
    cfg = train.TrainConfig(steps=100, warmup=10, lr=1.0)
    assert train.lr_at(0, cfg) == pytest.approx(0.1)
    assert train.lr_at(9, cfg) == pytest.approx(1.0)
    assert train.lr_at(55, cfg) == pytest.approx(0.55)
    assert train.lr_at(100, cfg) == pytest.approx(0.1)


def test_a_tiny_run_is_recorded_and_reproducible(
    stories: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        data, "load", lambda seed, val_fraction: data.split(stories, val_fraction, seed)
    )
    model_cfg = Config(vocab_size=300, context=16, layers=1, heads=2, dim=16)
    cfg = train.TrainConfig(
        steps=20, batch=4, warmup=5, eval_every=10, eval_batches=2, bpb_stories=2
    )
    first = train.train(model_cfg, cfg, tmp_path / "a", val_fraction=0.2)
    second = train.train(model_cfg, cfg, tmp_path / "b", val_fraction=0.2)
    assert first["history"][-1]["val_loss"] < first["history"][0]["val_loss"]
    for key in ("history", "val_bits_per_byte", "samples"):
        strip = (
            (lambda h: [{k: v for k, v in p.items() if k != "minutes"} for p in h])
            if key == "history"
            else (lambda v: v)
        )
        assert strip(first[key]) == strip(second[key])
    record = json.loads((tmp_path / "a" / "run.json").read_text())
    assert record["dataset"]["sha256"] == data.SHA256
    assert record["model"]["vocab_size"] == 300
    model, tok, loaded = train.load_run(tmp_path / "a")
    assert tok.vocab_size == 300 and loaded["seed"] == 0
    assert model.parameters_count() == record["parameters"]
