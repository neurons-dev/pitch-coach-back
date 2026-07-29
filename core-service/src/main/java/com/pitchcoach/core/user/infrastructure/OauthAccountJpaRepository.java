package com.pitchcoach.core.user.infrastructure;

import com.pitchcoach.core.user.domain.OauthAccount;
import com.pitchcoach.core.user.domain.OauthProvider;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface OauthAccountJpaRepository extends JpaRepository<OauthAccount, Long> {
    Optional<OauthAccount> findByProviderAndProviderUid(OauthProvider provider, String providerUid);
}