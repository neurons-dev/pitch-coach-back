package com.pitchcoach.core.user.presentation;

import com.pitchcoach.core.user.domain.User;
import com.pitchcoach.core.user.infrastructure.UserJpaRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/test/users")
@RequiredArgsConstructor
public class UserTestController {

    private final UserJpaRepository userJpaRepository;

    @PostMapping
    @Transactional
    public User create(@RequestParam String email, @RequestParam String nickname) {
        User user = User.createLocal(email, nickname);
        return userJpaRepository.save(user);
    }

    @GetMapping
    public List<User> findAll() {
        return userJpaRepository.findAll();
    }
}