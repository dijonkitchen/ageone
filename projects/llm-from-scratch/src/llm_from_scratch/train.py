"""Step 4: training.

The whole training set is one long stream of tokens, with the end-of-text token between stories. Each
step samples a batch of windows from random offsets; the target of every position is simply the next
token, so one window of n tokens gives n predictions to learn from.

The optimizer is AdamW (Loshchilov and Hutter, 2019), with weight decay on the weight matrices only.
The learning rate warms up linearly (large early updates on random weights are unstable), then follows
a cosine curve down to a tenth of its peak. Gradients are clipped so one bad batch cannot blow up the run.

Everything that decides the result is recorded in run.json: seeds, the dataset revision and hash, every
hyperparameter, the library versions, and the loss curve. Running the same command again on the same
machine gives the same numbers.
"""

import argparse
import json
import math
import platform
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch

from llm_from_scratch import data, tokenizer
from llm_from_scratch.evaluate import bits_per_byte
from llm_from_scratch.generate import PROMPTS, complete
from llm_from_scratch.model import GPT, Config


@dataclass(frozen=True)
class TrainConfig:
    steps: int = 3000
    batch: int = 32
    lr: float = 3e-3
    warmup: int = 100
    weight_decay: float = 0.1
    clip: float = 1.0
    eval_every: int = 250
    eval_batches: int = 20
    seed: int = 0
    bpb_stories: int = 200


def device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def lr_at(step: int, cfg: TrainConfig) -> float:
    if step < cfg.warmup:
        return cfg.lr * (step + 1) / cfg.warmup
    progress = (step - cfg.warmup) / max(1, cfg.steps - cfg.warmup)
    return cfg.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(1.0, progress))))


def batch(
    stream: torch.Tensor, size: int, context: int, generator: torch.Generator
) -> tuple[torch.Tensor, torch.Tensor]:
    starts = torch.randint(0, len(stream) - context - 1, (size,), generator=generator)
    x = torch.stack([stream[s : s + context] for s in starts.tolist()])
    y = torch.stack([stream[s + 1 : s + context + 1] for s in starts.tolist()])
    return x, y


@torch.no_grad()
def val_loss(
    model: GPT, stream: torch.Tensor, batches: int, size: int, dev: torch.device
) -> float:
    """Mean loss on the same fixed windows every time, so points on the curve are comparable."""
    model.eval()
    context = model.cfg.context
    generator = torch.Generator().manual_seed(1234)
    losses = []
    for _ in range(batches):
        x, y = batch(stream, size, context, generator)
        losses.append(model.loss(x.to(dev), y.to(dev)).item())
    model.train()
    return sum(losses) / len(losses)


def train(
    model_cfg: Config, cfg: TrainConfig, out: Path, val_fraction: float = 0.05
) -> dict[str, Any]:
    random.seed(cfg.seed)
    torch.manual_seed(cfg.seed)
    dev = device()
    out.mkdir(parents=True, exist_ok=True)
    began = time.time()

    train_stories, val_stories = data.load(cfg.seed, val_fraction)
    tok = tokenizer.train(data.EOT.join(train_stories), model_cfg.vocab_size)
    tok.save(out / "tokenizer.json")
    joined = data.EOT + data.EOT.join(train_stories) + data.EOT
    train_stream = torch.tensor(tok.encode(joined))
    val_stream = torch.tensor(
        tok.encode(data.EOT + data.EOT.join(val_stories) + data.EOT)
    )
    tokenized = time.time() - began
    print(
        f"tokenized in {tokenized:.0f}s: {len(train_stream):,} train and {len(val_stream):,} validation tokens"
    )

    model = GPT(model_cfg).to(dev)
    decay = [p for p in model.parameters() if p.dim() >= 2]
    no_decay = [p for p in model.parameters() if p.dim() < 2]
    optimizer = torch.optim.AdamW(
        [
            {"params": decay, "weight_decay": cfg.weight_decay},
            {"params": no_decay, "weight_decay": 0.0},
        ],
        lr=cfg.lr,
        betas=(0.9, 0.95),
    )
    generator = torch.Generator().manual_seed(cfg.seed)
    history: list[dict[str, float]] = []
    print(f"{model.parameters_count():,} parameters on {dev}")
    for step in range(cfg.steps + 1):
        if step % cfg.eval_every == 0 or step == cfg.steps:
            point = {
                "step": step,
                "val_loss": round(
                    val_loss(model, val_stream, cfg.eval_batches, cfg.batch, dev), 4
                ),
            }
            point["minutes"] = round((time.time() - began) / 60, 2)
            history.append(point)
            print(json.dumps(point), flush=True)
        if step == cfg.steps:
            break
        for group in optimizer.param_groups:
            group["lr"] = lr_at(step, cfg)
        x, y = batch(train_stream, cfg.batch, model_cfg.context, generator)
        loss = model.loss(x.to(dev), y.to(dev))
        optimizer.zero_grad(set_to_none=True)
        loss.backward()  # type: ignore[no-untyped-call]
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.clip)
        optimizer.step()

    model.cpu().eval()
    torch.save(
        {"config": model_cfg.to_dict(), "state": model.state_dict()}, out / "model.pt"
    )
    bpb = bits_per_byte(
        model, tok.encode, tok.eot, val_stories[: cfg.bpb_stories], model_cfg.context
    )
    samples = [
        {"prompt": p, "seed": cfg.seed, "text": complete(model, tok, p, cfg.seed)}
        for p in PROMPTS
    ]
    record: dict[str, Any] = {
        "seed": cfg.seed,
        "dataset": {
            "url": data.URL,
            "revision": data.REVISION,
            "sha256": data.SHA256,
            "val_fraction": val_fraction,
        },
        "model": model_cfg.to_dict(),
        "train": asdict(cfg),
        "parameters": model.parameters_count(),
        "tokens": {"train": len(train_stream), "val": len(val_stream)},
        "tokens_seen": cfg.steps * cfg.batch * model_cfg.context,
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device": str(dev),
            "machine": platform.machine(),
            "threads": torch.get_num_threads(),
        },
        "history": history,
        "val_bits_per_byte": round(bpb, 4),
        "bpb_stories": cfg.bpb_stories,
        "minutes": round((time.time() - began) / 60, 1),
        "samples": samples,
    }
    (out / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def load_run(run: Path) -> tuple[GPT, tokenizer.Tokenizer, dict[str, Any]]:
    """The trained model, its tokenizer, and its run record."""
    saved = torch.load(run / "model.pt", map_location="cpu", weights_only=True)
    model = GPT(Config(**saved["config"]))
    model.load_state_dict(saved["state"])
    model.eval()
    record: dict[str, Any] = json.loads((run / "run.json").read_text())
    return model, tokenizer.Tokenizer.load(run / "tokenizer.json"), record


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=Path("runs/default"))
    for name, value in [*asdict(Config()).items(), *asdict(TrainConfig()).items()]:
        parser.add_argument(
            f"--{name.replace('_', '-')}", type=type(value), default=value
        )
    args = vars(parser.parse_args())
    model_cfg = Config(**{k: args[k] for k in asdict(Config())})
    train_cfg = TrainConfig(**{k: args[k] for k in asdict(TrainConfig())})
    record = train(model_cfg, train_cfg, args["out"])
    print(
        f"done in {record['minutes']} minutes: {record['val_bits_per_byte']} bits per byte"
    )
    for sample in record["samples"]:
        print(f"\n{sample['text']}")


if __name__ == "__main__":
    main()
