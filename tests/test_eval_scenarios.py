from pathlib import Path

from evals.scenarios import Scenario, load_scenarios


def _write(dir_path: Path, filename: str, content: str) -> None:
    (dir_path / filename).write_text(content, encoding="utf-8")


def test_loads_a_single_scenario(tmp_path):
    _write(
        tmp_path,
        "happy-01.yaml",
        """
id: happy-01
persona: aditi@example.com
turns:
  - user: "Where is my order?"
expect:
  tools_called: [get_customer_orders]
  answer_contains_any: ["shipped", "delivered"]
""",
    )

    scenarios = load_scenarios(scenarios_dir=tmp_path)

    assert len(scenarios) == 1
    assert isinstance(scenarios[0], Scenario)
    assert scenarios[0].id == "happy-01"
    assert scenarios[0].persona == "aditi@example.com"
    assert scenarios[0].turns == [{"user": "Where is my order?"}]
    assert scenarios[0].expect["tools_called"] == ["get_customer_orders"]
    assert scenarios[0].smoke is False


def test_loads_multiple_scenarios_sorted_by_id(tmp_path):
    _write(tmp_path, "b.yaml", "id: b-scenario\npersona: aditi@example.com\nturns: []\nexpect: {}\n")
    _write(tmp_path, "a.yaml", "id: a-scenario\npersona: aditi@example.com\nturns: []\nexpect: {}\n")

    scenarios = load_scenarios(scenarios_dir=tmp_path)

    assert [s.id for s in scenarios] == ["a-scenario", "b-scenario"]


def test_smoke_subset_filters_to_tagged_scenarios(tmp_path):
    _write(tmp_path, "s1.yaml", "id: s1\npersona: aditi@example.com\nturns: []\nexpect: {}\nsmoke: true\n")
    _write(tmp_path, "s2.yaml", "id: s2\npersona: aditi@example.com\nturns: []\nexpect: {}\n")

    all_scenarios = load_scenarios(scenarios_dir=tmp_path)
    smoke_scenarios = load_scenarios(scenarios_dir=tmp_path, subset="smoke")

    assert len(all_scenarios) == 2
    assert [s.id for s in smoke_scenarios] == ["s1"]


def test_multi_turn_scenario_with_confirm_step(tmp_path):
    _write(
        tmp_path,
        "confirm.yaml",
        """
id: confirm-01
persona: aditi@example.com
turns:
  - user: "refund my order"
  - confirm: true
expect:
  answer_contains_any: ["refund"]
""",
    )

    scenarios = load_scenarios(scenarios_dir=tmp_path)

    assert scenarios[0].turns == [{"user": "refund my order"}, {"confirm": True}]
