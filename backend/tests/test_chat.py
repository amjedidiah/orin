from conftest import Clock, FakeGateway, collect, of_type, route_json

from orin.chat import Orchestrator, fallback_chain
from orin.gateway import ProviderError
from orin.registry import MUSE_IMAGE, MUSE_SPARK, MUSE_SPARK_OPEN

PAYMENT = ProviderError("payment_required", "HTTP 402", 402)


async def test_answer_streams_through_orin_and_is_stored(orchestrator: Orchestrator):
    events = await collect(orchestrator, "write my launch announcement")

    assert [e["type"] for e in events] == ["route", "step_start", "token", "token", "done"]
    assert of_type(events, "step_start")[0]["served_by"] == "Meta Model API"
    [stored] = await orchestrator.store.recent_conversations(10)
    assert stored.prompt == "write my launch announcement"
    assert stored.response == "Hello from Spark"
    assert stored.route["target"] == MUSE_SPARK


async def test_paid_model_out_of_credit_falls_back_to_free_model(
    orchestrator: Orchestrator, gateway: FakeGateway
):
    gateway.text_replies[MUSE_SPARK] = PAYMENT

    events = await collect(orchestrator, "hi")

    [fallback] = of_type(events, "fallback")
    assert fallback == {
        "type": "fallback",
        "index": 0,
        "from": MUSE_SPARK,
        "to": MUSE_SPARK_OPEN,
        "reason": "out of credit",
    }
    [start] = of_type(events, "step_start")
    assert (start["target"], start["cost"], start["served_by"]) == (
        MUSE_SPARK_OPEN,
        "free",
        "Baseten",
    )
    assert not orchestrator.availability.status(MUSE_SPARK).available


async def test_unavailable_model_is_skipped_without_a_call(
    orchestrator: Orchestrator, gateway: FakeGateway
):
    gateway.configured_ids.discard(MUSE_SPARK)
    gateway.route_reply = route_json(MUSE_SPARK_OPEN, [(MUSE_SPARK_OPEN, "answer")])
    orchestrator.availability.record_failure(MUSE_SPARK_OPEN, ProviderError("server", "HTTP 500"))

    events = await collect(orchestrator, "hi")

    [error] = of_type(events, "step_error")
    assert "fallback chain" in error["reason"]
    assert gateway.text_calls == []


async def test_free_mode_skips_muse_spark(orchestrator: Orchestrator, gateway: FakeGateway):
    orchestrator.settings.orin_route_fallback = "free"
    gateway.text_replies[MUSE_SPARK] = PAYMENT

    events = await collect(orchestrator, "hi")

    assert of_type(events, "step_start")[0]["target"] == MUSE_SPARK_OPEN
    assert fallback_chain(MUSE_SPARK, "free") == [MUSE_SPARK, MUSE_SPARK_OPEN]
    assert fallback_chain(MUSE_SPARK_OPEN, "spark") == [MUSE_SPARK_OPEN, MUSE_SPARK]


async def test_image_plan_writes_prompt_then_draws(
    orchestrator: Orchestrator, gateway: FakeGateway
):
    gateway.route_reply = route_json(
        MUSE_IMAGE, [(MUSE_SPARK, "write an image prompt"), (MUSE_IMAGE, "draw it")]
    )

    events = await collect(orchestrator, "make a launch banner")

    [image] = of_type(events, "image")
    assert gateway.image_prompts == ["Hello from Spark"]
    name = image["url"].removeprefix("/api/images/")
    assert await orchestrator.store.load_image(name) == b"\x89PNG fake"


async def test_image_failure_has_no_text_fallback(orchestrator: Orchestrator, gateway: FakeGateway):
    gateway.route_reply = route_json(
        MUSE_IMAGE, [(MUSE_SPARK, "write an image prompt"), (MUSE_IMAGE, "draw it")]
    )
    gateway.image_reply = ProviderError("server", "HTTP 503", 503)

    events = await collect(orchestrator, "make a launch banner")

    [error] = of_type(events, "step_error")
    assert error["index"] == 1
    assert "draw images" in error["reason"]
    assert of_type(events, "fallback") == []


async def test_failure_mid_answer_stops_instead_of_switching_models(
    orchestrator: Orchestrator, gateway: FakeGateway
):
    gateway.text_replies[MUSE_SPARK] = ["Half an ans", ProviderError("timeout", "timed out")]

    events = await collect(orchestrator, "hi")

    [error] = of_type(events, "step_error")
    assert "mid-answer" in error["reason"]
    assert [call[0] for call in gateway.text_calls] == [MUSE_SPARK]


async def test_model_recovers_after_cooldown(
    orchestrator: Orchestrator, gateway: FakeGateway, clock: Clock
):
    orchestrator.availability.record_failure(MUSE_SPARK, ProviderError("rate_limited", "429"))
    assert orchestrator.availability.status(MUSE_SPARK).reason == "rate limited"

    clock.now += 61

    assert orchestrator.availability.status(MUSE_SPARK).available


async def test_earlier_turns_become_context(orchestrator: Orchestrator, gateway: FakeGateway):
    await collect(orchestrator, "my launch is on Friday")
    await collect(orchestrator, "when is my launch?")

    assert "my launch is on Friday" in gateway.route_prompts[1]
    assert "my launch is on Friday" in gateway.text_calls[1][1]
