from evals import run as run_module
from evals.suite import SuiteResult
from evals.runner import ScenarioResult


def test_main_returns_zero_when_smoke_subset_fully_passes(monkeypatch, tmp_path):
    result = SuiteResult(results=[ScenarioResult(scenario_id="s1", passed=True, failures=[], answer="ok", tools_called=[])])
    monkeypatch.setattr(run_module, "run_suite", lambda subset=None: result)
    monkeypatch.setattr(run_module, "write_report", lambda suite_result, path=None: None)

    exit_code = run_module.main(["--subset", "smoke"])

    assert exit_code == 0


def test_main_returns_nonzero_when_smoke_subset_has_a_failure(monkeypatch):
    result = SuiteResult(
        results=[
            ScenarioResult(scenario_id="s1", passed=True, failures=[], answer="ok", tools_called=[]),
            ScenarioResult(scenario_id="s2", passed=False, failures=["boom"], answer="oops", tools_called=[]),
        ]
    )
    monkeypatch.setattr(run_module, "run_suite", lambda subset=None: result)
    monkeypatch.setattr(run_module, "write_report", lambda suite_result, path=None: None)

    exit_code = run_module.main(["--subset", "smoke"])

    assert exit_code == 1


def test_main_full_run_returns_zero_at_90_percent_pass_rate(monkeypatch):
    results = [ScenarioResult(scenario_id=f"s{i}", passed=(i != 0), failures=[], answer="ok", tools_called=[]) for i in range(10)]
    result = SuiteResult(results=results)
    monkeypatch.setattr(run_module, "run_suite", lambda subset=None: result)
    monkeypatch.setattr(run_module, "write_report", lambda suite_result, path=None: None)

    exit_code = run_module.main([])

    assert exit_code == 0
