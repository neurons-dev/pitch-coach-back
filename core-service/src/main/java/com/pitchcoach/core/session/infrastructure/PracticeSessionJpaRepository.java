package com.pitchcoach.core.session.infrastructure;

import com.pitchcoach.core.session.domain.PracticeSession;
import com.pitchcoach.core.session.domain.PracticeSessionStatus;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface PracticeSessionJpaRepository extends JpaRepository<PracticeSession, UUID> {
    Optional<PracticeSession> findByIdAndUserId(UUID id, Long userId);
    Optional<PracticeSession> findByLatestAnalysisJobIdAndUserId(UUID latestAnalysisJobId, Long userId);
    List<PracticeSession> findByUserIdAndStatusOrderByAnalysisCompletedAtDesc(
            Long userId, PracticeSessionStatus status, Pageable pageable);
}
