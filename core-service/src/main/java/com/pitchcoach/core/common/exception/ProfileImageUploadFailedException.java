package com.pitchcoach.core.common.exception;

public class ProfileImageUploadFailedException extends RuntimeException {
    public ProfileImageUploadFailedException(Throwable cause) {
        super("프로필 이미지 업로드에 실패했습니다.", cause);
    }
}
