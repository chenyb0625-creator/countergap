from __future__ import annotations

from countergap.schemas import ScoreVector


def _clip(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def build_score_vector(
    *,
    pre_cutoff_novelty: float,
    evidence_quality: float,
    counterevidence_robustness: float,
    future_emergence: float | None,
    reproducibility: float,
) -> ScoreVector:
    return ScoreVector(
        pre_cutoff_novelty=_clip(pre_cutoff_novelty),
        evidence_quality=_clip(evidence_quality),
        counterevidence_robustness=_clip(counterevidence_robustness),
        future_emergence=(
            _clip(future_emergence) if future_emergence is not None else None
        ),
        reproducibility=_clip(reproducibility),
    )


def aggregate_score(score: ScoreVector, weights: dict[str, float] | None = None) -> float:
    if weights is None:
        weights = {
            "pre_cutoff_novelty": 0.25,
            "evidence_quality": 0.25,
            "counterevidence_robustness": 0.25,
            "future_emergence": 0.15,
            "reproducibility": 0.10,
        }
    total_w = sum(weights.values())
    if total_w <= 0:
        raise ValueError("weights must sum to > 0")
    values = score.as_dict()
    available = [(values[key], weight) for key, weight in weights.items() if values[key] is not None]
    available_weight = sum(weight for _, weight in available)
    if available_weight <= 0:
        raise ValueError("at least one score component must be available")
    return sum(value * weight for value, weight in available) / available_weight
