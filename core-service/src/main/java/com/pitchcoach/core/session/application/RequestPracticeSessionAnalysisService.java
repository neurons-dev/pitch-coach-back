package com.pitchcoach.core.session.application;

import com.pitchcoach.core.common.exception.InvalidPracticeSessionStateException;
import com.pitchcoach.core.common.exception.PracticeSessionNotFoundException;
import com.pitchcoach.core.session.domain.PracticeSession;
import com.pitchcoach.core.session.infrastructure.AnalysisServiceClient;
import com.pitchcoach.core.session.infrastructure.PracticeSessionJpaRepository;
import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobCreateRequest;
import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobCreateResponse;
import com.pitchcoach.core.session.presentation.dto.PracticeSessionResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class RequestPracticeSessionAnalysisService {

    private final PracticeSessionJpaRepository practiceSessionJpaRepository;
    private final AnalysisServiceClient analysisServiceClient;

    @Transactional
    public PracticeSessionResponse request(Long userId, UUID sessionId) {
        PracticeSession session = practiceSessionJpaRepository.findByIdAndUserId(sessionId, userId)
                .orElseThrow(() -> new PracticeSessionNotFoundException(sessionId));

        if (!session.canRequestAnalysis()) {
            throw new InvalidPracticeSessionStateException(
                    "현재 세션 상태(%s)에서는 분석을 요청할 수 없습니다.".formatted(session.getStatus())
            );
        }

        AnalysisJobCreateRequest request = new AnalysisJobCreateRequest(
                session.getId(),
                session.getUser().getId(),
                session.getAudioObjectKey(),
                session.getAudioContentType(),
                session.getAudioSizeBytes(),
                session.getDurationMs()
        );
        // audioObjectKey는 업로드마다 새로 발급되는 고유 값이라, 세션당 idempotency key로 재사용해도
        // 재업로드 후 재요청 시 이전 요청과 충돌하지 않는다.
        AnalysisJobCreateResponse response = analysisServiceClient.createJob(request, session.getAudioObjectKey());

        session.requestAnalysis(response.analysisJobId());
        practiceSessionJpaRepository.flush();

        return PracticeSessionResponse.from(session);
    }
}
