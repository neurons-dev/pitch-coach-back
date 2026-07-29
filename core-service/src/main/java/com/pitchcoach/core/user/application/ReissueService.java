package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.InvalidTokenException;
import com.pitchcoach.core.common.security.JwtTokenProvider;
import com.pitchcoach.core.common.security.RefreshTokenGenerator;
import com.pitchcoach.core.user.domain.RefreshToken;
import com.pitchcoach.core.user.infrastructure.RefreshTokenJpaRepository;
import com.pitchcoach.core.user.presentation.dto.ReissueRequest;
import com.pitchcoach.core.user.presentation.dto.TokenResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class ReissueService {

    private static final long REFRESH_TOKEN_EXPIRE_DAYS = 14;

    private final RefreshTokenJpaRepository refreshTokenJpaRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final RefreshTokenGenerator refreshTokenGenerator;

    @Transactional
    public TokenResponse reissue(ReissueRequest request) {
        String hashed = refreshTokenGenerator.hash(request.refreshToken());

        RefreshToken savedToken = refreshTokenJpaRepository.findByTokenHash(hashed)
                .orElseThrow(() -> new InvalidTokenException("유효하지 않은 리프레시 토큰입니다."));

        if (savedToken.isRevoked()) {
            throw new InvalidTokenException("이미 폐기된 토큰입니다.");
        }
        if (savedToken.getExpiresAt().isBefore(LocalDateTime.now())) {
            throw new InvalidTokenException("만료된 토큰입니다.");
        }

        savedToken.revoke();

        Long userId = savedToken.getUser().getId();
        String newAccessToken = jwtTokenProvider.createAccessToken(userId);

        String newRawRefreshToken = refreshTokenGenerator.generate();
        String newHashedRefreshToken = refreshTokenGenerator.hash(newRawRefreshToken);

        RefreshToken newRefreshToken = RefreshToken.of(
                savedToken.getUser(),
                newHashedRefreshToken,
                savedToken.getDeviceInfo(),
                LocalDateTime.now().plusDays(REFRESH_TOKEN_EXPIRE_DAYS)
        );
        refreshTokenJpaRepository.save(newRefreshToken);

        return new TokenResponse(newAccessToken, newRawRefreshToken);
    }
}