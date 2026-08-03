package com.pitchcoach.core.session.application;

import com.pitchcoach.core.common.exception.PracticeSessionNotFoundException;
import com.pitchcoach.core.session.domain.PracticeSession;
import com.pitchcoach.core.session.infrastructure.PracticeSessionJpaRepository;
import com.pitchcoach.core.session.presentation.dto.PracticeSessionResponse;
import com.pitchcoach.core.session.presentation.dto.UpdatePracticeSessionTitleRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class UpdatePracticeSessionTitleService {

    private final PracticeSessionJpaRepository practiceSessionJpaRepository;

    @Transactional
    public PracticeSessionResponse update(Long userId, UUID sessionId, UpdatePracticeSessionTitleRequest request) {
        PracticeSession session = practiceSessionJpaRepository.findByIdAndUserId(sessionId, userId)
                .orElseThrow(() -> new PracticeSessionNotFoundException(sessionId));

        session.renameTitle(request.title());
        practiceSessionJpaRepository.flush();

        return PracticeSessionResponse.from(session);
    }
}
