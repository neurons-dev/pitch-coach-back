package com.pitchcoach.core.user.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

@Entity
@Table(name = "local_credentials")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class LocalCredential {

    @Id
    @Column(name = "user_id")
    private Long userId;

    @OneToOne(fetch = FetchType.LAZY)
    @MapsId
    @JoinColumn(name = "user_id")
    private User user;

    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    public static LocalCredential of(User user, String passwordHash) {
        LocalCredential credential = new LocalCredential();
        credential.user = user;
        credential.passwordHash = passwordHash;
        return credential;
    }

    public void changePassword(String newPasswordHash) {
        this.passwordHash = newPasswordHash;
    }
}