from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TranscriptWord:
    start_ms: int
    end_ms: int
    text: str
    probability: float


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    avg_logprob: float
    words: list[TranscriptWord] = field(default_factory=list)


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str
    model_version: str
    duration_ms: int
    segments: list[TranscriptSegment] = field(default_factory=list)


@dataclass(frozen=True)
class DownloadedAudio:
    path: Path
    content_type: str
    size_bytes: int
    duration_ms: int


class AudioStorage(Protocol):
    def download(self, object_key: str) -> DownloadedAudio: ...


class AudioNormalizer(Protocol):
    def normalize(self, input_path: Path) -> Path: ...


class SpeechTranscriber(Protocol):
    def transcribe(self, audio_path: Path, *, language: str) -> Transcript: ...
