package com.pitchcoach.core.session.presentation.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UpdatePracticeSessionTitleRequest(
        @NotBlank @Size(max = 100) String title
) {}
