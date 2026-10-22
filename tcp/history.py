"""Completion-aware history. Only this module consumes past ground truth."""
from dataclasses import dataclass
import math
from statistics import median
from .domain import BuildKey, CompletedBuild, RankingInput


@dataclass(frozen=True)
class HistoryConfig:
    beta_fail: float = 1.0
    beta_pass: float = 1.0
    confidence_tau: float = 5.0
    cold_duration_seconds: float = 1.0
    duration_floor_seconds: float = 1e-6
    epsilon: float = 1e-8

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in vars(self).values()):
            raise ValueError('History parameters must be finite and positive')


@dataclass(frozen=True)
class Feature:
    test_id: str
    observations: int
    failures: int
    probability: float
    confidence: float
    last_failure_available_at: float | None
    duration_estimate: float
    duration_origin: str
    normalized_duration: float
    history_score: float
    history_cost_score: float
    evidence_builds: tuple[BuildKey, ...]


@dataclass(frozen=True)
class Snapshot:
    key: BuildKey
    cutoff: float
    context: tuple[str, str, str]
    features: tuple[Feature, ...]
    eligible_builds: tuple[BuildKey, ...]
    latest_evidence_available_at: float | None
    duration_reference: float


class RollingHistory:
    """Observe completed records; every query enforces its cutoff independently.

    No missing observations are synthesized. Querying a past cutoff cannot
    accidentally use an already-ingested future completion.
    """
    def __init__(self, config=HistoryConfig()):
        self.config = config
        self._builds: dict[BuildKey, CompletedBuild] = {}

    def observe(self, build: CompletedBuild):
        if build.inputs.key in self._builds:
            raise ValueError('Duplicate completed build')
        self._builds[build.inputs.key] = build

    def snapshot(self, inputs: RankingInput) -> Snapshot:
        cfg = self.config
        eligible = sorted((b for b in self._builds.values() if (
            b.usable and b.available_at is not None
            and b.available_at < inputs.cutoff
            and b.inputs.context == inputs.context
            and bool(inputs.branch)
            and b.inputs.key.physical != inputs.key.physical
        )), key=lambda b: (b.available_at, b.inputs.key))
        reference_costs = [o.duration for b in eligible for o in b.outcomes
                           if o.duration is not None and math.isfinite(o.duration) and o.duration > 0]
        reference = max(cfg.duration_floor_seconds, median(reference_costs) if reference_costs else cfg.cold_duration_seconds)
        by_test = {}
        for b in eligible:
            for o in b.outcomes:
                by_test.setdefault(o.test_id, []).append((b, o))
        features = []
        for test in sorted(inputs.tests, key=lambda t: t.test_id):
            records = by_test.get(test.test_id, [])
            known = [(b, o) for b, o in records if o.failed is not None]
            failures = sum(o.failed for _, o in known)
            n = len(known)
            probability = (failures + cfg.beta_fail) / (n + cfg.beta_fail + cfg.beta_pass)
            confidence = n / (n + cfg.confidence_tau)
            costs = [o.duration for _, o in records if o.duration is not None and math.isfinite(o.duration) and o.duration > 0]
            estimate = max(cfg.duration_floor_seconds, median(costs) if costs else reference)
            origin = 'test_median' if costs else ('context_median' if reference_costs else 'fixed_cold_start')
            last_fail = max((b.available_at for b, o in known if o.failed), default=None)
            history_score = confidence * probability
            features.append(Feature(test.test_id, n, failures, probability, confidence, last_fail,
                                    estimate, origin, estimate / reference, history_score,
                                    history_score / (math.sqrt(estimate / reference) + cfg.epsilon),
                                    tuple(b.inputs.key for b, _ in records)))
        return Snapshot(inputs.key, inputs.cutoff, inputs.context, tuple(features),
                        tuple(b.inputs.key for b in eligible),
                        max((b.available_at for b in eligible), default=None), reference)
