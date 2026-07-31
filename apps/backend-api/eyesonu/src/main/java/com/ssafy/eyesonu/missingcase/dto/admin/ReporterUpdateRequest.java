package com.ssafy.eyesonu.missingcase.dto.admin;

public class ReporterUpdateRequest {

	private String name;
	private String phone;
	private String email;
	private String relation;
	private boolean namePresent;
	private boolean phonePresent;
	private boolean emailPresent;
	private boolean relationPresent;

	public String getName() { return name; }
	public void setName(String name) { this.name = name; this.namePresent = true; }
	public String getPhone() { return phone; }
	public void setPhone(String phone) { this.phone = phone; this.phonePresent = true; }
	public String getEmail() { return email; }
	public void setEmail(String email) { this.email = email; this.emailPresent = true; }
	public String getRelation() { return relation; }
	public void setRelation(String relation) { this.relation = relation; this.relationPresent = true; }

	public boolean hasName() { return namePresent; }
	public boolean hasPhone() { return phonePresent; }
	public boolean hasEmail() { return emailPresent; }
	public boolean hasRelation() { return relationPresent; }
	public boolean hasChanges() { return namePresent || phonePresent || emailPresent || relationPresent; }
}
