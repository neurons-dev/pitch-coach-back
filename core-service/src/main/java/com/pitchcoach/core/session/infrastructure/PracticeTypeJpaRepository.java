package com.pitchcoach.core.session.infrastructure;

import com.pitchcoach.core.session.domain.PracticeType;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PracticeTypeJpaRepository extends JpaRepository<PracticeType, Short> {
    Optional<PracticeType> findByCodeAndActiveTrue(String code);
    List<PracticeType> findByActiveTrueOrderBySortOrderAsc();
}
