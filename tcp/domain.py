"""Explicit boundary between pre-ranking inputs and post-run observations."""
from dataclasses import dataclass
import math


@dataclass(frozen=True, order=True)
class BuildKey:
    project: str
    pr: str
    build: str
    stage: str

    @property
    def physical(self):
        return self.project, self.pr, self.build


@dataclass(frozen=True)
class TestInput:
    test_id: str
    source_status: str = 'unverified'
    source_paths: tuple[str, ...] = ()
    source_sha256: str | None = None
    category: str = 'test'


@dataclass(frozen=True)
class RankingInput:
    key: BuildKey
    branch: str
    cutoff: float
    commit: str
    tests: tuple[TestInput, ...]
    inventory_origin: str = 'observed_log_inventory'

    def __post_init__(self):
        ids = [t.test_id for t in self.tests]
        if not math.isfinite(self.cutoff) or len(ids) != len(set(ids)):
            raise ValueError('Invalid cutoff or duplicate test IDs')
        if any(not name for name in ids):
            raise ValueError('Empty test ID')

    @property
    def context(self):
        # No merging of branch aliases, PRs share history only on the same base branch.
        return self.key.project, self.branch, self.key.stage


@dataclass(frozen=True)
class Outcome:
    test_id: str
    failed: bool | None
    duration: float | None

    def __post_init__(self):
        if self.failed is not None and type(self.failed) is not bool:
            raise ValueError('Outcome must be bool or None (unknown)')


@dataclass(frozen=True)
class CompletedBuild:
    inputs: RankingInput
    available_at: float | None
    result: str
    outcomes: tuple[Outcome, ...]

    def __post_init__(self):
        ids = [o.test_id for o in self.outcomes]
        if len(ids) != len(set(ids)) or set(ids) != {t.test_id for t in self.inputs.tests}:
            raise ValueError('Ground truth must match the full declared inventory')
        if self.available_at is not None and (
            not math.isfinite(self.available_at) or self.available_at < self.inputs.cutoff
        ):
            raise ValueError('Availability cannot precede ranking cutoff')

    @property
    def usable(self):
        return self.result in ('SUCCESS', 'FAILURE', 'UNSTABLE')
