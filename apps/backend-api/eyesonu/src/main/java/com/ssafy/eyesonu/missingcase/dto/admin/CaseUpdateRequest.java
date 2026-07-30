package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.Gender;
import java.math.BigDecimal;
import java.time.OffsetDateTime;

public class CaseUpdateRequest {

	private ReporterUpdateRequest reporter;
	private String reportContent;
	private String missingName;
	private Gender gender;
	private Integer birthYear;
	private AppearanceUpdateRequest appearance;
	private OffsetDateTime lastSeenTime;
	private BigDecimal lastSeenLat;
	private BigDecimal lastSeenLng;
	private String lastSeenAddress;

	private boolean reporterPresent;
	private boolean reportContentPresent;
	private boolean missingNamePresent;
	private boolean genderPresent;
	private boolean birthYearPresent;
	private boolean appearancePresent;
	private boolean lastSeenTimePresent;
	private boolean lastSeenLatPresent;
	private boolean lastSeenLngPresent;
	private boolean lastSeenAddressPresent;

	public ReporterUpdateRequest getReporter() { return reporter; }
	public void setReporter(ReporterUpdateRequest value) { reporter = value; reporterPresent = true; }
	public String getReportContent() { return reportContent; }
	public void setReportContent(String value) { reportContent = value; reportContentPresent = true; }
	public String getMissingName() { return missingName; }
	public void setMissingName(String value) { missingName = value; missingNamePresent = true; }
	public Gender getGender() { return gender; }
	public void setGender(Gender value) { gender = value; genderPresent = true; }
	public Integer getBirthYear() { return birthYear; }
	public void setBirthYear(Integer value) { birthYear = value; birthYearPresent = true; }
	public AppearanceUpdateRequest getAppearance() { return appearance; }
	public void setAppearance(AppearanceUpdateRequest value) { appearance = value; appearancePresent = true; }
	public OffsetDateTime getLastSeenTime() { return lastSeenTime; }
	public void setLastSeenTime(OffsetDateTime value) { lastSeenTime = value; lastSeenTimePresent = true; }
	public BigDecimal getLastSeenLat() { return lastSeenLat; }
	public void setLastSeenLat(BigDecimal value) { lastSeenLat = value; lastSeenLatPresent = true; }
	public BigDecimal getLastSeenLng() { return lastSeenLng; }
	public void setLastSeenLng(BigDecimal value) { lastSeenLng = value; lastSeenLngPresent = true; }
	public String getLastSeenAddress() { return lastSeenAddress; }
	public void setLastSeenAddress(String value) { lastSeenAddress = value; lastSeenAddressPresent = true; }

	public boolean hasReporter() { return reporterPresent; }
	public boolean hasReportContent() { return reportContentPresent; }
	public boolean hasMissingName() { return missingNamePresent; }
	public boolean hasGender() { return genderPresent; }
	public boolean hasBirthYear() { return birthYearPresent; }
	public boolean hasAppearance() { return appearancePresent; }
	public boolean hasLastSeenTime() { return lastSeenTimePresent; }
	public boolean hasLastSeenLat() { return lastSeenLatPresent; }
	public boolean hasLastSeenLng() { return lastSeenLngPresent; }
	public boolean hasLastSeenAddress() { return lastSeenAddressPresent; }

	public boolean hasChanges() {
		return reporterPresent || reportContentPresent || missingNamePresent || genderPresent
				|| birthYearPresent || appearancePresent || lastSeenTimePresent || lastSeenLatPresent
				|| lastSeenLngPresent || lastSeenAddressPresent;
	}
}
