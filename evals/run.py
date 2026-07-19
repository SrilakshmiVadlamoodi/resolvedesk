"""CLI: python -m evals.run [--subset smoke]

Runs real LLM calls (requires ANTHROPIC_API_KEY) — see docs/specs/features/
2026-07-06-f6-eval-suite/spec.md for scenario format and scoring.
"""

import argparse
import sys

from evals.suite import run_suite, write_report

_SMOKE_PASS_THRESHOLD = 1.0
_FULL_PASS_THRESHOLD = 0.90


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ResolveDesk eval scenarios.")
    parser.add_argument("--subset", choices=["smoke"], default=None, help="Run only the smoke subset.")
    args = parser.parse_args(argv)

    suite_result = run_suite(subset=args.subset)
    write_report(suite_result)

    total = len(suite_result.results)
    passed = sum(1 for r in suite_result.results if r.passed)
    print(f"{passed}/{total} scenarios passed ({suite_result.pass_rate:.1%}). Report: evals/report.md")

    threshold = _SMOKE_PASS_THRESHOLD if args.subset == "smoke" else _FULL_PASS_THRESHOLD
    return 0 if suite_result.pass_rate >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
