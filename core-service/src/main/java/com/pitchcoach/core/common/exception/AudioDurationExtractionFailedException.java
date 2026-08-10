package com.pitchcoach.core.common.exception;

public class AudioDurationExtractionFailedException extends RuntimeException {
    public AudioDurationExtractionFailedException() {
        super("오디오 파일에서 재생 길이를 추출할 수 없습니다. 파일이 손상되지 않았는지 확인해주세요.");
    }
}
