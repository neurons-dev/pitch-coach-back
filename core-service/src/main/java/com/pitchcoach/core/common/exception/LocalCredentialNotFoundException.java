package com.pitchcoach.core.common.exception;

public class LocalCredentialNotFoundException extends RuntimeException {
    public LocalCredentialNotFoundException() {
        super("소셜 로그인 계정은 비밀번호를 변경할 수 없습니다.");
    }
}
