"""Runs one scenario end-to-end against a fresh seeded DB and checks its
expectations: state assertions (DB rows), event assertions (tools called,
policy outcomes), and answer assertions (substrings)."""

from dataclasses import dataclass, field

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import agent
from app.db import Base
from app.models import Customer, Escalation, Event, Refund
from data.seed import seed_domain, seed_kb
from evals.fixtures import seed_eval_extras
from evals.scenarios import Scenario


@dataclass
class ScenarioResult:
    scenario_id: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    answer: str | None = None
    tools_called: list[str] = field(default_factory=list)


def _fresh_seeded_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    seed_eval_extras(session)
    return session


def run_scenario(scenario: Scenario, llm_complete, session=None, customer_id=None) -> ScenarioResult:
    owns_session = session is None
    if owns_session:
        session = _fresh_seeded_session()

    if customer_id is None:
        customer = session.query(Customer).filter_by(email=scenario.persona).one_or_none()
        if customer is None:
            return ScenarioResult(scenario.id, False, [f"unknown persona: {scenario.persona}"])
        customer_id = customer.id

    conversation_id = 1
    history: list[dict] = []
    last_result = None
    pending_nonce = None

    try:
        for turn in scenario.turns:
            if "user" in turn:
                last_result = agent.run_turn(
                    session, customer_id, conversation_id, history, turn["user"], llm_complete=llm_complete
                )
                history.append({"role": "user", "content": turn["user"]})
                if last_result.text:
                    history.append({"role": "assistant", "content": last_result.text})
                if last_result.confirmation_request:
                    pending_nonce = last_result.confirmation_request["nonce"]
            elif turn.get("confirm"):
                last_result = agent.confirm_action(session, customer_id, pending_nonce, llm_complete=llm_complete)
                if last_result.text:
                    history.append({"role": "assistant", "content": last_result.text})
    except Exception as exc:  # noqa: BLE001 - a broken API/auth/parsing failure must show up as a scenario failure, not crash the suite
        return ScenarioResult(scenario.id, False, [f"exception during scenario execution: {exc}"])

    # app/agent.py now catches provider/network failures internally and returns
    # a graceful TurnResult(error=...) instead of raising (F-007 fix) — that no
    # longer trips the except block above, so it needs its own check here to
    # keep a broken LLM call showing up as a scenario failure, not a pass.
    if last_result and last_result.error:
        detail_event = (
            session.query(Event)
            .filter_by(conversation_id=conversation_id, type="llm_error")
            .order_by(Event.id.desc())
            .first()
        )
        detail = detail_event.payload.get("detail") if detail_event else None
        message = f"turn returned a typed error: {last_result.error}"
        if detail:
            message += f" ({detail})"
        return ScenarioResult(scenario.id, False, [message])

    tool_events = (
        session.query(Event)
        .filter_by(conversation_id=conversation_id, type="tool_call")
        .order_by(Event.id)
        .all()
    )
    tools_called = [e.payload["tool"] for e in tool_events]

    failures = _check_expectations(session, conversation_id, scenario.expect, last_result, tool_events, tools_called)

    return ScenarioResult(
        scenario_id=scenario.id,
        passed=not failures,
        failures=failures,
        answer=last_result.text if last_result else None,
        tools_called=tools_called,
    )


def _check_expectations(session, conversation_id, expect, last_result, tool_events, tools_called) -> list[str]:
    failures = []

    if "tools_called" in expect:
        missing = [t for t in expect["tools_called"] if t not in tools_called]
        if missing:
            failures.append(
                f"expected tools {expect['tools_called']} to be called; missing {missing} (actual: {tools_called})"
            )

    if "policy_outcome" in expect:
        outcomes = [
            e.payload["outcome"]
            for e in session.query(Event).filter_by(conversation_id=conversation_id, type="policy_decision").all()
        ]
        if expect["policy_outcome"] not in outcomes:
            failures.append(f"expected policy outcome {expect['policy_outcome']!r}; actual outcomes: {outcomes}")

    if "policy_reason" in expect:
        reasons = [
            e.payload["reason"]
            for e in session.query(Event).filter_by(conversation_id=conversation_id, type="policy_decision").all()
        ]
        if expect["policy_reason"] not in reasons:
            failures.append(f"expected policy reason {expect['policy_reason']!r}; actual reasons: {reasons}")

    if "escalation_reason" in expect:
        reasons = [e.reason for e in session.query(Escalation).filter_by(conversation_id=conversation_id).all()]
        if expect["escalation_reason"] not in reasons:
            failures.append(f"expected escalation reason {expect['escalation_reason']!r}; actual: {reasons}")

    for must_not in expect.get("must_not", []):
        if must_not == "refund_created":
            if session.query(Refund).count() > 0:
                failures.append("expected no refund to be created, but one was")
        elif must_not == "address_updated":
            updated = [
                e for e in tool_events if e.payload["tool"] == "update_shipping_address" and "error" not in e.payload["result"]
            ]
            if updated:
                failures.append("expected no address update, but one occurred")
        elif must_not == "escalation_created":
            if session.query(Escalation).filter_by(conversation_id=conversation_id).count() > 0:
                failures.append("expected no escalation, but one was created")

    if expect.get("api_round_trip"):
        if not last_result or not (last_result.text or "").strip():
            failures.append("expected a non-empty real-API answer (api_round_trip check), got none")

    if "answer_contains_any" in expect:
        answer = (last_result.text or "").lower() if last_result else ""
        if not any(s.lower() in answer for s in expect["answer_contains_any"]):
            failures.append(f"expected answer to contain any of {expect['answer_contains_any']}; got: {answer!r}")

    return failures
