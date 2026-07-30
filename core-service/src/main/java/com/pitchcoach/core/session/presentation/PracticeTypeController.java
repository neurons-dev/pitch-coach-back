package com.pitchcoach.core.session.presentation;

import com.pitchcoach.core.session.application.ListPracticeTypesService;
import com.pitchcoach.core.session.presentation.dto.PracticeTypeResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Tag(name = "PracticeType", description = "발표 유형")
@RestController
@RequestMapping("/api/practice-types")
@RequiredArgsConstructor
public class PracticeTypeController {

    private final ListPracticeTypesService listPracticeTypesService;

    @Operation(summary = "발표 유형 목록 조회", description = "활성화된 발표 유형 목록을 정렬 순서대로 조회합니다.")
    @GetMapping
    public ResponseEntity<List<PracticeTypeResponse>> list() {
        return ResponseEntity.ok(listPracticeTypesService.list());
    }
}
