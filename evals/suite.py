"""Runs every scenario in a directory and renders a markdown report."""

from dataclasses import dataclass, field
from pathlib import Path

from app import llm
from evals.runner import ScenarioResult, run_scenario
from evals.scenarios import SCENARIOS_DIR, load_scenarios

REPORT_PATH = Path(__file__).parent / "report.md"


@dataclass
class SuiteResult:
    results: list[ScenarioResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)


def run_suite(
    subset: str | None = None,
    scenarios_dir: Path = SCENARIOS_DIR,
    llm_complete_factory=None,
) -> SuiteResult:
    """Run every matching scenario against a fresh seeded DB each. A new
    llm_complete is requested per scenario (default: the real Anthropic call)
    so scenarios never share iterator/call state."""
    llm_complete_factory = llm_complete_factory or (lambda _scenario_id: llm.complete)

    scenarios = load_scenarios(scenarios_dir=scenarios_dir, subset=subset)
    results = [run_scenario(s, llm_complete=llm_complete_factory(s.id)) for s in scenarios]
    return SuiteResult(results=results)


def render_report(suite_result) -> str:
    total = len(suite_result.results)
    passed = sum(1 for r in suite_result.results if r.passed)
    lines = [
        "# Eval Report",
        "",
        f"**Pass rate: {suite_result.pass_rate:.1%} ({passed}/{total})**",
        "",
        "| Scenario | Result |",
        "|---|---|",
    ]
    for r in suite_result.results:
        lines.append(f"| {r.scenario_id} | {'PASS' if r.passed else 'FAIL'} |")

    failures = [r for r in suite_result.results if not r.passed]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            lines.append(f"### {r.scenario_id}")
            lines.append(f"- Answer: {r.answer!r}")
            lines.append(f"- Tools called: {r.tools_called}")
            for failure in r.failures:
                lines.append(f"- {failure}")
            lines.append("")

    return "\n".join(lines)


def write_report(suite_result, path: Path = REPORT_PATH) -> None:
    path.write_text(render_report(suite_result), encoding="utf-8")
