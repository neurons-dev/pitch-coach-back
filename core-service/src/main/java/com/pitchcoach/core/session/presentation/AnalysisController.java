package com.pitchcoach.core.session.presentation;

import com.pitchcoach.core.session.application.GetAnalysisResultService;
import com.pitchcoach.core.session.application.GetAnalysisStatusService;
import com.pitchcoach.core.session.application.GetRecentAnalysesService;
import com.pitchcoach.core.session.presentation.dto.AnalysisResultResponse;
import com.pitchcoach.core.session.presentation.dto.AnalysisStatusResponse;
import com.pitchcoach.core.session.presentation.dto.RecentAnalysisResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Positive;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@Tag(name = "Analysis", description = "발표 분석")
@RestController
@RequestMapping("/api/analyses")
@RequiredArgsConstructor
@Validated
public class AnalysisController {

    private final GetAnalysisStatusService getAnalysisStatusService;
    private final GetAnalysisResultService getAnalysisResultService;
    private final GetRecentAnalysesService getRecentAnalysesService;

    @Operation(summary = "최근 분석 결과 조회", description = "본인 소유 세션 중 분석이 완료된 것을 최신순으로 조회합니다.")
    @GetMapping("/recent")
    public ResponseEntity<List<RecentAnalysisResponse>> getRecent(
            @AuthenticationPrincipal Long userId,
            @RequestParam(defaultValue = "4") @Positive int limit
    ) {
        return ResponseEntity.ok(getRecentAnalysesService.getRecent(userId, limit));
    }

    @Operation(summary = "분석 진행 상태 조회", description = "본인 소유 세션의 분석 작업 진행 상태를 조회합니다.")
    @GetMapping("/{analysisJobId}/status")
    public ResponseEntity<AnalysisStatusResponse> getStatus(
            @AuthenticationPrincipal Long userId,
            @PathVariable UUID analysisJobId
    ) {
        return ResponseEntity.ok(getAnalysisStatusService.getStatus(userId, analysisJobId));
    }

    @Operation(summary = "분석 결과 조회", description = "본인 소유 세션의 분석 결과(점수·코치 코멘트·피드백)를 조회합니다. 분석이 완료된 상태에서만 조회할 수 있습니다.")
    @GetMapping("/{analysisJobId}/result")
    public ResponseEntity<AnalysisResultResponse> getResult(
            @AuthenticationPrincipal Long userId,
            @PathVariable UUID analysisJobId
    ) {
        return ResponseEntity.ok(getAnalysisResultService.getResult(userId, analysisJobId));
    }
}
