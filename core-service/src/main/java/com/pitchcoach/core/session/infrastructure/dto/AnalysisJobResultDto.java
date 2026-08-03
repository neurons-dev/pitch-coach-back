package com.pitchcoach.core.session.infrastructure.dto;

import java.util.List;

public record AnalysisJobResultDto(
        int overallScore,
        String coachComment,
        List<AnalysisMetricScoreDto> metricScores,
        List<AnalysisFeedbackItemDto> feedbackItems
) {}
