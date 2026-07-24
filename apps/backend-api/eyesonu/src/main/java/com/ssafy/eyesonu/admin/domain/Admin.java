package com.ssafy.eyesonu.admin.domain;

public record Admin(Long id, String loginId, String passwordHash, String name) {
}
