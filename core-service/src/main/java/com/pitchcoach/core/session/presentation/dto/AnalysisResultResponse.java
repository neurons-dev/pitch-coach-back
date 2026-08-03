package com.pitchcoach.core.session.presentation.dto;

import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobResultDto;

import java.util.List;
import java.util.UUID;

public record AnalysisResultResponse(
        UUID practiceSessionId,
        UUID analysisJobId,
        int overallScore,
        String coachComment,
        List<MetricScoreResponse> metricScores,
        List<FeedbackItemResponse> feedbackItems
) {
    public static AnalysisResultResponse from(UUID practiceSessionId, UUID analysisJobId, AnalysisJobResultDto dto) {
        return new AnalysisResultResponse(
                practiceSessionId,
                analysisJobId,
                dto.overallScore(),
                dto.coachComment(),
                dto.metricScores().stream().map(MetricScoreResponse::from).toList(),
                dto.feedbackItems().stream().map(FeedbackItemResponse::from).toList()
        );
    }
}
