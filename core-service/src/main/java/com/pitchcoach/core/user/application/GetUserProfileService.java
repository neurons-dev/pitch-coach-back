package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.InvalidTokenException;
import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import com.pitchcoach.core.user.presentation.dto.UserProfileResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class GetUserProfileService {

    private final UserJpaRepository userJpaRepository;

    @Transactional(readOnly = true)
    public UserProfileResponse getMyProfile(Long userId) {
        User user = userJpaRepository.findById(userId)
                .orElseThrow(() -> new InvalidTokenException("사용자를 찾을 수 없습니다."));
        return UserProfileResponse.from(user);
    }
}
