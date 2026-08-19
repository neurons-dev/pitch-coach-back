package com.pitchcoach.core.user.infrastructure;

import com.pitchcoach.core.common.exception.ProfileImageUploadFailedException;
import com.pitchcoach.core.common.exception.UnsupportedImageFormatException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

import java.io.IOException;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Slf4j
@Component
@RequiredArgsConstructor
public class ProfileImageStorage {

    private static final Map<String, String> ALLOWED_CONTENT_TYPE_EXTENSIONS = Map.of(
            "image/jpeg", ".jpg",
            "image/png", ".png",
            "image/webp", ".webp"
    );

    private final S3Client s3Client;

    @Value("${aws.region}")
    private String region;

    @Value("${aws.s3.bucket}")
    private String bucket;

    public void validateContentType(String contentType) {
        if (contentType == null || !ALLOWED_CONTENT_TYPE_EXTENSIONS.containsKey(contentType.toLowerCase())) {
            throw new UnsupportedImageFormatException(contentType);
        }
    }

    public String upload(Long userId, MultipartFile file) {
        String objectKey = buildObjectKey(userId, file.getContentType());
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
            throw new ProfileImageUploadFailedException(e);
        }
        return buildPublicUrl(objectKey);
    }

    public void deleteIfOwned(String imageUrl) {
        extractObjectKey(imageUrl).ifPresent(objectKey -> {
            try {
                s3Client.deleteObject(DeleteObjectRequest.builder().bucket(bucket).key(objectKey).build());
            } catch (SdkException e) {
                log.warn("기존 프로필 이미지 삭제에 실패했습니다: {}", imageUrl, e);
            }
        });
    }

    private String buildObjectKey(Long userId, String contentType) {
        String extension = ALLOWED_CONTENT_TYPE_EXTENSIONS.get(contentType.toLowerCase());
        return "users/%d/%s%s".formatted(userId, UUID.randomUUID(), extension);
    }

    private String buildPublicUrl(String objectKey) {
        return "https://%s.s3.%s.amazonaws.com/%s".formatted(bucket, region, objectKey);
    }

    private Optional<String> extractObjectKey(String imageUrl) {
        String prefix = buildPublicUrl("");
        if (imageUrl == null || !imageUrl.startsWith(prefix)) {
            return Optional.empty();
        }
        return Optional.of(imageUrl.substring(prefix.length()));
    }
}
