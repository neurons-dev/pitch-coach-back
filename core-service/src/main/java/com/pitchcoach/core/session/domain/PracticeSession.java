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
}
