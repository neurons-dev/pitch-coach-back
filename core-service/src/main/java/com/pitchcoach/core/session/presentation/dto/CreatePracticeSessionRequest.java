package com.pitchcoach.core.session.presentation.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreatePracticeSessionRequest(
        @NotBlank @Size(max = 100) String title,
        @NotBlank String practiceTypeCode
) {}
