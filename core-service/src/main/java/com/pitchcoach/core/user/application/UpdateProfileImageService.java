package com.pitchcoach.core.user.application;

import com.pitchcoach.core.common.exception.InvalidTokenException;
import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.infrastructure.ProfileImageStorage;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import com.pitchcoach.core.user.presentation.dto.UserProfileResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

@Service
@RequiredArgsConstructor
public class UpdateProfileImageService {

    private final UserJpaRepository userJpaRepository;
    private final ProfileImageStorage profileImageStorage;

    @Transactional
    public UserProfileResponse update(Long userId, MultipartFile file) {
        User user = userJpaRepository.findById(userId)
                .orElseThrow(() -> new InvalidTokenException("사용자를 찾을 수 없습니다."));

        profileImageStorage.validateContentType(file.getContentType());
        String previousImageUrl = user.getProfileImageUrl();

        String newImageUrl = profileImageStorage.upload(userId, file);
        user.updateProfileImageUrl(newImageUrl);

        profileImageStorage.deleteIfOwned(previousImageUrl);

        return UserProfileResponse.from(user);
    }
}
