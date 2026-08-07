from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from app.core.config import Settings
from app.domain.entities import MetricCalculationInput, TranscriptSegmentFeatures
from app.infrastructure.audio.transcriber import FasterWhisperTranscriber
from app.infrastructure.pronunciation.local import LocalPronunciationAssessor
from evaluation.models import AudioObservation, AudioObservationSet
from evaluation.runner import DEFAULT_AUDIO_OBSERVATIONS_PATH, load_samples

_EVALUATION_ROOT = Path(__file__).resolve().parent


def capture_audio_baseline(*, model_size: str, output_path: Path) -> AudioObservationSet:
    samples = load_samples()
    settings = Settings(
        _env_file=None,
        whisper_model_size=model_size,
        whisper_device="cpu",
        whisper_compute_type="int8",
        stt_timeout_seconds=300,
    )
    transcriber = FasterWhisperTranscriber(settings=settings)
    assessor = LocalPronunciationAssessor()
    observations: list[AudioObservation] = []

    for sample in samples.samples:
        audio_path = _EVALUATION_ROOT / sample.audio.path
        if not audio_path.exists():
            raise FileNotFoundError(
                f"TTS audio is missing: {audio_path}. Run evaluation/generate_tts.ps1 first."
            )
        transcript = transcriber.transcribe(audio_path, language="ko-KR")
        calc_input = MetricCalculationInput(
            text=transcript.text,
            duration_ms=transcript.duration_ms,
            segments=[
                TranscriptSegmentFeatures(
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    text=segment.text,
                    avg_logprob=segment.avg_logprob,
                )
                for segment in transcript.segments
            ],
        )
        assessment = assessor.assess(
            audio_path=audio_path,
            calc_input=calc_input,
            language="ko-KR",
        )
        avg_logprob = (
            round(
                sum(segment.avg_logprob for segment in transcript.segments)
                / len(transcript.segments),
                4,
            )
            if transcript.segments
            else None
        )
        observations.append(
            AudioObservation(
                sample_id=sample.sample_id,
                audio_sha256=hashlib.sha256(audio_path.read_bytes()).hexdigest(),
                stt_model_version=transcript.model_version,
                transcript=transcript.text,
                duration_ms=transcript.duration_ms,
                avg_logprob=avg_logprob,
                pronunciation_provider=assessment.provider,
                pronunciation_score=assessment.pronunciation_score,
            )
        )

    result = AudioObservationSet(schema_version=1, observations=observations)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        result.model_dump_json(by_alias=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture current STT/local-pronunciation results for generated audio"
    )
    parser.add_argument("--model-size", default="tiny")
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIO_OBSERVATIONS_PATH)
    args = parser.parse_args()
    capture_audio_baseline(model_size=args.model_size, output_path=args.output)


if __name__ == "__main__":
    main()
