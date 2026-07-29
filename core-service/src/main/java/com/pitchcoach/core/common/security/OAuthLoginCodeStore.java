package com.pitchcoach.core.common.security;

import org.springframework.stereotype.Component;

import java.security.SecureRandom;
import java.util.Base64;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class OAuthLoginCodeStore {

    private static final long CODE_TTL_MILLIS = 60_000;

    private final SecureRandom secureRandom = new SecureRandom();
    private final Map<String, Entry> codes = new ConcurrentHashMap<>();

    public String issue(Long userId) {
        evictExpired();

        byte[] bytes = new byte[32];
        secureRandom.nextBytes(bytes);
        String code = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);

        codes.put(code, new Entry(userId, System.currentTimeMillis() + CODE_TTL_MILLIS));
        return code;
    }

    public Optional<Long> consume(String code) {
        Entry entry = codes.remove(code);
        if (entry == null || entry.isExpired()) {
            return Optional.empty();
        }
        return Optional.of(entry.userId());
    }

    private void evictExpired() {
        codes.values().removeIf(Entry::isExpired);
    }

    private record Entry(Long userId, long expiresAtMillis) {
        boolean isExpired() {
            return System.currentTimeMillis() > expiresAtMillis;
        }
    }
}
