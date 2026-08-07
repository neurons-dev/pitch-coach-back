from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _delta(candidate: float, baseline: float) -> float:
    return round(candidate - baseline, 4)


def compare_reports(baseline: dict, candidate: dict) -> dict:
    baseline_ids = {sample["sampleId"] for sample in baseline["samples"]}
    candidate_ids = {sample["sampleId"] for sample in candidate["samples"]}
    if baseline_ids != candidate_ids:
        raise ValueError("baseline and candidate must contain the same sample IDs")
    if baseline["sampleSetSha256"] != candidate["sampleSetSha256"]:
        raise ValueError("baseline and candidate must use the same validation sample set")

    baseline_filler = baseline["aggregate"]["filler"]
    candidate_filler = candidate["aggregate"]["filler"]
    baseline_structure = baseline["aggregate"]["structure"]
    candidate_structure = candidate["aggregate"]["structure"]
    baseline_pronunciation = baseline["aggregate"]["pronunciation"]
    candidate_pronunciation = candidate["aggregate"]["pronunciation"]

    pronunciation_comparable = all(
        value is not None
        for value in (
            baseline_pronunciation["meanAbsoluteError"],
            candidate_pronunciation["meanAbsoluteError"],
            baseline_pronunciation["pearsonCorrelation"],
            candidate_pronunciation["pearsonCorrelation"],
        )
    )
    pronunciation_comparison = {"comparable": pronunciation_comparable}
    if pronunciation_comparable:
        pronunciation_comparison.update(
            {
                "meanAbsoluteError": {
                    "baseline": baseline_pronunciation["meanAbsoluteError"],
                    "candidate": candidate_pronunciation["meanAbsoluteError"],
                    "delta": _delta(
                        candidate_pronunciation["meanAbsoluteError"],
                        baseline_pronunciation["meanAbsoluteError"],
                    ),
                    "improved": (
                        candidate_pronunciation["meanAbsoluteError"]
                        < baseline_pronunciation["meanAbsoluteError"]
                    ),
                },
                "pearsonCorrelation": {
                    "baseline": baseline_pronunciation["pearsonCorrelation"],
                    "candidate": candidate_pronunciation["pearsonCorrelation"],
                    "delta": _delta(
                        candidate_pronunciation["pearsonCorrelation"],
                        baseline_pronunciation["pearsonCorrelation"],
                    ),
                    "improved": (
                        candidate_pronunciation["pearsonCorrelation"]
                        > baseline_pronunciation["pearsonCorrelation"]
                    ),
                },
            }
        )

    return {
        "schemaVersion": 1,
        "baselineScoringRuleVersion": baseline["scoringRuleVersion"],
        "candidateScoringRuleVersion": candidate["scoringRuleVersion"],
        "sampleSetSha256": baseline["sampleSetSha256"],
        "sampleCount": len(baseline_ids),
        "metrics": {
            "fillerF1": {
                "baseline": baseline_filler["f1"],
                "candidate": candidate_filler["f1"],
                "delta": _delta(candidate_filler["f1"], baseline_filler["f1"]),
                "improved": candidate_filler["f1"] > baseline_filler["f1"],
            },
            "structureMeanAbsoluteError": {
                "baseline": baseline_structure["meanAbsoluteError"],
                "candidate": candidate_structure["meanAbsoluteError"],
                "delta": _delta(
                    candidate_structure["meanAbsoluteError"],
                    baseline_structure["meanAbsoluteError"],
                ),
                "improved": (
                    candidate_structure["meanAbsoluteError"]
                    < baseline_structure["meanAbsoluteError"]
                ),
            },
            "pronunciation": pronunciation_comparison,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two analysis baseline reports")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    comparison = compare_reports(load_report(args.baseline), load_report(args.candidate))
    serialized = json.dumps(comparison, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(serialized, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
