package com.pitchcoach.core.session.presentation.dto;

import java.util.UUID;

public record AnalysisStatusResponse(
        UUID practiceSessionId,
        UUID analysisJobId,
        String status,
        String currentStage,
        Integer progressPercent,
        String errorMessage
) {}
