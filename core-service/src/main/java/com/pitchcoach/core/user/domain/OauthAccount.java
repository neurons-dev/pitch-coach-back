package com.pitchcoach.core.user.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;

@Entity
@Table(name = "oauth_accounts")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class OauthAccount {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Convert(converter = OauthProviderConverter.class)
    @Column(nullable = false)
    private OauthProvider provider;

    @Column(name = "provider_uid", nullable = false)
    private String providerUid;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    public static OauthAccount of(User user, OauthProvider provider, String providerUid) {
        OauthAccount account = new OauthAccount();
        account.user = user;
        account.provider = provider;
        account.providerUid = providerUid;
        return account;
    }
}