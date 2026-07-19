from app.llm import LLMResponse
from evals.runner import ScenarioResult
from evals.suite import render_report, run_suite, write_report


def _write(dir_path, filename, content):
    (dir_path / filename).write_text(content, encoding="utf-8")


def test_run_suite_runs_every_scenario_and_aggregates_pass_rate(tmp_path):
    _write(
        tmp_path,
        "a.yaml",
        "id: a\npersona: aditi@example.com\nturns:\n  - user: \"hi\"\nexpect: {}\n",
    )
    _write(
        tmp_path,
        "b.yaml",
        "id: b\npersona: aditi@example.com\nturns:\n  - user: \"hi\"\nexpect:\n  answer_contains_any: [\"never going to match\"]\n",
    )

    responses = {
        "a": [LLMResponse(content="Hello!", tool_calls=[])],
        "b": [LLMResponse(content="Hello!", tool_calls=[])],
    }

    def factory(scenario_id):
        it = iter(responses[scenario_id])

        def _complete(messages, tools=None, tool_choice=None):
            return next(it)

        return _complete

    suite_result = run_suite(scenarios_dir=tmp_path, llm_complete_factory=factory)

    assert len(suite_result.results) == 2
    assert suite_result.pass_rate == 0.5


def test_render_report_includes_pass_rate_table_and_failure_details():
    results = [
        ScenarioResult(scenario_id="ok", passed=True, failures=[], answer="fine", tools_called=[]),
        ScenarioResult(scenario_id="broken", passed=False, failures=["expected X, got Y"], answer="oops", tools_called=[]),
    ]

    class _Suite:
        def __init__(self, results):
            self.results = results

        @property
        def pass_rate(self):
            return sum(r.passed for r in self.results) / len(self.results)

    report = render_report(_Suite(results))

    assert "50" in report or "0.5" in report
    assert "ok" in report
    assert "broken" in report
    assert "expected X, got Y" in report


def test_write_report_writes_to_disk(tmp_path):
    class _Suite:
        results = [ScenarioResult(scenario_id="ok", passed=True, failures=[], answer="fine", tools_called=[])]
        pass_rate = 1.0

    report_path = tmp_path / "report.md"
    write_report(_Suite(), path=report_path)

    assert report_path.exists()
    assert "ok" in report_path.read_text(encoding="utf-8")
