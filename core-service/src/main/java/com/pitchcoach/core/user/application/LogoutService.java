package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.InvalidTokenException;
import com.pitchcoach.core.common.security.RefreshTokenGenerator;
import com.pitchcoach.core.user.domain.RefreshToken;
import com.pitchcoach.core.user.infrastructure.RefreshTokenJpaRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class LogoutService {

    private final RefreshTokenJpaRepository refreshTokenJpaRepository;
    private final RefreshTokenGenerator refreshTokenGenerator;

    @Transactional
    public void logout(String rawRefreshToken) {
        String hashed = refreshTokenGenerator.hash(rawRefreshToken);
        RefreshToken savedToken = refreshTokenJpaRepository.findByTokenHash(hashed)
                .orElseThrow(() -> new InvalidTokenException("유효하지 않은 토큰입니다."));

        savedToken.revoke();
    }
}