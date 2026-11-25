"""Spend meter: Anthropic tokens and ElevenLabs characters to dollars and credits (M0.5, RUNTIME §spend).

Prices are config, not code. The defaults below are placeholders to be checked against the providers'
price pages before the numbers are trusted (Haiku 5.5 is assumed to cost what Haiku 4.5 did; ElevenLabs
Flash v2.5 is assumed to cost 0.5 credits per character on the Starter plan). Cached phrases cost nothing.
An alert fires once when month-to-date spend passes 70 % of the cap.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TokenPrice:
    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


@dataclass(frozen=True)
class Prices:
    anthropic: Mapping[str, TokenPrice] = field(default_factory=lambda: {
        "claude-haiku-5-5": TokenPrice(1.00, 5.00, 1.25, 0.10),
        "claude-sonnet-5-5": TokenPrice(2.00, 10.00, 2.50, 0.20),   # the deep voice brain and tasks (list price, Nov 2026)
    })
    elevenlabs_credits_per_char: Mapping[str, float] = field(default_factory=lambda: {
        "eleven_flash_v2_5": 0.5,
        "eleven_v4_turbo": 1.0,  # not yet checked against his invoice: counted at the full rate to be safe
    })
    elevenlabs_usd_per_credit: float = 5.0 / 30_000        # Starter: $5 for 30k credits a month
    elevenlabs_monthly_credits: float = 30_000
    monthly_cap_usd: float = 30.0                          # RUNTIME estimate ~$30/month
    alert_fraction: float = 0.70

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Prices:
        kw = dict(data)
        if "anthropic" in kw:
            kw["anthropic"] = {k: TokenPrice(**v) if isinstance(v, Mapping) else v for k, v in kw["anthropic"].items()}
        return cls(**kw)


def _get(usage: Any, name: str) -> int:
    v = usage.get(name) if isinstance(usage, Mapping) else getattr(usage, name, None)
    return int(v or 0)


class SpendMeter:
    def __init__(self, prices: Prices | None = None, on_alert: Callable[[float, float], None] | None = None) -> None:
        self.prices = prices or Prices()
        self._on_alert = on_alert
        self._alerted = False
        self.anthropic_usd = 0.0
        self.elevenlabs_credits = 0.0
        self.tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
        self.characters = 0
        self.cached_phrase_plays = 0

    def record_llm(self, model: str, usage: Any) -> float:
        """Add one Messages API ``usage`` (object or dict). Returns the dollars for this call."""
        price = self.prices.anthropic.get(model)
        if price is None:
            raise KeyError(f"no price configured for model {model!r}")
        counts = {
            "input": _get(usage, "input_tokens"),
            "output": _get(usage, "output_tokens"),
            "cache_write": _get(usage, "cache_creation_input_tokens"),
            "cache_read": _get(usage, "cache_read_input_tokens"),
        }
        for k, v in counts.items():
            self.tokens[k] += v
        usd = (counts["input"] * price.input_per_mtok + counts["output"] * price.output_per_mtok
               + counts["cache_write"] * price.cache_write_per_mtok
               + counts["cache_read"] * price.cache_read_per_mtok) / 1_000_000
        self.anthropic_usd += usd
        self._check()
        return usd

    def record_tts(self, model: str, characters: int) -> float:
        """Add characters sent to ElevenLabs. Returns the credits used."""
        credits = characters * self.prices.elevenlabs_credits_per_char.get(model, 1.0)
        self.characters += characters
        self.elevenlabs_credits += credits
        self._check()
        return credits

    def record_cached_phrase(self) -> None:
        self.cached_phrase_plays += 1

    @property
    def elevenlabs_usd(self) -> float:
        return self.elevenlabs_credits * self.prices.elevenlabs_usd_per_credit

    @property
    def total_usd(self) -> float:
        return self.anthropic_usd + self.elevenlabs_usd

    def _check(self) -> None:
        cap = self.prices.monthly_cap_usd
        if not self._alerted and cap > 0 and self.total_usd >= self.prices.alert_fraction * cap:
            self._alerted = True
            if self._on_alert:
                self._on_alert(self.total_usd, cap)

    def to_metrics(self) -> dict[str, Any]:
        """``spend`` and ``credits`` for contracts/metrics.schema.json."""
        total = self.prices.elevenlabs_monthly_credits
        return {
            "spend": {"claude_usd": round(self.anthropic_usd, 4), "credit_usd": self.prices.monthly_cap_usd},
            "credits": {"elevenlabs_left": max(0.0, round(total - self.elevenlabs_credits, 1)),
                        "elevenlabs_total": total},
        }
