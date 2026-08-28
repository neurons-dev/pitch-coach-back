package com.pitchcoach.core.session.infrastructure.dto;

import java.util.UUID;

public record AnalysisJobCreateRequest(
        UUID sessionId,
        Long userId,
        String title,
        String practiceTypeCode,
        String audioObjectKey,
        String audioContentType,
        Long audioSizeBytes,
        Long durationMs
) {}
