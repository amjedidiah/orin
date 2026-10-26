"""Live router eval: how often the router picks the expected model.

Every model is treated as available, so the score measures routing judgement, not
provider configuration. Run from `backend/`: `uv run python scripts/eval_router.py`
Exits non-zero when accuracy is below `--min` (default 0.8).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from orin.config import get_settings
from orin.gateway import ModelGateway
from orin.registry import MODELS
from orin.router import route

CASES = Path(__file__).parent.parent / "evals" / "router_cases.json"


def passed(case: dict, target: str, steps: list[str]) -> bool:
    if target not in case["expect"]:
        return False
    expected_steps = case.get("steps")
    if expected_steps is None:
        return len(steps) == 1
    return len(steps) == len(expected_steps) and all(
        want in ("*", got) for want, got in zip(expected_steps, steps, strict=True)
    )


async def main(minimum: float) -> int:
    cases = json.loads(CASES.read_text())
    gateway = ModelGateway(get_settings())
    correct = 0
    for case in cases:
        decision = await route(gateway, case["prompt"], "", list(MODELS))
        steps = [step.target for step in decision.steps]
        ok = passed(case, decision.target, steps)
        correct += ok
        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {decision.target:<16} {steps}  {case['prompt'][:60]}")
        if decision.routed_by != "router":
            print(f"      ({decision.reason})")
    accuracy = correct / len(cases)
    print(f"\nRouter accuracy: {correct}/{len(cases)} = {accuracy:.0%}")
    return 0 if accuracy >= minimum else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min", type=float, default=0.8)
    sys.exit(asyncio.run(main(parser.parse_args().min)))
