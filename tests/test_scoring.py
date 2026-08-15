import pytest
from pydantic import ValidationError

from countergap.schemas import ScoreVector
from countergap.scoring import aggregate_score, build_score_vector


def test_score_vector_clips_to_unit_interval():
    s = build_score_vector(
        pre_cutoff_novelty=-1,
        evidence_quality=2,
        counterevidence_robustness=0.5,
        future_emergence=0.2,
        reproducibility=1.0,
    )
    assert s.pre_cutoff_novelty == 0.0
    assert s.evidence_quality == 1.0
    assert 0.0 <= aggregate_score(s) <= 1.0


def test_zero_weight_sum_rejected():
    s = build_score_vector(
        pre_cutoff_novelty=0.1,
        evidence_quality=0.1,
        counterevidence_robustness=0.1,
        future_emergence=0.1,
        reproducibility=0.1,
    )
    with pytest.raises(ValueError):
        aggregate_score(s, {"pre_cutoff_novelty": 0.0})


def test_direct_score_vector_rejects_out_of_range_components():
    with pytest.raises(ValidationError):
        ScoreVector(
            pre_cutoff_novelty=1.1,
            evidence_quality=0.5,
            counterevidence_robustness=0.5,
            future_emergence=0.5,
            reproducibility=0.5,
        )


def test_missing_future_emergence_is_excluded_from_aggregation():
    score = build_score_vector(
        pre_cutoff_novelty=0.5,
        evidence_quality=0.5,
        counterevidence_robustness=0.5,
        future_emergence=None,
        reproducibility=0.5,
    )

    assert score.future_emergence is None
    assert aggregate_score(score) == pytest.approx(0.5)
