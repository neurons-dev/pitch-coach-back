package com.pitchcoach.core.session.presentation.dto;

import com.pitchcoach.core.session.domain.PracticeSession;

import java.time.LocalDateTime;
import java.util.UUID;

public record RecentAnalysisResponse(
        UUID analysisId,
        String title,
        LocalDateTime createdAt,
        Long durationSeconds,
        Short totalScore
) {
    public static RecentAnalysisResponse from(PracticeSession session) {
        Long durationMs = session.getDurationMs();
        return new RecentAnalysisResponse(
                session.getLatestAnalysisJobId(),
                session.getTitle(),
                session.getCreatedAt(),
                durationMs == null ? null : durationMs / 1000,
                session.getOverallScore()
        );
    }
}
