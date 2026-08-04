package com.pitchcoach.core.session.presentation.dto;

import java.util.UUID;

public record AnalysisStatusResponse(
        UUID practiceSessionId,
        UUID analysisJobId,
        String status,
        String currentStep,
        Integer progress,
        String errorMessage
) {}
