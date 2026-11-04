"""Step 3: the model, a GPT-style decoder-only transformer (Radford et al., 2019).

Each token id looks up a learned vector (its embedding), and each position adds another, so the model
knows both what a token is and where it is. A stack of identical blocks then refines those vectors:

- Causal self-attention lets each position gather information from earlier positions only. Every vector
  is projected into a query, a key, and a value; a position's output is the average of earlier values,
  weighted by how well its query matches their keys. Several heads do this in parallel on slices of the
  vector, so they can attend to different things (the subject, the last word, the opening quote).
- A two-layer MLP then transforms each position on its own.

Both sublayers add their output back to their input (a residual connection) after a layer norm, which
keeps training stable as blocks stack up. Finally the vectors are projected back onto the vocabulary to
give a score (logit) for every possible next token. The output projection shares its weights with the
token embedding, which saves parameters and helps small models.

Attention is written out by hand rather than with torch's fused kernel so every step is visible.
"""

import math
from dataclasses import asdict, dataclass

import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True)
class Config:
    vocab_size: int = 2048
    context: int = 256
    layers: int = 6
    heads: int = 4
    dim: int = 128
    dropout: float = 0.0

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


class CausalSelfAttention(nn.Module):
    mask: torch.Tensor

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        if cfg.dim % cfg.heads:
            raise ValueError("dim must be divisible by heads")
        self.heads = cfg.heads
        self.qkv = nn.Linear(cfg.dim, 3 * cfg.dim)
        self.proj = nn.Linear(cfg.dim, cfg.dim)
        self.dropout = nn.Dropout(cfg.dropout)
        # mask[i, j] is True where position i may not look at position j (j is in the future).
        mask = torch.triu(
            torch.ones(cfg.context, cfg.context, dtype=torch.bool), diagonal=1
        )
        self.register_buffer("mask", mask, persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch, time, dim = x.shape
        q, k, v = self.qkv(x).split(dim, dim=2)
        # (batch, time, dim) -> (batch, heads, time, head_dim): each head works on its own slice.
        q, k, v = (
            t.view(batch, time, self.heads, dim // self.heads).transpose(1, 2)
            for t in (q, k, v)
        )
        # Scaled dot products: dividing by sqrt(head_dim) keeps the softmax from saturating.
        scores = q @ k.transpose(-2, -1) / math.sqrt(k.size(-1))
        scores = scores.masked_fill(self.mask[:time, :time], float("-inf"))
        weights = self.dropout(F.softmax(scores, dim=-1))
        out = (weights @ v).transpose(1, 2).contiguous().view(batch, time, dim)
        return self.dropout(self.proj(out))  # type: ignore[no-any-return]


class Block(nn.Module):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.dim)
        self.attn = CausalSelfAttention(cfg)
        self.ln2 = nn.LayerNorm(cfg.dim)
        self.mlp = nn.Sequential(
            nn.Linear(cfg.dim, 4 * cfg.dim),
            nn.GELU(),
            nn.Linear(4 * cfg.dim, cfg.dim),
            nn.Dropout(cfg.dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        return x + self.mlp(self.ln2(x))  # type: ignore[no-any-return]


class GPT(nn.Module):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.tok = nn.Embedding(cfg.vocab_size, cfg.dim)
        self.pos = nn.Embedding(cfg.context, cfg.dim)
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList(Block(cfg) for _ in range(cfg.layers))
        self.ln = nn.LayerNorm(cfg.dim)
        self.head = nn.Linear(cfg.dim, cfg.vocab_size, bias=False)
        self.head.weight = self.tok.weight  # weight tying
        self.apply(_init)
        # GPT-2's trick: scale the projections that feed the residual stream by depth.
        for name, p in self.named_parameters():
            if name.endswith(("proj.weight", "mlp.2.weight")):
                nn.init.normal_(p, std=0.02 / math.sqrt(2 * cfg.layers))

    def parameters_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        """Logits of shape (batch, time, vocab) for ids of shape (batch, time)."""
        time = ids.size(1)
        if time > self.cfg.context:
            raise ValueError(
                f"sequence of {time} tokens is longer than the context of {self.cfg.context}"
            )
        positions = torch.arange(time, device=ids.device)
        x = self.drop(self.tok(ids) + self.pos(positions))
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln(x))  # type: ignore[no-any-return]

    def loss(self, ids: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Mean cross-entropy of predicting each target token (natural log, per token)."""
        logits = self(ids)
        return F.cross_entropy(logits.view(-1, logits.size(-1)), targets.reshape(-1))

    @torch.no_grad()
    def generate(
        self,
        ids: torch.Tensor,
        new_tokens: int,
        temperature: float = 0.8,
        top_k: int | None = 40,
        stop: int | None = None,
        generator: torch.Generator | None = None,
    ) -> torch.Tensor:
        """Sample one token at a time, feeding each back in; the window slides once the context is full."""
        for _ in range(new_tokens):
            logits = self(ids[:, -self.cfg.context :])[:, -1, :] / max(
                temperature, 1e-6
            )
            if top_k is not None:
                kth = torch.topk(logits, min(top_k, logits.size(-1))).values[:, -1:]
                logits = logits.masked_fill(logits < kth, float("-inf"))
            nxt = torch.multinomial(F.softmax(logits, dim=-1), 1, generator=generator)
            ids = torch.cat([ids, nxt], dim=1)
            if stop is not None and bool((nxt == stop).all()):
                break
        return ids


def _init(module: nn.Module) -> None:
    if isinstance(module, nn.Linear):
        nn.init.normal_(module.weight, std=0.02)
        if module.bias is not None:
            nn.init.zeros_(module.bias)
    elif isinstance(module, nn.Embedding):
        nn.init.normal_(module.weight, std=0.02)
