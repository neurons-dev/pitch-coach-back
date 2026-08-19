package com.pitchcoach.core.common.exception;

public class UnsupportedImageFormatException extends RuntimeException {
    public UnsupportedImageFormatException(String contentType) {
        super("지원하지 않는 이미지 형식입니다: " + contentType);
    }
}
