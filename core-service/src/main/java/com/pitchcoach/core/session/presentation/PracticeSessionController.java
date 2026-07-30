package com.pitchcoach.core.session.presentation;

import com.pitchcoach.core.session.application.CreatePracticeSessionService;
import com.pitchcoach.core.session.application.GetPracticeSessionService;
import com.pitchcoach.core.session.application.UpdatePracticeSessionTitleService;
import com.pitchcoach.core.session.presentation.dto.CreatePracticeSessionRequest;
import com.pitchcoach.core.session.presentation.dto.PracticeSessionResponse;
import com.pitchcoach.core.session.presentation.dto.UpdatePracticeSessionTitleRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.net.URI;
import java.util.UUID;

@Tag(name = "PracticeSession", description = "발표 연습 세션")
@RestController
@RequestMapping("/api/practice-sessions")
@RequiredArgsConstructor
public class PracticeSessionController {

    private final CreatePracticeSessionService createPracticeSessionService;
    private final UpdatePracticeSessionTitleService updatePracticeSessionTitleService;
    private final GetPracticeSessionService getPracticeSessionService;

    @Operation(summary = "발표 연습 세션 단건 조회", description = "본인 소유의 발표 연습 세션을 조회합니다.")
    @GetMapping("/{sessionId}")
    public ResponseEntity<PracticeSessionResponse> get(
            @AuthenticationPrincipal Long userId,
            @PathVariable UUID sessionId
    ) {
        return ResponseEntity.ok(getPracticeSessionService.get(userId, sessionId));
    }

    @Operation(summary = "발표 연습 세션 생성", description = "발표 제목과 유형을 입력해 새 발표 연습 세션을 생성합니다.")
    @PostMapping
    public ResponseEntity<PracticeSessionResponse> create(
            @AuthenticationPrincipal Long userId,
            @Valid @RequestBody CreatePracticeSessionRequest request
    ) {
        PracticeSessionResponse response = createPracticeSessionService.create(userId, request);
        return ResponseEntity.created(URI.create("/api/practice-sessions/" + response.id())).body(response);
    }

    @Operation(summary = "발표 연습 세션 제목 수정", description = "본인 소유의 발표 연습 세션 제목을 수정합니다.")
    @PatchMapping("/{sessionId}")
    public ResponseEntity<PracticeSessionResponse> updateTitle(
            @AuthenticationPrincipal Long userId,
            @PathVariable UUID sessionId,
            @Valid @RequestBody UpdatePracticeSessionTitleRequest request
    ) {
        return ResponseEntity.ok(updatePracticeSessionTitleService.update(userId, sessionId, request));
    }
}
