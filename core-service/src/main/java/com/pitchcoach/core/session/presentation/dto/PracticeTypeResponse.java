package com.pitchcoach.core.session.presentation.dto;

import com.pitchcoach.core.session.domain.PracticeType;

public record PracticeTypeResponse(
        String code,
        String label,
        Integer recommendedMinSec,
        Integer recommendedMaxSec
) {
    public static PracticeTypeResponse from(PracticeType practiceType) {
        return new PracticeTypeResponse(
                practiceType.getCode(),
                practiceType.getLabel(),
                practiceType.getRecommendedMinSec(),
                practiceType.getRecommendedMaxSec()
        );
    }
}
