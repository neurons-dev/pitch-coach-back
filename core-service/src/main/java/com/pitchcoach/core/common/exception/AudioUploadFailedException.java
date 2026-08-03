package com.pitchcoach.core.common.exception;

public class AudioUploadFailedException extends RuntimeException {
    public AudioUploadFailedException(Throwable cause) {
        super("오디오 파일 업로드에 실패했습니다.", cause);
    }
}
