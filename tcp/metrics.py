"""Full-inventory failing-class metrics, not distinct-fault metrics."""
import math
from .domain import Outcome


def evaluate(order: tuple[str, ...], outcomes: tuple[Outcome, ...], budgets=(0.1, 0.25, 0.5)):
    ids = [o.test_id for o in outcomes]
    if len(set(ids)) != len(ids) or len(order) != len(ids) or set(order) != set(ids):
        raise ValueError('Ranking must be an exact permutation of the declared ground truth')
    if any(not math.isfinite(x) or x <= 0 or x > 1 for x in budgets):
        raise ValueError('Budget fractions must be in (0,1]')
    data = {o.test_id: o for o in outcomes}
    n = len(order)
    unknown = sum(o.failed is None for o in outcomes)
    invalid = sum(o.duration is None or not math.isfinite(o.duration) or o.duration < 0 for o in outcomes)
    m = sum(o.failed is True for o in outcomes)
    zero = sum(o.duration == 0 for o in outcomes)
    total = math.fsum(o.duration for o in outcomes) if not invalid else None
    result = dict(tests=n, observed_failures=m, unknown_outcomes=unknown, invalid_durations=invalid,
                  zero_durations=zero, total_duration_seconds=total, apfd=None, apfdc_midpoint=None,
                  ttff_seconds=None, ttff_censored=None, censor_time_seconds=None,
                  recall={str(b): None for b in budgets}, reasons=[])
    if not n:
        result['reasons'].append('empty_inventory')
        return result
    if unknown:
        result['reasons'].append('unknown_outcomes')
        return result
    if not m:
        result['reasons'].append('no_failures')
        result['ttff_censored'] = True
        result['censor_time_seconds'] = total
        return result
    result['apfd'] = 1 - sum(i for i, t in enumerate(order, 1) if data[t].failed) / (n*m) + 1/(2*n)
    if invalid:
        result['reasons'].append('invalid_duration')
        return result
    if total <= 0:
        result['reasons'].append('zero_total_duration')
        return result
    elapsed = 0.0
    midpoints, failure_completions = [], []
    for t in order:
        cost = data[t].duration
        if data[t].failed:
            midpoints.append(elapsed + cost/2)
            failure_completions.append(elapsed + cost)
        elapsed += cost
    result['apfdc_midpoint'] = 1 - math.fsum(midpoints)/(m*total)
    result['ttff_seconds'] = failure_completions[0]
    result['ttff_censored'] = False
    result['recall'] = {str(b): sum(c <= b*total or math.isclose(c, b*total, rel_tol=1e-12, abs_tol=0)
                                 for c in failure_completions)/m for b in budgets}
    return result
