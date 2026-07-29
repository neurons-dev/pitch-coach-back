package com.pitchcoach.core.user.infrastructure;

public interface OAuth2UserInfo {
    String getProviderUid();
    String getEmail();
    String getNickname();
    String getProfileImageUrl();
    boolean isEmailVerified();
}