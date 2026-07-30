package com.pitchcoach.core.session.presentation.dto;

import com.pitchcoach.core.session.domain.PracticeSession;

import java.time.LocalDateTime;
import java.util.UUID;

public record PracticeSessionResponse(
        UUID id,
        String title,
        String practiceTypeCode,
        String status,
        String audioOriginalName,
        String audioContentType,
        Long audioSizeBytes,
        Long durationMs,
        LocalDateTime recordedAt,
        UUID latestAnalysisJobId,
        String failureReason,
        LocalDateTime analysisCompletedAt,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
    public static PracticeSessionResponse from(PracticeSession session) {
        return new PracticeSessionResponse(
                session.getId(),
                session.getTitle(),
                session.getPracticeType().getCode(),
                session.getStatus().name(),
                session.getAudioOriginalName(),
                session.getAudioContentType(),
                session.getAudioSizeBytes(),
                session.getDurationMs(),
                session.getRecordedAt(),
                session.getLatestAnalysisJobId(),
                session.getFailureReason(),
                session.getAnalysisCompletedAt(),
                session.getCreatedAt(),
                session.getUpdatedAt()
        );
    }
}
