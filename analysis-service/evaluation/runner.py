from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from typing import Callable

from app.core.config import get_settings
from app.domain.entities import (
    MetricCalculationInput,
    StructureAnalysisResult,
    TranscriptSegmentFeatures,
)
from app.domain.filler import (
    FillerOccurrence,
    detect_conservative_filler_occurrences,
)
from app.domain.filler_detector import FillerDetectionResult
from app.domain.metrics import (
    SCORING_RULE_VERSION,
    calc_filler,
    calc_structure,
)
from app.infrastructure.filler.factory import create_filler_detector
from app.infrastructure.structure.factory import create_structure_analyzer
from evaluation.models import AudioObservationSet, ValidationSample, ValidationSampleSet

_EVALUATION_ROOT = Path(__file__).resolve().parent
DEFAULT_SAMPLES_PATH = _EVALUATION_ROOT / "samples" / "validation_samples.json"
DEFAULT_AUDIO_OBSERVATIONS_PATH = (
    _EVALUATION_ROOT / "baselines" / "audio_observations.json"
)
DEFAULT_OUTPUT_PATH = _EVALUATION_ROOT / "baselines" / "coach-ko-v2.local.json"


def _conservative_detector(
    calc_input: MetricCalculationInput,
) -> FillerDetectionResult:
    return FillerDetectionResult(
        occurrences=detect_conservative_filler_occurrences(calc_input),
        detector="conservative-v1",
    )


def load_samples(path: Path = DEFAULT_SAMPLES_PATH) -> ValidationSampleSet:
    return ValidationSampleSet.model_validate_json(path.read_text(encoding="utf-8"))


def load_audio_observations(
    path: Path = DEFAULT_AUDIO_OBSERVATIONS_PATH,
) -> AudioObservationSet:
    if not path.exists():
        return AudioObservationSet(schema_version=1, observations=[])
    return AudioObservationSet.model_validate_json(path.read_text(encoding="utf-8"))


def _metric_input(sample: ValidationSample) -> MetricCalculationInput:
    return MetricCalculationInput(
        text=sample.transcript,
        duration_ms=sample.duration_ms,
        segments=[
            TranscriptSegmentFeatures(
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text,
                avg_logprob=0.0,
            )
            for segment in sample.segments
        ],
    )


def _sample_set_sha256(samples: ValidationSampleSet) -> str:
    serialized = json.dumps(
        samples.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _round_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 1.0


def _filler_counts(
    sample: ValidationSample,
    predicted: list[FillerOccurrence],
    *,
    include_evidence: bool,
) -> tuple[int, int, int, list[dict]]:
    expected_keys = {
        (item.start_char, item.end_char, item.text) for item in sample.expected_fillers
    }
    predicted_keys = {
        (item.start_char, item.end_char, item.text) for item in predicted
    }
    true_positives = len(expected_keys & predicted_keys)
    false_positives = len(predicted_keys - expected_keys)
    false_negatives = len(expected_keys - predicted_keys)
    detections = []
    for item in predicted:
        detection = {
            "text": item.text,
            "startChar": item.start_char,
            "endChar": item.end_char,
            "isExpected": (item.start_char, item.end_char, item.text) in expected_keys,
        }
        if include_evidence:
            detection.update(
                {
                    "startMs": item.start_ms,
                    "endMs": item.end_ms,
                    "precedingPauseMs": item.preceding_pause_ms,
                    "followingPauseMs": item.following_pause_ms,
                    "reason": item.reason,
                    "evidence": item.evidence,
                }
            )
        detections.append(detection)

    return (
        true_positives,
        false_positives,
        false_negatives,
        detections,
    )


def _pearson_correlation(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    left = [pair[0] for pair in pairs]
    right = [pair[1] for pair in pairs]
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in pairs)
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left)
        * sum((y - right_mean) ** 2 for y in right)
    )
    return round(numerator / denominator, 4) if denominator else None


def build_baseline(
    samples: ValidationSampleSet,
    audio_observations: AudioObservationSet | None = None,
    *,
    structure_analyzer: Callable[..., StructureAnalysisResult],
    filler_detector: Callable[
        [MetricCalculationInput], FillerDetectionResult
    ] = _conservative_detector,
    scoring_rule_version: str = SCORING_RULE_VERSION,
    schema_version: int = 2,
    include_filler_evidence: bool = True,
) -> dict:
    observations = (
        audio_observations or AudioObservationSet(schema_version=1, observations=[])
    ).observations
    sample_ids = {sample.sample_id for sample in samples.samples}
    observation_ids = {observation.sample_id for observation in observations}
    unknown_observation_ids = observation_ids - sample_ids
    if unknown_observation_ids:
        raise ValueError(
            f"audio observations reference unknown samples: {sorted(unknown_observation_ids)}"
        )
    observation_by_id = {
        observation.sample_id: observation
        for observation in observations
    }
    sample_results: list[dict] = []
    filler_totals = {"truePositives": 0, "falsePositives": 0, "falseNegatives": 0}
    structure_errors: list[int] = []
    pronunciation_pairs: list[tuple[float, float]] = []

    for sample in samples.samples:
        calc_input = _metric_input(sample)
        filler_detection = filler_detector(calc_input)
        filler_score = calc_filler(calc_input, filler_detection)
        structure_analysis = structure_analyzer(
            calc_input,
            practice_type_code=sample.practice_type_code,
            target_duration_sec=sample.target_duration_sec,
        )
        structure_score = calc_structure(structure_analysis)
        true_positives, false_positives, false_negatives, detections = _filler_counts(
            sample,
            filler_detection.occurrences,
            include_evidence=include_filler_evidence,
        )
        filler_totals["truePositives"] += true_positives
        filler_totals["falsePositives"] += false_positives
        filler_totals["falseNegatives"] += false_negatives

        structure_error = abs(structure_score.score - sample.structure.human_score)
        structure_errors.append(structure_error)
        observation = observation_by_id.get(sample.sample_id)
        human_pronunciation_score = (
            mean(sample.pronunciation.human_scores)
            if sample.pronunciation.use_for_accuracy
            else None
        )
        if observation is not None and human_pronunciation_score is not None:
            pronunciation_pairs.append(
                (float(observation.pronunciation_score), human_pronunciation_score)
            )

        filler_result = {
            "expectedCount": len(sample.expected_fillers),
            "predictedCount": len(detections),
            "detections": detections,
        }
        if include_filler_evidence:
            filler_result.update(
                {
                    "detector": filler_detection.detector,
                    "model": filler_detection.model,
                    "promptVersion": filler_detection.prompt_version,
                    "fallbackReason": filler_detection.fallback_reason,
                }
            )

        sample_results.append(
            {
                "sampleId": sample.sample_id,
                "scores": {
                    "pronunciation": (
                        observation.pronunciation_score if observation is not None else None
                    ),
                    "filler": filler_score.score,
                    "structure": structure_score.score,
                },
                "filler": filler_result,
                "structure": {
                    "signals": {
                        "intro": structure_analysis.intro,
                        "body": structure_analysis.body,
                        "conclusion": structure_analysis.conclusion,
                    },
                    "reasoning": structure_analysis.reasoning,
                    "analyzer": structure_analysis.analyzer,
                    "humanScore": sample.structure.human_score,
                    "absoluteError": structure_error,
                },
                "pronunciation": {
                    "accuracyEligible": sample.pronunciation.use_for_accuracy,
                    "audioKind": sample.audio.kind,
                    "observationAvailable": observation is not None,
                    "audioSha256": (
                        observation.audio_sha256 if observation is not None else None
                    ),
                    "sttModelVersion": (
                        observation.stt_model_version if observation is not None else None
                    ),
                    "provider": (
                        observation.pronunciation_provider
                        if observation is not None
                        else None
                    ),
                },
            }
        )

    true_positives = filler_totals["truePositives"]
    false_positives = filler_totals["falsePositives"]
    false_negatives = filler_totals["falseNegatives"]
    precision = _round_ratio(true_positives, true_positives + false_positives)
    recall = _round_ratio(true_positives, true_positives + false_negatives)
    f1 = round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0
    pronunciation_errors = [abs(predicted - expected) for predicted, expected in pronunciation_pairs]

    return {
        "schemaVersion": schema_version,
        "scoringRuleVersion": scoring_rule_version,
        "sampleSetSha256": _sample_set_sha256(samples),
        "sampleCount": len(samples.samples),
        "aggregate": {
            "filler": {
                **filler_totals,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            },
            "structure": {
                "meanAbsoluteError": round(mean(structure_errors), 4),
                "exactMatchRate": _round_ratio(
                    sum(error == 0 for error in structure_errors), len(structure_errors)
                ),
                "withinTenPointsRate": _round_ratio(
                    sum(error <= 10 for error in structure_errors), len(structure_errors)
                ),
            },
            "pronunciation": {
                "eligibleSampleCount": len(pronunciation_pairs),
                "meanAbsoluteError": (
                    round(mean(pronunciation_errors), 4) if pronunciation_errors else None
                ),
                "pearsonCorrelation": _pearson_correlation(pronunciation_pairs),
            },
        },
        "samples": sample_results,
    }


def write_baseline(report: dict, output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the current analysis metric baseline")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES_PATH)
    parser.add_argument(
        "--audio-observations", type=Path, default=DEFAULT_AUDIO_OBSERVATIONS_PATH
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    settings = get_settings()
    detector = create_filler_detector(settings)
    analyzer = create_structure_analyzer(settings)
    report = build_baseline(
        load_samples(args.samples),
        load_audio_observations(args.audio_observations),
        filler_detector=detector.detect,
        structure_analyzer=analyzer.analyze,
    )
    write_baseline(report, args.output)


if __name__ == "__main__":
    main()
