package com.pitchcoach.core.session.presentation;

import com.pitchcoach.core.session.application.GetAnalysisStatusService;
import com.pitchcoach.core.session.presentation.dto.AnalysisStatusResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@Tag(name = "Analysis", description = "발표 분석")
@RestController
@RequestMapping("/api/analyses")
@RequiredArgsConstructor
public class AnalysisController {

    private final GetAnalysisStatusService getAnalysisStatusService;

    @Operation(summary = "분석 진행 상태 조회", description = "본인 소유 세션의 분석 작업 진행 상태를 조회합니다.")
    @GetMapping("/{analysisJobId}/status")
    public ResponseEntity<AnalysisStatusResponse> getStatus(
            @AuthenticationPrincipal Long userId,
            @PathVariable UUID analysisJobId
    ) {
        return ResponseEntity.ok(getAnalysisStatusService.getStatus(userId, analysisJobId));
    }
}
