package com.pitchcoach.core.session.infrastructure;

import com.pitchcoach.core.common.exception.AudioDurationExtractionFailedException;
import com.pitchcoach.core.common.exception.AudioUploadFailedException;
import com.pitchcoach.core.common.exception.UnsupportedAudioFormatException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
@RequiredArgsConstructor
public class AudioStorage {

    private static final Map<String, String> ALLOWED_CONTENT_TYPE_EXTENSIONS = Map.of(
            "audio/mpeg", ".mp3",
            "audio/mp4", ".m4a",
            "audio/x-m4a", ".m4a",
            "audio/aac", ".aac",
            "audio/wav", ".wav",
            "audio/x-wav", ".wav",
            "audio/wave", ".wav"
    );

    private static final long FFPROBE_TIMEOUT_SECONDS = 30;

    private final S3Client s3Client;

    @Value("${aws.s3.bucket}")
    private String bucket;

    public void validateContentType(String contentType) {
        if (contentType == null || !ALLOWED_CONTENT_TYPE_EXTENSIONS.containsKey(contentType.toLowerCase())) {
            throw new UnsupportedAudioFormatException(contentType);
        }
    }

    public UploadedAudio upload(UUID sessionId, MultipartFile file) {
        String objectKey = buildObjectKey(sessionId, file.getContentType());
        Path tempFile = writeToTempFile(file);
        try {
            long durationMs = extractDurationMs(tempFile);
            s3Client.putObject(
                    PutObjectRequest.builder()
                            .bucket(bucket)
                            .key(objectKey)
                            .contentType(file.getContentType())
                            .contentLength(file.getSize())
                            .build(),
                    RequestBody.fromFile(tempFile)
            );
            return new UploadedAudio(objectKey, durationMs);
        } catch (SdkException e) {
            throw new AudioUploadFailedException(e);
        } finally {
            deleteQuietly(tempFile);
        }
    }

    private Path writeToTempFile(MultipartFile file) {
        try {
            Path tempFile = Files.createTempFile("audio-upload-", tempFileSuffix(file.getContentType()));
            file.transferTo(tempFile);
            return tempFile;
        } catch (IOException e) {
            throw new AudioUploadFailedException(e);
        }
    }

    private String tempFileSuffix(String contentType) {
        String extension = ALLOWED_CONTENT_TYPE_EXTENSIONS.get(contentType.toLowerCase());
        return extension == null ? "" : extension;
    }

    private long extractDurationMs(Path audioFile) {
        try {
            Process process = new ProcessBuilder(
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audioFile.toAbsolutePath().toString()
            ).redirectErrorStream(false).start();

            String output = new String(process.getInputStream().readAllBytes()).trim();
            boolean finished = process.waitFor(FFPROBE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                throw new AudioDurationExtractionFailedException();
            }
            if (process.exitValue() != 0 || output.isEmpty()) {
                throw new AudioDurationExtractionFailedException();
            }

            double seconds = Double.parseDouble(output);
            return Math.round(seconds * 1000);
        } catch (IOException | InterruptedException | NumberFormatException e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            log.error("ffprobe로 오디오 길이를 추출하지 못했습니다.", e);
            throw new AudioDurationExtractionFailedException();
        }
    }

    private void deleteQuietly(Path path) {
        try {
            Files.deleteIfExists(path);
        } catch (IOException e) {
            log.warn("임시 오디오 파일 삭제에 실패했습니다: {}", path, e);
        }
    }

    private String buildObjectKey(UUID sessionId, String contentType) {
        String extension = ALLOWED_CONTENT_TYPE_EXTENSIONS.get(contentType.toLowerCase());
        return "sessions/%s/%s%s".formatted(sessionId, UUID.randomUUID(), extension);
    }

    public record UploadedAudio(String objectKey, long durationMs) {}
}
