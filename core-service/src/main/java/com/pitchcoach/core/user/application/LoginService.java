package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.InvalidCredentialsException;
import com.pitchcoach.core.common.security.JwtTokenProvider;
import com.pitchcoach.core.common.security.RefreshTokenGenerator;
import com.pitchcoach.core.user.domain.LocalCredential;
import com.pitchcoach.core.user.domain.RefreshToken;
import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.infrastructure.LocalCredentialJpaRepository;
import com.pitchcoach.core.user.infrastructure.RefreshTokenJpaRepository;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import com.pitchcoach.core.user.presentation.dto.LoginRequest;
import com.pitchcoach.core.user.presentation.dto.TokenResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class LoginService {
    private static final long REFRESH_TOKEN_EXPIRE_DAYS = 14;

    private final UserJpaRepository userJpaRepository;
    private final LocalCredentialJpaRepository localCredentialJpaRepository;
    private final RefreshTokenJpaRepository refreshTokenJpaRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final RefreshTokenGenerator refreshTokenGenerator;

    @Transactional
    public TokenResponse login(LoginRequest request) {
        User user = userJpaRepository.findByEmailIgnoreCase(request.email())
                .orElseThrow(InvalidCredentialsException::new);

        LocalCredential credential = localCredentialJpaRepository.findById(user.getId())
                .orElseThrow(InvalidCredentialsException::new);

        if (!passwordEncoder.matches(request.password(), credential.getPasswordHash())) {
            throw new InvalidCredentialsException();
        }

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