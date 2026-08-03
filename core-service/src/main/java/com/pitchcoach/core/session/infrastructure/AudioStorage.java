package com.pitchcoach.core.session.infrastructure;

import com.pitchcoach.core.common.exception.AudioUploadFailedException;
import com.pitchcoach.core.common.exception.UnsupportedAudioFormatException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

import java.io.IOException;
import java.util.Map;
import java.util.UUID;

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

    private final S3Client s3Client;

    @Value("${aws.s3.bucket}")
    private String bucket;

    public void validateContentType(String contentType) {
        if (contentType == null || !ALLOWED_CONTENT_TYPE_EXTENSIONS.containsKey(contentType.toLowerCase())) {
            throw new UnsupportedAudioFormatException(contentType);
        }
    }

    public String upload(UUID sessionId, MultipartFile file) {
        String objectKey = buildObjectKey(sessionId, file.getContentType());
        try {
            s3Client.putObject(
                    PutObjectRequest.builder()
                            .bucket(bucket)
                            .key(objectKey)
                            .contentType(file.getContentType())
                            .contentLength(file.getSize())
                            .build(),
                    RequestBody.fromInputStream(file.getInputStream(), file.getSize())
            );
        } catch (IOException | SdkException e) {
            throw new AudioUploadFailedException(e);
        }
        return objectKey;
    }

    private String buildObjectKey(UUID sessionId, String contentType) {
        String extension = ALLOWED_CONTENT_TYPE_EXTENSIONS.get(contentType.toLowerCase());
        return "sessions/%s/%s%s".formatted(sessionId, UUID.randomUUID(), extension);
    }
}
