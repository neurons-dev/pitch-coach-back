package com.pitchcoach.core.session.infrastructure.dto;

import java.util.UUID;

public record AnalysisJobCreateResponse(
        UUID analysisJobId,
        String status
) {}
