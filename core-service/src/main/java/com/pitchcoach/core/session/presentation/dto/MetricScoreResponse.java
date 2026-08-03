package com.pitchcoach.core.session.presentation.dto;

import com.pitchcoach.core.session.infrastructure.dto.AnalysisMetricScoreDto;

public record MetricScoreResponse(
        String metricCode,
        int score,
        Double rawValue,
        String unit
) {
    public static MetricScoreResponse from(AnalysisMetricScoreDto dto) {
        return new MetricScoreResponse(dto.metricCode(), dto.score(), dto.rawValue(), dto.unit());
    }
}
