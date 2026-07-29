package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;

public record AppearanceResponse(
		String hair,
		String face,
		String upperClothing,
		String lowerClothing,
		String shoes,
		String belongings,
		String bodyType,
		String distinctiveFeatures) {

	public static AppearanceResponse from(MissingCaseRow row) {
		return new AppearanceResponse(
				row.getHair(), row.getFace(), row.getUpperClothing(), row.getLowerClothing(),
				row.getShoes(), row.getBelongings(), row.getBodyType(), row.getDistinctiveFeatures());
	}
}
