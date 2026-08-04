package com.pitchcoach.core.user.presentation;

import com.pitchcoach.core.user.application.LoginService;
import com.pitchcoach.core.user.application.LogoutService;
import com.pitchcoach.core.user.application.OAuthExchangeService;
import com.pitchcoach.core.user.application.ReissueService;
import com.pitchcoach.core.user.application.SignUpService;
import com.pitchcoach.core.user.presentation.dto.*;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.URI;

@Tag(name = "Auth", description = "회원가입 / 로그인 / 소셜 로그인 / 로그아웃")
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final SignUpService signUpService;
    private final LoginService loginService;
    private final ReissueService reissueService;
    private final LogoutService logoutService;
    private final OAuthExchangeService oAuthExchangeService;

    @Operation(summary = "회원가입", description = "로컬 계정으로 회원가입하고 accessToken/refreshToken을 즉시 발급받습니다. 응답 Location 헤더에 생성된 유저 리소스 경로가 담깁니다.")
    @PostMapping("/signup")
    public ResponseEntity<AuthResponse> signUp(@Valid @RequestBody SignUpRequest request) {
        AuthResponse response = signUpService.signUp(request);
        return ResponseEntity.created(URI.create("/api/users/" + response.userId())).body(response);
    }

    @Operation(summary = "로그인", description = "로컬 계정 이메일/비밀번호로 로그인하고 accessToken/refreshToken을 발급받습니다.")
    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(@Valid @RequestBody LoginRequest request) {
        return ResponseEntity.ok(loginService.login(request));
    }

    @Operation(summary = "소셜 로그인 코드 교환",
            description = "소셜 로그인 성공 후 리다이렉트로 받은 1회용 code(60초 내 사용)를 실제 accessToken/refreshToken으로 교환합니다.")
    @PostMapping("/oauth/exchange")
    public ResponseEntity<AuthResponse> exchangeOAuthCode(@Valid @RequestBody OAuthExchangeRequest request) {
        return ResponseEntity.ok(oAuthExchangeService.exchange(request.code()));
    }

    @Operation(summary = "토큰 재발급", description = "refreshToken으로 새 accessToken/refreshToken 쌍을 발급받습니다. 기존 refreshToken은 즉시 폐기됩니다.")
    @PostMapping("/reissue")
    public ResponseEntity<TokenResponse> reissue(@Valid @RequestBody ReissueRequest request) {
        return ResponseEntity.ok(reissueService.reissue(request));
    }

    @Operation(summary = "로그아웃", description = "전달한 refreshToken 하나만 폐기합니다. 다른 기기의 세션에는 영향이 없습니다.")
    @PostMapping("/logout")
    public ResponseEntity<Void> logout(@Valid @RequestBody ReissueRequest request) {
        logoutService.logout(request.refreshToken());
        return ResponseEntity.noContent().build();
    }
}