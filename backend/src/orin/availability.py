"""Which models are usable right now, learned from the errors their providers return."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from orin.gateway import ErrorKind, Gateway, ProviderError
from orin.registry import MODELS

# How long a model stays unavailable after each kind of failure, in seconds.
COOLDOWNS: dict[ErrorKind, float] = {
    "rate_limited": 60,
    "server": 30,
    "timeout": 30,
    "payment_required": 600,
    "auth": 600,
}

REASONS: dict[ErrorKind, str] = {
    "not_configured": "not configured",
    "rate_limited": "rate limited",
    "payment_required": "out of credit",
    "auth": "key rejected",
    "server": "provider error",
    "timeout": "timed out",
    "bad_request": "request rejected",
}


@dataclass(frozen=True)
class Status:
    available: bool
    reason: str | None = None


class Availability:
    def __init__(self, gateway: Gateway, clock: Callable[[], float] = time.monotonic) -> None:
        self.gateway = gateway
        self.clock = clock
        self._failures: dict[str, tuple[ErrorKind, float]] = {}

    def record_failure(self, target_id: str, error: ProviderError) -> None:
        if error.kind in COOLDOWNS:
            self._failures[target_id] = (error.kind, self.clock() + COOLDOWNS[error.kind])

    def status(self, target_id: str) -> Status:
        if not self.gateway.configured(target_id):
            return Status(False, REASONS["not_configured"])
        failure = self._failures.get(target_id)
        if failure and self.clock() < failure[1]:
            return Status(False, REASONS[failure[0]])
        return Status(True)

    def available_ids(self) -> list[str]:
        return [target_id for target_id in MODELS if self.status(target_id).available]


def reason_for(error: ProviderError) -> str:
    return REASONS[error.kind]
