from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.compare import compare_reports
from evaluation.models import PronunciationAnnotation
from evaluation.runner import build_baseline, load_audio_observations, load_samples

_ANALYSIS_SERVICE_ROOT = Path(__file__).resolve().parents[1]
_BASELINE_PATH = _ANALYSIS_SERVICE_ROOT / "evaluation" / "baselines" / "coach-ko-v1.json"


def test_validation_samples_have_valid_annotations_and_unique_ids():
    # given
    expected_sample_count = 6

    # when
    sample_set = load_samples()

    # then
    assert len(sample_set.samples) == expected_sample_count
    assert len({sample.sample_id for sample in sample_set.samples}) == len(sample_set.samples)
    assert any(sample.expected_fillers for sample in sample_set.samples)
    assert any(sample.normal_expressions for sample in sample_set.samples)
    assert any(not sample.structure.conclusion.present for sample in sample_set.samples)


def test_pronunciation_accuracy_requires_two_human_scores():
    # given
    input_data = {
        "useForAccuracy": True,
        "humanScores": [80],
        "note": "single reviewer is not enough",
    }

    # when / then
    with pytest.raises(ValidationError, match="at least two"):
        PronunciationAnnotation.model_validate(input_data)


def test_current_metrics_reproduce_tracked_baseline():
    # given
    sample_set = load_samples()
    observations = load_audio_observations()
    expected = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))

    # when
    actual = build_baseline(sample_set, observations)

    # then
    assert actual == expected


def test_baseline_exposes_known_filler_and_structure_limitations():
    # given
    sample_set = load_samples()

    # when
    report = build_baseline(sample_set)

    # then
    assert report["aggregate"]["filler"] == {
        "truePositives": 4,
        "falsePositives": 4,
        "falseNegatives": 0,
        "precision": 0.5,
        "recall": 1.0,
        "f1": 0.6667,
    }
    assert report["aggregate"]["structure"]["meanAbsoluteError"] == 10


def test_tts_observations_are_not_used_as_pronunciation_accuracy_ground_truth():
    # given
    sample_set = load_samples()
    observations = load_audio_observations()

    # when
    report = build_baseline(sample_set, observations)

    # then
    pronunciation = report["aggregate"]["pronunciation"]
    assert len(observations.observations) == 6
    assert all(
        sample.audio.kind == "tts" and not sample.pronunciation.use_for_accuracy
        for sample in sample_set.samples
    )
    assert pronunciation == {
        "eligibleSampleCount": 0,
        "meanAbsoluteError": None,
        "pearsonCorrelation": None,
    }


def test_comparison_reports_filler_and_structure_improvements():
    # given
    baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    candidate = deepcopy(baseline)
    candidate["scoringRuleVersion"] = "coach-ko-v2"
    candidate["aggregate"]["filler"]["f1"] = 0.8
    candidate["aggregate"]["structure"]["meanAbsoluteError"] = 7.5

    # when
    comparison = compare_reports(baseline, candidate)

    # then
    assert comparison["metrics"]["fillerF1"]["delta"] == 0.1333
    assert comparison["metrics"]["fillerF1"]["improved"] is True
    assert comparison["metrics"]["structureMeanAbsoluteError"]["delta"] == -2.5
    assert comparison["metrics"]["structureMeanAbsoluteError"]["improved"] is True
    assert comparison["metrics"]["pronunciation"] == {"comparable": False}


def test_comparison_rejects_different_sample_sets():
    # given
    baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    candidate = deepcopy(baseline)
    candidate["samples"] = candidate["samples"][:-1]

    # when / then
    with pytest.raises(ValueError, match="same sample IDs"):
        compare_reports(baseline, candidate)


def test_comparison_rejects_changed_annotations_with_same_sample_ids():
    # given
    baseline = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    candidate = deepcopy(baseline)
    candidate["sampleSetSha256"] = "changed"

    # when / then
    with pytest.raises(ValueError, match="same validation sample set"):
        compare_reports(baseline, candidate)
