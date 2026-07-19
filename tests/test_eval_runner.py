from app.llm import LLMResponse
from evals.runner import run_scenario
from evals.scenarios import Scenario


def fake_llm(*responses):
    it = iter(responses)

    def _complete(messages, tools=None, tool_choice=None):
        return next(it)

    return _complete


def test_happy_path_scenario_passes():
    scenario = Scenario(
        id="happy-01",
        persona="aditi@example.com",
        turns=[{"user": "Where is my order?"}],
        expect={"tools_called": ["get_customer_orders"], "answer_contains_any": ["shipped", "delivered"]},
    )
    llm = fake_llm(
        LLMResponse(content=None, tool_calls=[{"id": "1", "name": "get_customer_orders", "arguments": {}}]),
        LLMResponse(content="Your VoltWatch Fit order is currently shipped.", tool_calls=[]),
    )

    result = run_scenario(scenario, llm_complete=llm)

    assert result.passed is True, result.failures
    assert result.tools_called == ["get_customer_orders"]


def test_scenario_fails_when_expected_tool_not_called():
    scenario = Scenario(
        id="wrong-tool",
        persona="aditi@example.com",
        turns=[{"user": "Where is my order?"}],
        expect={"tools_called": ["get_order_details"]},
    )
    llm = fake_llm(
        LLMResponse(content=None, tool_calls=[{"id": "1", "name": "get_customer_orders", "arguments": {}}]),
        LLMResponse(content="You have orders.", tool_calls=[]),
    )

    result = run_scenario(scenario, llm_complete=llm)

    assert result.passed is False
    assert any("get_order_details" in f for f in result.failures)


def test_must_not_refund_created_fails_when_a_refund_happens():
    scenario = Scenario(
        id="no-refund-expected",
        persona="aditi@example.com",
        turns=[{"user": "refund my order please"}, {"confirm": True}],
        expect={"must_not": ["refund_created"]},
    )
    import app.rag  # noqa: F401  (ensure module import order doesn't matter)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db import Base
    from data.seed import seed_domain, seed_kb

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    from app.models import Customer, Order

    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    llm = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "initiate_refund", "arguments": {"order_id": order.id, "amount": 2999, "reason": "x"}}],
        ),
        LLMResponse(content="Your refund is on its way.", tool_calls=[]),
    )

    result = run_scenario(scenario, llm_complete=llm, session=session, customer_id=aditi.id)

    assert result.passed is False
    assert any("refund" in f.lower() for f in result.failures)


def test_policy_outcome_and_escalation_reason_checked():
    scenario = Scenario(
        id="over-limit",
        persona="aditi@example.com",
        turns=[{"user": "refund my ₹8,499 order"}],
        expect={"policy_outcome": "ESCALATE", "escalation_reason": "OVER_LIMIT", "must_not": ["refund_created"]},
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db import Base
    from data.seed import seed_domain, seed_kb

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    from app.models import Customer, Order

    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    llm = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "initiate_refund", "arguments": {"order_id": order.id, "amount": 8499, "reason": "x"}}],
        ),
        LLMResponse(content='{"summary": "s", "sentiment": "frustrated", "suggested_action": "review"}', tool_calls=[]),
        LLMResponse(content="refund", tool_calls=[]),
    )

    result = run_scenario(scenario, llm_complete=llm, session=session, customer_id=aditi.id)

    assert result.passed is True, result.failures


def test_pending_confirmation_survives_an_unrelated_turn_in_between():
    scenario = Scenario(
        id="interjection",
        persona="aditi@example.com",
        turns=[
            {"user": "refund my order please"},
            {"user": "actually wait, what's your warranty policy?"},
            {"confirm": True},
        ],
        expect={"must_not": []},
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db import Base
    from data.seed import seed_domain, seed_kb

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    from app.models import Customer, Order, Refund

    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    order = session.query(Order).filter_by(customer_id=aditi.id, status="delivered").one()

    llm = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "initiate_refund", "arguments": {"order_id": order.id, "amount": 2999, "reason": "x"}}],
        ),
        LLMResponse(content="Our warranty covers manufacturing defects for 12-18 months.", tool_calls=[]),
        LLMResponse(content="Your refund is on its way.", tool_calls=[]),
    )

    result = run_scenario(scenario, llm_complete=llm, session=session, customer_id=aditi.id)

    assert result.passed is True, result.failures
    assert session.query(Refund).count() == 1


def test_policy_reason_checked_against_policy_decision_events_for_deny_outcomes():
    scenario = Scenario(
        id="deny-shipped",
        persona="aditi@example.com",
        turns=[{"user": "please update my shipping address, my order has already shipped"}],
        expect={"policy_outcome": "DENY", "policy_reason": "ALREADY_SHIPPED"},
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db import Base
    from data.seed import seed_domain, seed_kb

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    from app.models import Customer, Order

    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    shipped_order = session.query(Order).filter_by(customer_id=aditi.id, status="shipped").one()

    llm = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[
                {"id": "1", "name": "update_shipping_address", "arguments": {"order_id": shipped_order.id, "new_address": "new address"}}
            ],
        ),
        LLMResponse(content="I'm sorry, that order has already shipped.", tool_calls=[]),
    )

    result = run_scenario(scenario, llm_complete=llm, session=session, customer_id=aditi.id)

    assert result.passed is True, result.failures


def test_policy_reason_check_fails_when_actual_reason_differs():
    scenario = Scenario(
        id="deny-shipped-wrong-expectation",
        persona="aditi@example.com",
        turns=[{"user": "please update my shipping address, my order has already shipped"}],
        expect={"policy_reason": "SOME_OTHER_REASON"},
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db import Base
    from data.seed import seed_domain, seed_kb

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_kb(session)
    seed_domain(session)
    from app.models import Customer, Order

    aditi = session.query(Customer).filter_by(email="aditi@example.com").one()
    shipped_order = session.query(Order).filter_by(customer_id=aditi.id, status="shipped").one()

    llm = fake_llm(
        LLMResponse(
            content=None,
            tool_calls=[
                {"id": "1", "name": "update_shipping_address", "arguments": {"order_id": shipped_order.id, "new_address": "new address"}}
            ],
        ),
        LLMResponse(content="I'm sorry, that order has already shipped.", tool_calls=[]),
    )

    result = run_scenario(scenario, llm_complete=llm, session=session, customer_id=aditi.id)

    assert result.passed is False
    assert any("SOME_OTHER_REASON" in f for f in result.failures)


def test_an_exception_from_llm_complete_is_recorded_as_a_failure_not_raised():
    scenario = Scenario(id="broken-api", persona="aditi@example.com", turns=[{"user": "hi"}], expect={})

    def broken_llm(messages, tools=None, tool_choice=None):
        raise RuntimeError("401 unauthorized")

    result = run_scenario(scenario, llm_complete=broken_llm)

    assert result.passed is False
    assert any("401 unauthorized" in f for f in result.failures)


def test_api_round_trip_check_passes_when_a_non_empty_answer_comes_back():
    scenario = Scenario(
        id="round-trip",
        persona="aditi@example.com",
        turns=[{"user": "hello"}],
        expect={"api_round_trip": True},
    )
    llm = fake_llm(LLMResponse(content="Hi there, how can I help?", tool_calls=[]))

    result = run_scenario(scenario, llm_complete=llm)

    assert result.passed is True, result.failures


def test_api_round_trip_check_fails_on_empty_answer():
    scenario = Scenario(
        id="round-trip-empty",
        persona="aditi@example.com",
        turns=[{"user": "hello"}],
        expect={"api_round_trip": True},
    )
    llm = fake_llm(LLMResponse(content="", tool_calls=[]))

    result = run_scenario(scenario, llm_complete=llm)

    assert result.passed is False


def test_unknown_persona_fails_gracefully():
    scenario = Scenario(id="bad-persona", persona="nobody@example.com", turns=[], expect={})

    result = run_scenario(scenario, llm_complete=fake_llm())

    assert result.passed is False
    assert any("persona" in f.lower() for f in result.failures)
