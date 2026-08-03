package com.pitchcoach.core.session.application;

import com.pitchcoach.core.common.exception.InvalidPracticeSessionStateException;
import com.pitchcoach.core.common.exception.PracticeSessionNotFoundException;
import com.pitchcoach.core.session.domain.PracticeSession;
import com.pitchcoach.core.session.infrastructure.AudioStorage;
import com.pitchcoach.core.session.infrastructure.PracticeSessionJpaRepository;
import com.pitchcoach.core.session.presentation.dto.PracticeSessionResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class UploadPracticeSessionAudioService {

    private final PracticeSessionJpaRepository practiceSessionJpaRepository;
    private final AudioStorage audioStorage;

    @Transactional
    public PracticeSessionResponse upload(Long userId, UUID sessionId, MultipartFile file, long durationMs) {
        PracticeSession session = practiceSessionJpaRepository.findByIdAndUserId(sessionId, userId)
                .orElseThrow(() -> new PracticeSessionNotFoundException(sessionId));

        if (!session.canUploadAudio()) {
            throw new InvalidPracticeSessionStateException(
                    "현재 세션 상태(%s)에서는 음성 파일을 업로드할 수 없습니다.".formatted(session.getStatus())
            );
        }

        audioStorage.validateContentType(file.getContentType());
        String objectKey = audioStorage.upload(sessionId, file);

        session.completeAudioUpload(
                objectKey,
                file.getOriginalFilename(),
                file.getContentType(),
                file.getSize(),
                durationMs
        );
        practiceSessionJpaRepository.flush();

        return PracticeSessionResponse.from(session);
    }
}
