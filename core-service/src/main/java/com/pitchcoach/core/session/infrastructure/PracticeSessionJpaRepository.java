package com.pitchcoach.core.session.infrastructure;

import com.pitchcoach.core.session.domain.PracticeSession;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface PracticeSessionJpaRepository extends JpaRepository<PracticeSession, UUID> {
    Optional<PracticeSession> findByIdAndUserId(UUID id, Long userId);
}
