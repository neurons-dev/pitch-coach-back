package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.InvalidTokenException;
import com.pitchcoach.core.common.security.JwtTokenProvider;
import com.pitchcoach.core.common.security.OAuthLoginCodeStore;
import com.pitchcoach.core.common.security.RefreshTokenGenerator;
import com.pitchcoach.core.user.domain.RefreshToken;
import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.infrastructure.RefreshTokenJpaRepository;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import com.pitchcoach.core.user.presentation.dto.TokenResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class OAuthExchangeService {

    private static final long REFRESH_TOKEN_EXPIRE_DAYS = 14;
    private static final String INVALID_CODE_MESSAGE = "유효하지 않거나 만료된 코드입니다.";

    private final OAuthLoginCodeStore oAuthLoginCodeStore;
    private final UserJpaRepository userJpaRepository;
    private final RefreshTokenJpaRepository refreshTokenJpaRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final RefreshTokenGenerator refreshTokenGenerator;

    @Transactional
    public TokenResponse exchange(String code) {
        Long userId = oAuthLoginCodeStore.consume(code)
                .orElseThrow(() -> new InvalidTokenException(INVALID_CODE_MESSAGE));

        User user = userJpaRepository.findById(userId)
                .orElseThrow(() -> new InvalidTokenException(INVALID_CODE_MESSAGE));

        String accessToken = jwtTokenProvider.createAccessToken(user.getId());

        String rawRefreshToken = refreshTokenGenerator.generate();
        String hashedRefreshToken = refreshTokenGenerator.hash(rawRefreshToken);

        RefreshToken refreshToken = RefreshToken.of(
                user,
                hashedRefreshToken,
                null,
                LocalDateTime.now().plusDays(REFRESH_TOKEN_EXPIRE_DAYS)
        );
        refreshTokenJpaRepository.save(refreshToken);

        return new TokenResponse(accessToken, rawRefreshToken);
    }
}
