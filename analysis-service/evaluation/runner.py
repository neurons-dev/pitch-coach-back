from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

from app.domain.entities import MetricCalculationInput, TranscriptSegmentFeatures
from app.domain.metrics import (
    SCORING_RULE_VERSION,
    calc_filler,
    calc_structure,
    detect_filler_occurrences,
    detect_structure_signals,
)
from evaluation.models import AudioObservationSet, ValidationSample, ValidationSampleSet

_EVALUATION_ROOT = Path(__file__).resolve().parent
DEFAULT_SAMPLES_PATH = _EVALUATION_ROOT / "samples" / "validation_samples.json"
DEFAULT_AUDIO_OBSERVATIONS_PATH = (
    _EVALUATION_ROOT / "baselines" / "audio_observations.json"
)
DEFAULT_OUTPUT_PATH = _EVALUATION_ROOT / "baselines" / "coach-ko-v1.json"


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


def _filler_counts(sample: ValidationSample) -> tuple[int, int, int, list[dict]]:
    predicted = detect_filler_occurrences(sample.transcript)
    expected_keys = {
        (item.start_char, item.end_char, item.text) for item in sample.expected_fillers
    }
    predicted_keys = {
        (item.start_char, item.end_char, item.text) for item in predicted
    }
    true_positives = len(expected_keys & predicted_keys)
    false_positives = len(predicted_keys - expected_keys)
    false_negatives = len(expected_keys - predicted_keys)
    return (
        true_positives,
        false_positives,
        false_negatives,
        [
            {
                "text": item.text,
                "startChar": item.start_char,
                "endChar": item.end_char,
                "isExpected": (item.start_char, item.end_char, item.text) in expected_keys,
            }
            for item in predicted
        ],
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
        filler_score = calc_filler(calc_input)
        structure_score = calc_structure(calc_input)
        signals = detect_structure_signals(calc_input)
        true_positives, false_positives, false_negatives, detections = _filler_counts(sample)
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
                "filler": {
                    "expectedCount": len(sample.expected_fillers),
                    "predictedCount": len(detections),
                    "detections": detections,
                },
                "structure": {
                    "signals": {
                        "intro": signals.intro,
                        "body": signals.body,
                        "conclusion": signals.conclusion,
                    },
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
        "schemaVersion": 1,
        "scoringRuleVersion": SCORING_RULE_VERSION,
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

    report = build_baseline(
        load_samples(args.samples),
        load_audio_observations(args.audio_observations),
    )
    write_baseline(report, args.output)


if __name__ == "__main__":
    main()
