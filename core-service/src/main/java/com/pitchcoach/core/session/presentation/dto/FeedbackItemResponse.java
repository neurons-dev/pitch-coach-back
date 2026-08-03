package com.pitchcoach.core.session.presentation.dto;

import com.pitchcoach.core.session.infrastructure.dto.AnalysisFeedbackItemDto;

public record FeedbackItemResponse(
        String metricCode,
        String itemType,
        String title,
        String description
) {
    public static FeedbackItemResponse from(AnalysisFeedbackItemDto dto) {
        return new FeedbackItemResponse(dto.metricCode(), dto.itemType(), dto.title(), dto.description());
    }
}
