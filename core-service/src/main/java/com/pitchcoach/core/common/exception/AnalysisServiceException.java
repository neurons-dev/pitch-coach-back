package com.pitchcoach.core.common.exception;

public class AnalysisServiceException extends RuntimeException {
    public AnalysisServiceException(Throwable cause) {
        super("분석 서비스 요청에 실패했습니다.", cause);
    }
}
