package com.pitchcoach.core.user.infrastructure;

import com.pitchcoach.core.user.domain.LocalCredential;
import org.springframework.data.jpa.repository.JpaRepository;

public interface LocalCredentialJpaRepository extends JpaRepository<LocalCredential, Long> {
}