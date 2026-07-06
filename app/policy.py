"""Policy engine. The LLM proposes actions; these pure functions dispose them."""

from dataclasses import dataclass


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
