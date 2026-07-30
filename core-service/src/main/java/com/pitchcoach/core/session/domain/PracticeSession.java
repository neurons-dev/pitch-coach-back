package com.pitchcoach.core.session.domain;

import com.pitchcoach.core.user.domain.User;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "practice_sessions")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class PracticeSession {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "practice_type_id", nullable = false)
    private PracticeType practiceType;

    @Column(nullable = false)
    private String title;

    @Convert(converter = PracticeSessionStatusConverter.class)
    @Column(nullable = false)
    private PracticeSessionStatus status = PracticeSessionStatus.CREATED;

    @Column(name = "audio_object_key")
    private String audioObjectKey;

    @Column(name = "audio_original_name")
    private String audioOriginalName;

    @Column(name = "audio_content_type")
    private String audioContentType;

    @Column(name = "audio_size_bytes")
    private Long audioSizeBytes;

    @Column(name = "duration_ms")
    private Long durationMs;

    @Column(name = "recorded_at")
    private LocalDateTime recordedAt;

    @Column(name = "latest_analysis_job_id")
    private UUID latestAnalysisJobId;

    @Column(name = "failure_reason")
    private String failureReason;

    @Column(name = "analysis_completed_at")
    private LocalDateTime analysisCompletedAt;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    public static PracticeSession create(User user, PracticeType practiceType, String title) {
        PracticeSession session = new PracticeSession();
        session.user = user;
        session.practiceType = practiceType;
        session.title = title;
        session.status = PracticeSessionStatus.CREATED;
        return session;
    }

    public void renameTitle(String title) {
        this.title = title;
    }

    public boolean canUploadAudio() {
        return status == PracticeSessionStatus.CREATED || status == PracticeSessionStatus.FAILED;
    }

    public void completeAudioUpload(
            String audioObjectKey,
            String audioOriginalName,
            String audioContentType,
            long audioSizeBytes,
            long durationMs
    ) {
        this.audioObjectKey = audioObjectKey;
        this.audioOriginalName = audioOriginalName;
        this.audioContentType = audioContentType;
        this.audioSizeBytes = audioSizeBytes;
        this.durationMs = durationMs;
        this.recordedAt = LocalDateTime.now();
        this.status = PracticeSessionStatus.UPLOADED;
    }

    public boolean canRequestAnalysis() {
        return status == PracticeSessionStatus.UPLOADED;
    }

    public void requestAnalysis(UUID analysisJobId) {
        this.latestAnalysisJobId = analysisJobId;
        this.status = PracticeSessionStatus.ANALYSIS_REQUESTED;
    }

    public boolean isAnalysisPending() {
        return status == PracticeSessionStatus.ANALYSIS_REQUESTED;
    }

    public void completeAnalysis() {
        this.status = PracticeSessionStatus.COMPLETED;
        this.analysisCompletedAt = LocalDateTime.now();
    }

    public void failAnalysis(String reason) {
        this.status = PracticeSessionStatus.FAILED;
        this.failureReason = reason;
        this.analysisCompletedAt = LocalDateTime.now();
    }
}
