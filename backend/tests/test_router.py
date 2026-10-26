from conftest import FakeGateway, route_json

from orin.gateway import ProviderError
from orin.registry import MUSE_IMAGE, MUSE_SPARK, MUSE_SPARK_OPEN
from orin.router import route, schema

ALL = [MUSE_SPARK, MUSE_SPARK_OPEN, MUSE_IMAGE]


async def test_valid_decision_is_used(gateway: FakeGateway):
    gateway.route_reply = route_json(
        MUSE_SPARK_OPEN, [(MUSE_SPARK_OPEN, "summarize")], "short task"
    )

    decision = await route(gateway, "summarize this", "", ALL)

    assert decision.target == MUSE_SPARK_OPEN
    assert decision.reason == "short task"
    assert decision.routed_by == "router"


async def test_image_plan_with_prompt_writer_is_valid(gateway: FakeGateway):
    gateway.route_reply = route_json(
        MUSE_IMAGE, [(MUSE_SPARK, "write a prompt"), (MUSE_IMAGE, "draw it")]
    )

    decision = await route(gateway, "make a banner", "", ALL)

    assert [step.target for step in decision.steps] == [MUSE_SPARK, MUSE_IMAGE]


async def test_image_model_first_falls_back_to_default(gateway: FakeGateway):
    gateway.route_reply = route_json(MUSE_IMAGE, [(MUSE_IMAGE, "draw")])

    decision = await route(gateway, "make a banner", "", ALL)

    assert decision.routed_by == "default"
    assert decision.target == MUSE_SPARK


async def test_unavailable_target_falls_back_to_default(gateway: FakeGateway):
    gateway.route_reply = route_json(MUSE_SPARK_OPEN, [(MUSE_SPARK_OPEN, "answer")])

    decision = await route(gateway, "hi", "", [MUSE_SPARK])

    assert decision.routed_by == "default"


async def test_router_outage_falls_back_to_default(gateway: FakeGateway):
    gateway.route_reply = ProviderError("rate_limited", "HTTP 429", 429)

    decision = await route(gateway, "hi", "", ALL)

    assert decision.routed_by == "default"
    assert decision.steps[0].instruction == "hi"
    assert "unavailable" in decision.reason


async def test_unreadable_answer_falls_back_to_default(gateway: FakeGateway):
    gateway.route_reply = "not json"

    decision = await route(gateway, "hi", "", ALL)

    assert decision.routed_by == "default"


async def test_context_reaches_the_router(gateway: FakeGateway):
    await route(gateway, "when is my launch?", "User: launch is Friday", ALL)

    assert "launch is Friday" in gateway.route_prompts[0]


def test_schema_only_allows_the_given_targets():
    targets = schema([MUSE_SPARK])["properties"]["target"]

    assert targets["enum"] == [MUSE_SPARK]
