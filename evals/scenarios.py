"""Eval scenario schema and loader — evals/scenarios/*.yaml."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


@dataclass
class Scenario:
    id: str
    persona: str
    turns: list[dict] = field(default_factory=list)
    expect: dict = field(default_factory=dict)
    smoke: bool = False


def load_scenarios(scenarios_dir: Path = SCENARIOS_DIR, subset: str | None = None) -> list[Scenario]:
    scenarios = []
    for path in sorted(scenarios_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        scenarios.append(
            Scenario(
                id=data["id"],
                persona=data["persona"],
                turns=data.get("turns", []),
                expect=data.get("expect", {}),
                smoke=data.get("smoke", False),
            )
        )

    scenarios.sort(key=lambda s: s.id)

    if subset == "smoke":
        scenarios = [s for s in scenarios if s.smoke]

    return scenarios
