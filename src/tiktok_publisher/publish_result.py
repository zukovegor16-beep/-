from __future__ import annotations

from dataclasses import dataclass

from tiktok_publisher.outcomes import Outcome, OutcomeCode


@dataclass(frozen=True)
class PublishResult:
    ok: bool
    code: OutcomeCode
    message: str

    def to_outcome(self, *, dry_run: bool) -> Outcome:
        if dry_run and self.ok:
            return Outcome.from_code(OutcomeCode.dry_run, self.message)
        if self.ok:
            return Outcome.from_code(OutcomeCode.published, self.message)
        return Outcome.from_code(self.code, self.message)

    @classmethod
    def from_outcome(cls, outcome: Outcome) -> PublishResult:
        ok = outcome.code in (
            OutcomeCode.published,
            OutcomeCode.dry_run,
        )
        return cls(ok=ok, code=outcome.code, message=outcome.detail)
