package com.pitchcoach.core.session.application;

import com.pitchcoach.core.session.infrastructure.PracticeTypeJpaRepository;
import com.pitchcoach.core.session.presentation.dto.PracticeTypeResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ListPracticeTypesService {

    private final PracticeTypeJpaRepository practiceTypeJpaRepository;

    @Transactional(readOnly = true)
    public List<PracticeTypeResponse> list() {
        return practiceTypeJpaRepository.findByActiveTrueOrderBySortOrderAsc().stream()
                .map(PracticeTypeResponse::from)
                .toList();
    }
}
