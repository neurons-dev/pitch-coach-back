package com.pitchcoach.core.session.application;

import com.pitchcoach.core.common.exception.AnalysisNotFoundException;
import com.pitchcoach.core.common.exception.InvalidPracticeSessionStateException;
import com.pitchcoach.core.session.domain.PracticeSession;
import com.pitchcoach.core.session.infrastructure.AnalysisServiceClient;
import com.pitchcoach.core.session.infrastructure.PracticeSessionJpaRepository;
import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobResultDto;
import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobStatusResponse;
import com.pitchcoach.core.session.presentation.dto.AnalysisResultResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Set;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class GetAnalysisResultService {

    private static final Set<String> TERMINAL_FAILURE_STATUSES = Set.of("failed", "cancelled");

    private final PracticeSessionJpaRepository practiceSessionJpaRepository;
    private final AnalysisServiceClient analysisServiceClient;

    // 실패 상태 동기화(failAnalysis)를 커밋한 뒤에도 409를 반환해야 하므로,
    // 이 예외에 대해서는 롤백하지 않도록 명시한다.
    @Transactional(noRollbackFor = InvalidPracticeSessionStateException.class)
    public AnalysisResultResponse getResult(Long userId, UUID analysisJobId) {
        PracticeSession session = practiceSessionJpaRepository.findByLatestAnalysisJobIdAndUserId(analysisJobId, userId)
                .orElseThrow(() -> new AnalysisNotFoundException(analysisJobId));

        // 로컬 캐시(session.status)가 아니라 analysis-service의 최신 상태를 기준으로 판단한다.
        // /status를 먼저 폴링하지 않고 /result를 바로 호출해도 정상 동작해야 하기 때문.
        AnalysisJobStatusResponse jobStatus = analysisServiceClient.getJobStatus(analysisJobId);
        AnalysisJobResultDto result = jobStatus.result();

        if (result == null) {
            if (session.isAnalysisPending() && TERMINAL_FAILURE_STATUSES.contains(jobStatus.status())) {
                session.failAnalysis(jobStatus.errorMessage());
                practiceSessionJpaRepository.flush();
                throw new InvalidPracticeSessionStateException(
                        "분석이 실패했습니다: %s".formatted(jobStatus.errorMessage())
                );
            }
            throw new InvalidPracticeSessionStateException(
                    "아직 분석이 진행 중입니다. 현재 상태: %s".formatted(jobStatus.status())
            );
        }

        if (session.isAnalysisPending()) {
            session.completeAnalysis();
        }
        session.updateOverallScore((short) result.overallScore());
        practiceSessionJpaRepository.flush();

        return AnalysisResultResponse.from(session.getId(), analysisJobId, result);
    }
}
