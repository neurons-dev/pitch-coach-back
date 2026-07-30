package com.pitchcoach.core.session.presentation.dto;

import com.pitchcoach.core.session.domain.PracticeSession;

import java.time.LocalDateTime;
import java.util.UUID;

public record PracticeSessionResponse(
        UUID id,
        String title,
        String practiceTypeCode,
        String status,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
    public static PracticeSessionResponse from(PracticeSession session) {
        return new PracticeSessionResponse(
                session.getId(),
                session.getTitle(),
                session.getPracticeType().getCode(),
                session.getStatus().name(),
                session.getCreatedAt(),
                session.getUpdatedAt()
        );
    }
}
