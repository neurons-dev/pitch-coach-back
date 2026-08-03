package com.pitchcoach.core.session.infrastructure.dto;

public record AnalysisMetricScoreDto(
        String metricCode,
        int score,
        Double rawValue,
        String unit
) {}
