package com.pitchcoach.core.common.exception;

public class UnsupportedAudioFormatException extends RuntimeException {
    public UnsupportedAudioFormatException(String contentType) {
        super("지원하지 않는 오디오 형식입니다: " + contentType);
    }
}
