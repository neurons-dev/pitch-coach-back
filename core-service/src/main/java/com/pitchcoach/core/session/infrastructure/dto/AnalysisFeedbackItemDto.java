package com.pitchcoach.core.session.infrastructure.dto;

public record AnalysisFeedbackItemDto(
        String metricCode,
        String itemType,
        String title,
        String description,
        int sortOrder
) {}
