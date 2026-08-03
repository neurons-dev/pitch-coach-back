package com.pitchcoach.core.session.application;

import com.pitchcoach.core.common.exception.AnalysisNotFoundException;
import com.pitchcoach.core.session.domain.PracticeSession;
import com.pitchcoach.core.session.infrastructure.AnalysisServiceClient;
import com.pitchcoach.core.session.infrastructure.PracticeSessionJpaRepository;
import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobStatusResponse;
import com.pitchcoach.core.session.presentation.dto.AnalysisStatusResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class GetAnalysisStatusService {

    private final PracticeSessionJpaRepository practiceSessionJpaRepository;
    private final AnalysisServiceClient analysisServiceClient;

    @Transactional
    public AnalysisStatusResponse getStatus(Long userId, UUID analysisJobId) {
        PracticeSession session = practiceSessionJpaRepository.findByLatestAnalysisJobIdAndUserId(analysisJobId, userId)
                .orElseThrow(() -> new AnalysisNotFoundException(analysisJobId));

        AnalysisJobStatusResponse jobStatus = analysisServiceClient.getJobStatus(analysisJobId);
        syncSessionStatus(session, jobStatus);
        practiceSessionJpaRepository.flush();

        return new AnalysisStatusResponse(
                session.getId(),
                jobStatus.analysisJobId(),
                jobStatus.status(),
                jobStatus.currentStage(),
                jobStatus.progressPercent(),
                jobStatus.errorMessage()
        );
    }

    private void syncSessionStatus(PracticeSession session, AnalysisJobStatusResponse jobStatus) {
        if (!session.isAnalysisPending()) {
            return;
        }
        switch (jobStatus.status()) {
            case "completed" -> {
                session.completeAnalysis();
                if (jobStatus.result() != null) {
                    session.updateOverallScore((short) jobStatus.result().overallScore());
                }
            }
            case "failed", "cancelled" -> session.failAnalysis(jobStatus.errorMessage());
            default -> { }
        }
    }
}
