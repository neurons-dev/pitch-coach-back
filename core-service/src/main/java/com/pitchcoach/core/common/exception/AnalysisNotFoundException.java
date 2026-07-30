package com.pitchcoach.core.common.exception;

import java.util.UUID;

public class AnalysisNotFoundException extends RuntimeException {
    public AnalysisNotFoundException(UUID analysisJobId) {
        super("존재하지 않는 분석 작업입니다: " + analysisJobId);
    }
}
