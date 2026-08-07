package com.pitchcoach.core.session.application;

import com.pitchcoach.core.common.exception.InactiveUserException;
import com.pitchcoach.core.common.exception.InvalidTokenException;
import com.pitchcoach.core.common.exception.PracticeTypeNotFoundException;
import com.pitchcoach.core.session.domain.PracticeSession;
import com.pitchcoach.core.session.domain.PracticeType;
import com.pitchcoach.core.session.infrastructure.PracticeSessionJpaRepository;
import com.pitchcoach.core.session.infrastructure.PracticeTypeJpaRepository;
import com.pitchcoach.core.session.presentation.dto.CreatePracticeSessionRequest;
import com.pitchcoach.core.session.presentation.dto.PracticeSessionResponse;
import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.domain.UserStatus;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class CreatePracticeSessionService {

    private final UserJpaRepository userJpaRepository;
    private final PracticeTypeJpaRepository practiceTypeJpaRepository;
    private final PracticeSessionJpaRepository practiceSessionJpaRepository;

    @Transactional
    public PracticeSessionResponse create(Long userId, CreatePracticeSessionRequest request) {
        User user = userJpaRepository.findById(userId)
                .orElseThrow(() -> new InvalidTokenException("사용자를 찾을 수 없습니다."));
        if (user.getStatus() != UserStatus.ACTIVE) {
            throw new InactiveUserException(user.getStatus().name());
        }

        String practiceTypeCode = request.practiceTypeCode().trim().toUpperCase();
        PracticeType practiceType = practiceTypeJpaRepository.findByCodeAndActiveTrue(practiceTypeCode)
                .orElseThrow(() -> new PracticeTypeNotFoundException(practiceTypeCode));

        PracticeSession session = PracticeSession.create(user, practiceType, request.title(), request.targetDurationSeconds());
        practiceSessionJpaRepository.saveAndFlush(session);

        return PracticeSessionResponse.from(session);
    }
}
