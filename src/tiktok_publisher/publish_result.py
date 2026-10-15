from __future__ import annotations

from dataclasses import dataclass

from tiktok_publisher.outcomes import Outcome, OutcomeCode, outcome_from_publish


@dataclass(frozen=True)
class PublishResult:
    ok: bool
    code: OutcomeCode
    message: str

    def to_outcome(self, *, dry_run: bool) -> Outcome:
        return outcome_from_publish(self.ok, self.message, dry_run=dry_run)

    @classmethod
    def from_outcome(cls, outcome: Outcome) -> PublishResult:
        ok = outcome.code in (
            OutcomeCode.published,
            OutcomeCode.dry_run,
        )
        return cls(ok=ok, code=outcome.code, message=outcome.detail)
