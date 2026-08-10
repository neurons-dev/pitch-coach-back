from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from evaluation.compare import compare_reports
from evaluation.models import PronunciationAnnotation
from evaluation.runner import build_baseline, load_audio_observations, load_samples
from app.domain.entities import StructureAnalysisResult
from app.domain.filler_detector import FillerDetectionResult


def _fake_structure_analyzer(_calc_input, *, practice_type_code=None, target_duration_sec=None):
    return StructureAnalysisResult(
        score=80, intro=True, body=True, conclusion=True,
        reasoning="테스트용 고정 결과", analyzer="fake",
    )


def _baseline_report() -> dict:
    return {
        "schemaVersion": 2,
        "scoringRuleVersion": "coach-ko-v2",
        "sampleSetSha256": "test-sha",
        "sampleCount": 2,
        "aggregate": {
            "filler": {
                "truePositives": 4,
                "falsePositives": 4,
                "falseNegatives": 4,
                "precision": 0.5,
                "recall": 0.5,
                "f1": 0.5,
            },
            "structure": {
                "meanAbsoluteError": 10.0,
                "exactMatchRate": 0.5,
                "withinTenPointsRate": 0.5,
            },
            "pronunciation": {
                "eligibleSampleCount": 0,
                "meanAbsoluteError": None,
                "pearsonCorrelation": None,
            },
        },
        "samples": [
            {"sampleId": "sample-1"},
            {"sampleId": "sample-2"},
        ],
    }


def test_validation_samples_have_valid_annotations_and_unique_ids():
    # given
    expected_sample_count = 8

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


def test_baseline_records_injected_detector_metadata():
    # given
    sample_set = load_samples()

    def fake_detector(_calc_input):
        return FillerDetectionResult(
            detector="openai",
            model="test-model",
            prompt_version="test-prompt-v1",
        )

    # when
    report = build_baseline(
        sample_set, filler_detector=fake_detector, structure_analyzer=_fake_structure_analyzer
    )

    # then
    assert report["schemaVersion"] == 2
    assert report["samples"][0]["filler"] == {
        "expectedCount": 0,
        "predictedCount": 0,
        "detector": "openai",
        "model": "test-model",
        "promptVersion": "test-prompt-v1",
        "fallbackReason": None,
        "detections": [],
    }


def test_tts_observations_are_not_used_as_pronunciation_accuracy_ground_truth():
    # given
    sample_set = load_samples()
    observations = load_audio_observations()

    # when
    report = build_baseline(
        sample_set, observations, structure_analyzer=_fake_structure_analyzer
    )

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
    baseline = _baseline_report()
    candidate = deepcopy(baseline)
    candidate["scoringRuleVersion"] = "coach-ko-v3"
    candidate["aggregate"]["filler"]["precision"] = 0.75
    candidate["aggregate"]["filler"]["recall"] = 1.0
    candidate["aggregate"]["filler"]["f1"] = 0.8
    candidate["aggregate"]["filler"]["falsePositives"] = 1
    candidate["aggregate"]["structure"]["meanAbsoluteError"] = 7.5

    # when
    comparison = compare_reports(baseline, candidate)

    # then
    assert comparison["metrics"]["fillerPrecision"]["delta"] == 0.25
    assert comparison["metrics"]["fillerPrecision"]["improved"] is True
    assert comparison["metrics"]["fillerRecall"]["delta"] == 0.5
    assert comparison["metrics"]["fillerF1"]["delta"] == 0.3
    assert comparison["metrics"]["fillerF1"]["improved"] is True
    assert comparison["metrics"]["fillerFalsePositives"]["delta"] == -3
    assert comparison["metrics"]["fillerFalsePositives"]["improved"] is True
    assert comparison["metrics"]["structureMeanAbsoluteError"]["delta"] == -2.5
    assert comparison["metrics"]["structureMeanAbsoluteError"]["improved"] is True
    assert comparison["metrics"]["pronunciation"] == {"comparable": False}


def test_comparison_rejects_different_sample_sets():
    # given
    baseline = _baseline_report()
    candidate = deepcopy(baseline)
    candidate["samples"] = candidate["samples"][:-1]

    # when / then
    with pytest.raises(ValueError, match="same sample IDs"):
        compare_reports(baseline, candidate)


def test_comparison_rejects_changed_annotations_with_same_sample_ids():
    # given
    baseline = _baseline_report()
    candidate = deepcopy(baseline)
    candidate["sampleSetSha256"] = "changed"

    # when / then
    with pytest.raises(ValueError, match="same validation sample set"):
        compare_reports(baseline, candidate)
