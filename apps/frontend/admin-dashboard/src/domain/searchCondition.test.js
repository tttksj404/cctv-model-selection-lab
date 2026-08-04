import { describe, expect, it } from "vitest";
import {
  buildCanonicalPrompt,
  buildSearchConditionPayload,
  emptyDescriptor,
  parseCanonicalPrompt,
  toLocalDateTimeInput,
  validateSearchConditionForm
} from "./searchCondition";

const validForm = (overrides = {}) => ({
  subject: { gender: "woman", upperColor: "red", sleeve: "long sleeve", lowerColor: "black" },
  exclusionEnabled: false,
  exclusion: emptyDescriptor(),
  searchStart: "2026-08-03T09:20",
  searchEnd: "2026-08-03T13:20",
  searchArea: " 테헤란로 ",
  ...overrides
});

describe("searchCondition domain", () => {
  it("builds and parses the Jetson canonical prompt", () => {
    const prompt = buildCanonicalPrompt(validForm().subject);
    expect(prompt).toBe("a woman wearing a red long sleeve top and black pants");
    expect(parseCanonicalPrompt(prompt)).toEqual(validForm().subject);
    expect(parseCanonicalPrompt("빨간 상의를 입은 사람")).toBeNull();
  });

  it("requires every structured field including an enabled exclusion", () => {
    expect(validateSearchConditionForm(validForm({
      subject: { ...validForm().subject, upperColor: "" }
    }))).toContain("모두 선택");
    expect(validateSearchConditionForm(validForm({ exclusionEnabled: true }))).toContain("제외 조건");
  });

  it("requires a complete, ordered time pair", () => {
    expect(validateSearchConditionForm(validForm({ searchEnd: "" }))).toContain("함께 입력");
    expect(validateSearchConditionForm(validForm({
      searchStart: "2026-08-03T13:21",
      searchEnd: "2026-08-03T13:20"
    }))).toContain("빠를 수 없습니다");
  });

  it("creates the API payload without a similarity threshold", () => {
    const payload = buildSearchConditionPayload(validForm({
      exclusionEnabled: true,
      exclusion: { gender: "man", upperColor: "blue", sleeve: "short sleeve", lowerColor: "gray" }
    }));

    expect(payload).toMatchObject({
      prompt: "a woman wearing a red long sleeve top and black pants",
      exclusionPrompt: "a man wearing a blue short sleeve top and gray pants",
      searchArea: "테헤란로"
    });
    expect(payload.searchStart).toMatch(/^2026-08-03T/);
    expect(payload).not.toHaveProperty("similarityThreshold");
  });

  it("preserves seconds and milliseconds while converting an existing API time for editing", () => {
    const source = new Date(2026, 7, 3, 9, 20, 59, 987).toISOString();
    const localValue = toLocalDateTimeInput(source);
    const payload = buildSearchConditionPayload(validForm({
      searchStart: localValue,
      searchEnd: localValue
    }));

    expect(localValue).toMatch(/T09:20:59\.987$/);
    expect(new Date(payload.searchStart).getSeconds()).toBe(59);
    expect(new Date(payload.searchStart).getMilliseconds()).toBe(987);
    expect(new Date(payload.searchEnd).getSeconds()).toBe(59);
    expect(new Date(payload.searchEnd).getMilliseconds()).toBe(987);
  });
});
