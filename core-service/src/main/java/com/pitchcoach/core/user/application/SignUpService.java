package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.DuplicateEmailException;
import com.pitchcoach.core.user.domain.LocalCredential;
import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.infrastructure.LocalCredentialJpaRepository;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import com.pitchcoach.core.user.presentation.dto.SignUpRequest;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class SignUpService {

    private final UserJpaRepository userJpaRepository;
    private final LocalCredentialJpaRepository localCredentialJpaRepository;
    private final PasswordEncoder passwordEncoder;

    @Transactional
    public Long signUp(SignUpRequest request) {
        if (userJpaRepository.existsByEmailIgnoreCase(request.email())) {
            throw new DuplicateEmailException(request.email());
        }

        User user = User.createLocal(request.email(), request.nickname());
        userJpaRepository.save(user);

        String hashed = passwordEncoder.encode(request.password());
        LocalCredential credential = LocalCredential.of(user, hashed);
        localCredentialJpaRepository.save(credential);

        return user.getId();
    }
}