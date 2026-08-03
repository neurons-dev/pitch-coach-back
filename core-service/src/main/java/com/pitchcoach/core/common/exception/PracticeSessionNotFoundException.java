package com.pitchcoach.core.common.exception;

import java.util.UUID;

public class PracticeSessionNotFoundException extends RuntimeException {
    public PracticeSessionNotFoundException(UUID id) {
        super("존재하지 않는 발표 세션입니다: " + id);
    }
}
