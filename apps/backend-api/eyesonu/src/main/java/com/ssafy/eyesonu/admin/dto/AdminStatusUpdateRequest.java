package com.ssafy.eyesonu.admin.dto;

import jakarta.validation.constraints.NotNull;

public record AdminStatusUpdateRequest(@NotNull Boolean enabled) {
}
