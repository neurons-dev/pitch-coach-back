package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.DuplicateEmailException;
import com.pitchcoach.core.common.security.JwtTokenProvider;
import com.pitchcoach.core.common.security.RefreshTokenGenerator;
import com.pitchcoach.core.user.domain.LocalCredential;
import com.pitchcoach.core.user.domain.RefreshToken;
import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.infrastructure.LocalCredentialJpaRepository;
import com.pitchcoach.core.user.infrastructure.RefreshTokenJpaRepository;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import com.pitchcoach.core.user.presentation.dto.AuthResponse;
import com.pitchcoach.core.user.presentation.dto.SignUpRequest;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class SignUpService {

    private static final long REFRESH_TOKEN_EXPIRE_DAYS = 14;

    private final UserJpaRepository userJpaRepository;
    private final LocalCredentialJpaRepository localCredentialJpaRepository;
    private final RefreshTokenJpaRepository refreshTokenJpaRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final RefreshTokenGenerator refreshTokenGenerator;

    @Transactional
    public AuthResponse signUp(SignUpRequest request) {
        if (userJpaRepository.existsByEmailIgnoreCase(request.email())) {
            throw new DuplicateEmailException(request.email());
        }

        User user = User.createLocal(request.email(), request.nickname());
        userJpaRepository.save(user);

        String hashed = passwordEncoder.encode(request.password());
        LocalCredential credential = LocalCredential.of(user, hashed);
        localCredentialJpaRepository.save(credential);

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

        return new AuthResponse(user.getId(), user.getNickname(), user.getEmail(), accessToken, rawRefreshToken);
    }
}