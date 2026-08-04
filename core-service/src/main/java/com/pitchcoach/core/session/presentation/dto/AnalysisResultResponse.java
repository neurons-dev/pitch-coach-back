package com.pitchcoach.core.session.presentation.dto;

import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobResultDto;
import com.pitchcoach.core.session.infrastructure.dto.AnalysisMetricScoreDto;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

public record AnalysisResultResponse(
        UUID practiceSessionId,
        UUID analysisJobId,
        int overallScore,
        String coachComment,
        Integer speechRateScore,
        Integer fillerWordScore,
        Integer structureScore,
        Integer deliveryScore,
        List<FeedbackItemResponse> feedback
) {
    public static AnalysisResultResponse from(UUID practiceSessionId, UUID analysisJobId, AnalysisJobResultDto dto) {
        Map<String, Integer> scoresByMetricCode = dto.metricScores().stream()
                .collect(Collectors.toMap(AnalysisMetricScoreDto::metricCode, AnalysisMetricScoreDto::score, (a, b) -> a));

        return new AnalysisResultResponse(
                practiceSessionId,
                analysisJobId,
                dto.overallScore(),
                dto.coachComment(),
                scoresByMetricCode.get("SPEED"),
                scoresByMetricCode.get("FILLER"),
                scoresByMetricCode.get("STRUCTURE"),
                scoresByMetricCode.get("DELIVERY"),
                dto.feedbackItems().stream().map(FeedbackItemResponse::from).toList()
        );
    }
}
