package com.pitchcoach.core.user.presentation.dto;

public record TokenResponse(
        String accessToken,
        String refreshToken
) {}