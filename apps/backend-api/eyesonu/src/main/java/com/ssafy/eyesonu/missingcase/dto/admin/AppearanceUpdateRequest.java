package com.ssafy.eyesonu.missingcase.dto.admin;

public class AppearanceUpdateRequest {

	private String hair;
	private String face;
	private String upperClothing;
	private String lowerClothing;
	private String shoes;
	private String belongings;
	private String bodyType;
	private String distinctiveFeatures;
	private boolean hairPresent;
	private boolean facePresent;
	private boolean upperClothingPresent;
	private boolean lowerClothingPresent;
	private boolean shoesPresent;
	private boolean belongingsPresent;
	private boolean bodyTypePresent;
	private boolean distinctiveFeaturesPresent;

	public String getHair() { return hair; }
	public void setHair(String value) { hair = value; hairPresent = true; }
	public String getFace() { return face; }
	public void setFace(String value) { face = value; facePresent = true; }
	public String getUpperClothing() { return upperClothing; }
	public void setUpperClothing(String value) { upperClothing = value; upperClothingPresent = true; }
	public String getLowerClothing() { return lowerClothing; }
	public void setLowerClothing(String value) { lowerClothing = value; lowerClothingPresent = true; }
	public String getShoes() { return shoes; }
	public void setShoes(String value) { shoes = value; shoesPresent = true; }
	public String getBelongings() { return belongings; }
	public void setBelongings(String value) { belongings = value; belongingsPresent = true; }
	public String getBodyType() { return bodyType; }
	public void setBodyType(String value) { bodyType = value; bodyTypePresent = true; }
	public String getDistinctiveFeatures() { return distinctiveFeatures; }
	public void setDistinctiveFeatures(String value) { distinctiveFeatures = value; distinctiveFeaturesPresent = true; }

	public boolean hasHair() { return hairPresent; }
	public boolean hasFace() { return facePresent; }
	public boolean hasUpperClothing() { return upperClothingPresent; }
	public boolean hasLowerClothing() { return lowerClothingPresent; }
	public boolean hasShoes() { return shoesPresent; }
	public boolean hasBelongings() { return belongingsPresent; }
	public boolean hasBodyType() { return bodyTypePresent; }
	public boolean hasDistinctiveFeatures() { return distinctiveFeaturesPresent; }
	public boolean hasChanges() {
		return hairPresent || facePresent || upperClothingPresent || lowerClothingPresent
				|| shoesPresent || belongingsPresent || bodyTypePresent || distinctiveFeaturesPresent;
	}
}
