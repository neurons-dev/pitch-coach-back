package com.pitchcoach.core.common.exception;

public class InactiveUserException extends RuntimeException {
    public InactiveUserException(String status) {
        super("비활성화된 사용자입니다: " + status);
    }
}
