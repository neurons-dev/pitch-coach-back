package com.pitchcoach.core.session.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "practice_types")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class PracticeType {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Short id;

    @Column(nullable = false, unique = true)
    private String code;

    @Column(nullable = false)
    private String label;

    @Column(name = "recommended_min_sec")
    private Integer recommendedMinSec;

    @Column(name = "recommended_max_sec")
    private Integer recommendedMaxSec;

    @Column(name = "sort_order", nullable = false)
    private Short sortOrder = 0;

    @Column(name = "is_active", nullable = false)
    private boolean active = true;
}
