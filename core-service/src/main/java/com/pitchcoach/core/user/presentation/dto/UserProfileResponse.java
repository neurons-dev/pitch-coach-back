package com.pitchcoach.core.user.presentation.dto;

import com.pitchcoach.core.user.domain.User;

import java.time.LocalDateTime;

public record UserProfileResponse(
        Long userId,
        String name,
        String email,
        String profileImageUrl,
        Short level,
        String status,
        LocalDateTime createdAt
) {
    public static UserProfileResponse from(User user) {
        return new UserProfileResponse(
                user.getId(),
                user.getNickname(),
                user.getEmail(),
                user.getProfileImageUrl(),
                user.getLevel(),
                user.getStatus().name(),
                user.getCreatedAt()
        );
    }
}
