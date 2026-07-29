package com.pitchcoach.core.user.presentation;

import com.pitchcoach.core.user.application.LoginService;
import com.pitchcoach.core.user.application.LogoutService;
import com.pitchcoach.core.user.application.ReissueService;
import com.pitchcoach.core.user.application.SignUpService;
import com.pitchcoach.core.user.presentation.dto.*;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.URI;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final SignUpService signUpService;
    private final LoginService loginService;
    private final ReissueService reissueService;
    private final LogoutService logoutService;

    @PostMapping("/signup")
    public ResponseEntity<Void> signUp(@Valid @RequestBody SignUpRequest request) {
        Long userId = signUpService.signUp(request);
        return ResponseEntity.created(URI.create("/api/users/" + userId)).build();
    }

    @PostMapping("/login")
    public ResponseEntity<TokenResponse> login(@Valid @RequestBody LoginRequest request) {
        return ResponseEntity.ok(loginService.login(request));
    }

    @PostMapping("/reissue")
    public ResponseEntity<TokenResponse> reissue(@Valid @RequestBody ReissueRequest request) {
        return ResponseEntity.ok(reissueService.reissue(request));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(@Valid @RequestBody ReissueRequest request) {
        logoutService.logout(request.refreshToken());
        return ResponseEntity.noContent().build();
    }
}