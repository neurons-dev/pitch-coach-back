package com.pitchcoach.core.user.presentation;

import com.pitchcoach.core.user.application.GetUserProfileService;
import com.pitchcoach.core.user.application.UpdatePasswordService;
import com.pitchcoach.core.user.application.UpdateProfileImageService;
import com.pitchcoach.core.user.presentation.dto.UpdatePasswordRequest;
import com.pitchcoach.core.user.presentation.dto.UserProfileResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@Tag(name = "User", description = "사용자 프로필")
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final GetUserProfileService getUserProfileService;
    private final UpdateProfileImageService updateProfileImageService;
    private final UpdatePasswordService updatePasswordService;

    @Operation(summary = "내 프로필 조회", description = "로그인한 사용자 본인의 프로필 정보를 조회합니다.")
    @GetMapping("/me")
    public ResponseEntity<UserProfileResponse> getMyProfile(@AuthenticationPrincipal Long userId) {
        return ResponseEntity.ok(getUserProfileService.getMyProfile(userId));
    }

    @Operation(summary = "프로필 이미지 업로드", description = "본인의 프로필 이미지를 업로드합니다. 기존 이미지가 있으면(직접 업로드한 것에 한해) 삭제됩니다.")
    @PostMapping("/me/profile-image")
    public ResponseEntity<UserProfileResponse> updateProfileImage(
            @AuthenticationPrincipal Long userId,
            @RequestParam("file") MultipartFile file
    ) {
        return ResponseEntity.ok(updateProfileImageService.update(userId, file));
    }

    @Operation(summary = "비밀번호 변경", description = "로컬 계정의 비밀번호를 변경합니다. 소셜 로그인 전용 계정은 사용할 수 없습니다.")
    @PatchMapping("/me/password")
    public ResponseEntity<Void> updatePassword(
            @AuthenticationPrincipal Long userId,
            @Valid @RequestBody UpdatePasswordRequest request
    ) {
        updatePasswordService.update(userId, request);
        return ResponseEntity.noContent().build();
    }
}
