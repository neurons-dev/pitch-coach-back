package com.pitchcoach.core.common.security;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.security.web.authentication.SimpleUrlAuthenticationSuccessHandler;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
@RequiredArgsConstructor
public class OAuth2LoginSuccessHandler extends SimpleUrlAuthenticationSuccessHandler {

    @Value("${app.frontend.oauth-redirect-base}")
    private String frontendRedirectBase;

    private final OAuthLoginCodeStore oAuthLoginCodeStore;

    @Override
    public void onAuthenticationSuccess(
            HttpServletRequest request,
            HttpServletResponse response,
            Authentication authentication
    ) throws IOException {

        OAuth2User oAuth2User = (OAuth2User) authentication.getPrincipal();
        Long userId = Long.valueOf(String.valueOf(oAuth2User.getAttributes().get("pitchcoach_user_id")));

        String code = oAuthLoginCodeStore.issue(userId);

        String redirectUrl = frontendRedirectBase + "?code=" + code;

        getRedirectStrategy().sendRedirect(request, response, redirectUrl);
    }
}
