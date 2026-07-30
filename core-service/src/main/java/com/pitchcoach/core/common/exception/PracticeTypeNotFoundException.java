package com.pitchcoach.core.common.exception;

public class PracticeTypeNotFoundException extends RuntimeException {
    public PracticeTypeNotFoundException(String code) {
        super("존재하지 않는 발표 유형입니다: " + code);
    }
}
