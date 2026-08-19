package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.CurrentPasswordMismatchException;
import com.pitchcoach.core.common.exception.InvalidTokenException;
import com.pitchcoach.core.user.domain.LocalCredential;
import com.pitchcoach.core.user.domain.RefreshToken;
import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.infrastructure.LocalCredentialJpaRepository;
import com.pitchcoach.core.user.infrastructure.RefreshTokenJpaRepository;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import com.pitchcoach.core.user.presentation.dto.WithdrawRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class WithdrawAccountService {

    private final UserJpaRepository userJpaRepository;
    private final LocalCredentialJpaRepository localCredentialJpaRepository;
    private final RefreshTokenJpaRepository refreshTokenJpaRepository;
    private final PasswordEncoder passwordEncoder;

    @Transactional
    public void withdraw(Long userId, WithdrawRequest request) {
        User user = userJpaRepository.findById(userId)
                .orElseThrow(() -> new InvalidTokenException("사용자를 찾을 수 없습니다."));

        localCredentialJpaRepository.findById(userId).ifPresent(credential -> verifyPassword(credential, request));

        user.withdraw();

        refreshTokenJpaRepository.findAllByUserIdAndRevokedAtIsNull(userId)
                .forEach(RefreshToken::revoke);
    }

    private void verifyPassword(LocalCredential credential, WithdrawRequest request) {
        String password = request == null ? null : request.password();
        if (password == null || !passwordEncoder.matches(password, credential.getPasswordHash())) {
            throw new CurrentPasswordMismatchException();
        }
    }
}
