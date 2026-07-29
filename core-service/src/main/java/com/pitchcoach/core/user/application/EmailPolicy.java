package com.pitchcoach.core.user.application;

import org.springframework.stereotype.Component;

@Component
public class EmailPolicy {

    public String resolveEmail(String rawEmail, String provider, String providerUid) {
        if (rawEmail != null && !rawEmail.isBlank()) {
            return rawEmail;
        }
        return "%s_%s@noemail.pitchcoach.local".formatted(provider.toLowerCase(), providerUid);
    }
}