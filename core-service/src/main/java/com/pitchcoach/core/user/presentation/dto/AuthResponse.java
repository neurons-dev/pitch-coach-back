package com.pitchcoach.core.user.presentation.dto;

public record AuthResponse(
        Long userId,
        String name,
        String email,
        String accessToken,
        String refreshToken
) {}
