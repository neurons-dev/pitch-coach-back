package com.pitchcoach.core.session.infrastructure.dto;

import java.util.UUID;

public record AnalysisJobStatusResponse(
        UUID analysisJobId,
        String status,
        String currentStage,
        Integer progressPercent,
        String errorCode,
        String errorMessage,
        AnalysisJobResultDto result
) {}
