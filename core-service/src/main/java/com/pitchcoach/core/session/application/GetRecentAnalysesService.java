package com.pitchcoach.core.session.application;

import com.pitchcoach.core.session.domain.PracticeSessionStatus;
import com.pitchcoach.core.session.infrastructure.PracticeSessionJpaRepository;
import com.pitchcoach.core.session.presentation.dto.RecentAnalysisResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class GetRecentAnalysesService {

    private final PracticeSessionJpaRepository practiceSessionJpaRepository;

    @Transactional(readOnly = true)
    public List<RecentAnalysisResponse> getRecent(Long userId, int limit) {
        return practiceSessionJpaRepository
                .findByUserIdAndStatusOrderByAnalysisCompletedAtDesc(
                        userId, PracticeSessionStatus.COMPLETED, PageRequest.of(0, limit))
                .stream()
                .map(RecentAnalysisResponse::from)
                .toList();
    }
}
