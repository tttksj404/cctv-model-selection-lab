package com.ssafy.eyesonu.missingcase.domain;

public enum CaseStatus {

	RECEIVED,
	SEARCHING,
	CANDIDATE_FOUND,
	FIELD_SEARCH,
	CLOSED;

	public boolean canTransitionTo(CaseStatus target) {
		if (target == null || target == this) {
			return false;
		}
		return switch (this) {
			case RECEIVED -> target == SEARCHING || target == CLOSED;
			case SEARCHING -> target == CANDIDATE_FOUND || target == CLOSED;
			case CANDIDATE_FOUND -> target == SEARCHING
					|| target == FIELD_SEARCH
					|| target == CLOSED;
			case FIELD_SEARCH -> target == SEARCHING || target == CLOSED;
			case CLOSED -> false;
		};
	}
}
