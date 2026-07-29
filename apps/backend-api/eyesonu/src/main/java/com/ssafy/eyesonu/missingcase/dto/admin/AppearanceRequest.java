package com.ssafy.eyesonu.missingcase.dto.admin;

import jakarta.validation.constraints.Size;

public record AppearanceRequest(
		@Size(max = 255) String hair,
		@Size(max = 255) String face,
		@Size(max = 255) String upperClothing,
		@Size(max = 255) String lowerClothing,
		@Size(max = 255) String shoes,
		@Size(max = 1000) String belongings,
		@Size(max = 255) String bodyType,
		@Size(max = 2000) String distinctiveFeatures) {
}
