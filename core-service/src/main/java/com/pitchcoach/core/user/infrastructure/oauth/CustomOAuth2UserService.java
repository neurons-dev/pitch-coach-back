package com.pitchcoach.core.user.infrastructure.oauth;

import com.pitchcoach.core.user.application.EmailPolicy;
import com.pitchcoach.core.user.domain.OauthAccount;
import com.pitchcoach.core.user.domain.OauthProvider;
import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.infrastructure.OAuth2UserInfo;
import com.pitchcoach.core.user.infrastructure.OAuth2UserInfoFactory;
import com.pitchcoach.core.user.infrastructure.OauthAccountJpaRepository;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.oauth2.client.userinfo.DefaultOAuth2UserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.user.DefaultOAuth2User;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@Slf4j
@Service
@RequiredArgsConstructor
public class CustomOAuth2UserService extends DefaultOAuth2UserService {

    private final UserJpaRepository userJpaRepository;
    private final OauthAccountJpaRepository oauthAccountJpaRepository;
    private final EmailPolicy emailPolicy;

    @Override
    @Transactional
    public OAuth2User loadUser(OAuth2UserRequest userRequest) throws OAuth2AuthenticationException {
        OAuth2User oAuth2User = super.loadUser(userRequest);

        try {
            String registrationId = userRequest.getClientRegistration().getRegistrationId(); // "google" or "kakao"
            OAuth2UserInfo userInfo = OAuth2UserInfoFactory.of(registrationId, oAuth2User.getAttributes());
            OauthProvider provider = OauthProvider.valueOf(registrationId.toUpperCase());

            User user = findOrCreateUser(provider, userInfo);

            Map<String, Object> attributes = new java.util.HashMap<>(oAuth2User.getAttributes());
            attributes.put("pitchcoach_user_id", user.getId());

            return new DefaultOAuth2User(
                    List.of(new org.springframework.security.core.authority.SimpleGrantedAuthority("ROLE_USER")),
                    attributes,
                    "pitchcoach_user_id"
            );
        } catch (OAuth2AuthenticationException e) {
            throw e;
        } catch (Exception e) {
            throw new OAuth2AuthenticationException(
                    new OAuth2Error("social_login_processing_failed", "소셜 로그인 처리 중 오류가 발생했습니다.", null), e);
        }
    }

    private User findOrCreateUser(OauthProvider provider, OAuth2UserInfo userInfo) {
        return oauthAccountJpaRepository.findByProviderAndProviderUid(provider, userInfo.getProviderUid())
                .map(OauthAccount::getUser)
                .orElseGet(() -> linkExistingUser(provider, userInfo).orElseGet(() -> createNewUser(provider, userInfo)));
    }

    private Optional<User> linkExistingUser(OauthProvider provider, OAuth2UserInfo userInfo) {
        String email = userInfo.getEmail();
        if (email == null || email.isBlank()) {
            return Optional.empty();
        }

        Optional<User> existing = userJpaRepository.findByEmailIgnoreCase(email);
        if (existing.isEmpty()) {
            return Optional.empty();
        }

        if (!userInfo.isEmailVerified()) {
            log.warn("이메일이 같지만 검증되지 않아 자동 연동하지 않음: email={}, provider={}", email, provider);
            return Optional.empty();
        }

        User user = existing.get();
        oauthAccountJpaRepository.save(OauthAccount.of(user, provider, userInfo.getProviderUid()));
        log.info("기존 계정에 소셜 로그인 연동: userId={}, provider={}", user.getId(), provider);
        return Optional.of(user);
    }

    private User createNewUser(OauthProvider provider, OAuth2UserInfo userInfo) {
        String email = emailPolicy.resolveEmail(userInfo.getEmail(), provider.name(), userInfo.getProviderUid());
        String nickname = userInfo.getNickname() != null ? userInfo.getNickname() : "사용자" + userInfo.getProviderUid();

        User user = User.createSocial(email, nickname, userInfo.getProfileImageUrl());
        userJpaRepository.save(user);

        OauthAccount oauthAccount = OauthAccount.of(user, provider, userInfo.getProviderUid());
        oauthAccountJpaRepository.save(oauthAccount);

        return user;
    }
}