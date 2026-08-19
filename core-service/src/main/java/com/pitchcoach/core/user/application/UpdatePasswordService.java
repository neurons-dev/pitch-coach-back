package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.CurrentPasswordMismatchException;
import com.pitchcoach.core.common.exception.LocalCredentialNotFoundException;
import com.pitchcoach.core.user.domain.LocalCredential;
import com.pitchcoach.core.user.infrastructure.LocalCredentialJpaRepository;
import com.pitchcoach.core.user.presentation.dto.UpdatePasswordRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class UpdatePasswordService {

    private final LocalCredentialJpaRepository localCredentialJpaRepository;
    private final PasswordEncoder passwordEncoder;

    @Transactional
    public void update(Long userId, UpdatePasswordRequest request) {
        LocalCredential credential = localCredentialJpaRepository.findById(userId)
                .orElseThrow(LocalCredentialNotFoundException::new);

        if (!passwordEncoder.matches(request.currentPassword(), credential.getPasswordHash())) {
            throw new CurrentPasswordMismatchException();
        }

        credential.changePassword(passwordEncoder.encode(request.newPassword()));
    }
}
