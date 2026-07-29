package com.ssafy.eyesonu.missingcase.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

class CaseStatusTests {

	private static final Map<CaseStatus, Set<CaseStatus>> ALLOWED_TRANSITIONS = Map.of(
			CaseStatus.RECEIVED, Set.of(CaseStatus.SEARCHING, CaseStatus.CLOSED),
			CaseStatus.SEARCHING, Set.of(CaseStatus.CANDIDATE_FOUND, CaseStatus.CLOSED),
			CaseStatus.CANDIDATE_FOUND,
			Set.of(CaseStatus.SEARCHING, CaseStatus.FIELD_SEARCH, CaseStatus.CLOSED),
			CaseStatus.FIELD_SEARCH, Set.of(CaseStatus.SEARCHING, CaseStatus.CLOSED),
			CaseStatus.CLOSED, Set.of());

	@Test
	void allowsOnlyDocumentedTransitions() {
		for (CaseStatus source : CaseStatus.values()) {
			for (CaseStatus target : CaseStatus.values()) {
				assertEquals(
						ALLOWED_TRANSITIONS.get(source).contains(target),
						source.canTransitionTo(target),
						() -> source + " -> " + target);
			}
		}
	}

	@Test
	void rejectsNullTargetsAndKeepsClosedTerminal() {
		for (CaseStatus source : CaseStatus.values()) {
			assertFalse(source.canTransitionTo(null), () -> source + " -> null");
		}
		for (CaseStatus target : CaseStatus.values()) {
			assertFalse(CaseStatus.CLOSED.canTransitionTo(target), () -> "CLOSED -> " + target);
		}
	}
}
