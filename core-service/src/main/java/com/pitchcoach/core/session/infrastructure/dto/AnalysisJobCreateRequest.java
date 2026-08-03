package com.pitchcoach.core.session.infrastructure.dto;

import java.util.UUID;

public record AnalysisJobCreateRequest(
        UUID sessionId,
        Long userId,
        String audioObjectKey,
        String audioContentType,
        Long audioSizeBytes,
        Long durationMs
) {}
