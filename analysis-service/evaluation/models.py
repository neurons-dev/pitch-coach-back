from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class EvaluationModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class TranscriptSegmentSample(EvaluationModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> TranscriptSegmentSample:
        if self.end_ms <= self.start_ms:
            raise ValueError("segment endMs must be greater than startMs")
        return self


class TextSpanAnnotation(EvaluationModel):
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    note: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> TextSpanAnnotation:
        if self.end_char <= self.start_char:
            raise ValueError("annotation endChar must be greater than startChar")
        return self


class StructureElementAnnotation(EvaluationModel):
    present: bool
    evidence: list[str]


class StructureAnnotation(EvaluationModel):
    intro: StructureElementAnnotation
    body: StructureElementAnnotation
    conclusion: StructureElementAnnotation
    human_score: int = Field(ge=0, le=100)


class PronunciationAnnotation(EvaluationModel):
    use_for_accuracy: bool
    human_scores: list[int] = Field(default_factory=list)
    note: str

    @model_validator(mode="after")
    def validate_human_scores(self) -> PronunciationAnnotation:
        if any(not 0 <= score <= 100 for score in self.human_scores):
            raise ValueError("human pronunciation scores must be between 0 and 100")
        if self.use_for_accuracy and len(self.human_scores) < 2:
            raise ValueError(
                "accuracy samples require at least two human pronunciation scores"
            )
        return self


class AudioSampleMetadata(EvaluationModel):
    kind: Literal["tts", "human", "public"]
    path: str
    source: str
    usage: str
    use_for_pronunciation_accuracy: bool


class ValidationSample(EvaluationModel):
    sample_id: str = Field(min_length=1)
    title: str
    practice_type_code: str
    target_duration_sec: int | None = None
    transcript: str
    duration_ms: int = Field(gt=0)
    segments: list[TranscriptSegmentSample]
    expected_fillers: list[TextSpanAnnotation]
    normal_expressions: list[TextSpanAnnotation]
    structure: StructureAnnotation
    pronunciation: PronunciationAnnotation
    audio: AudioSampleMetadata

    @model_validator(mode="after")
    def validate_annotations(self) -> ValidationSample:
        annotations = self.expected_fillers + self.normal_expressions
        for annotation in annotations:
            actual = self.transcript[annotation.start_char : annotation.end_char]
            if actual != annotation.text:
                raise ValueError(
                    f"{self.sample_id}: annotation {annotation.text!r} does not match "
                    f"transcript slice {actual!r}"
                )
        if any(segment.end_ms > self.duration_ms for segment in self.segments):
            raise ValueError(f"{self.sample_id}: segment exceeds durationMs")
        annotation_keys = {
            (annotation.start_char, annotation.end_char, annotation.text)
            for annotation in annotations
        }
        if len(annotation_keys) != len(annotations):
            raise ValueError(f"{self.sample_id}: duplicate text annotations are not allowed")
        for element in (
            self.structure.intro,
            self.structure.body,
            self.structure.conclusion,
        ):
            if element.present and not element.evidence:
                raise ValueError(f"{self.sample_id}: present structure elements require evidence")
            if not element.present and element.evidence:
                raise ValueError(f"{self.sample_id}: absent structure elements cannot have evidence")
            if any(evidence not in self.transcript for evidence in element.evidence):
                raise ValueError(f"{self.sample_id}: structure evidence is not in transcript")
        if self.audio.use_for_pronunciation_accuracy != self.pronunciation.use_for_accuracy:
            raise ValueError(f"{self.sample_id}: pronunciation accuracy flags must match")
        if self.audio.kind == "tts" and self.pronunciation.use_for_accuracy:
            raise ValueError(f"{self.sample_id}: TTS cannot be pronunciation ground truth")
        return self


class ValidationSampleSet(EvaluationModel):
    schema_version: int
    description: str
    samples: list[ValidationSample] = Field(min_length=1)


class AudioObservation(EvaluationModel):
    sample_id: str
    audio_sha256: str
    stt_model_version: str
    transcript: str
    duration_ms: int
    avg_logprob: float | None
    pronunciation_provider: str
    pronunciation_score: int


class AudioObservationSet(EvaluationModel):
    schema_version: int
    observations: list[AudioObservation]

    @model_validator(mode="after")
    def validate_unique_sample_ids(self) -> AudioObservationSet:
        sample_ids = [observation.sample_id for observation in self.observations]
        if len(set(sample_ids)) != len(sample_ids):
            raise ValueError("audio observation sample IDs must be unique")
        return self
