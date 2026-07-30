package com.pitchcoach.core.session.application;

import com.pitchcoach.core.common.exception.PracticeSessionNotFoundException;
import com.pitchcoach.core.session.domain.PracticeSession;
import com.pitchcoach.core.session.infrastructure.PracticeSessionJpaRepository;
import com.pitchcoach.core.session.presentation.dto.PracticeSessionResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class GetPracticeSessionService {

    private final PracticeSessionJpaRepository practiceSessionJpaRepository;

    @Transactional(readOnly = true)
    public PracticeSessionResponse get(Long userId, UUID sessionId) {
        PracticeSession session = practiceSessionJpaRepository.findByIdAndUserId(sessionId, userId)
                .orElseThrow(() -> new PracticeSessionNotFoundException(sessionId));

        return PracticeSessionResponse.from(session);
    }
}
