import { describe, expect, it } from "vitest";
import { formatCandidateDate, reviewStatusLabel, reviewStatusTone, similarityPercent, similarityTone } from "./candidateMapper";
describe("candidateMapper", () => { it("maps statuses", () => { expect(reviewStatusLabel("PENDING")).toBe("미판정"); expect(reviewStatusLabel("CONFIRMED")).toBe("확정"); expect(reviewStatusTone("REJECTED")).toBe("gray"); }); it("formats values", () => { expect(similarityPercent("0.913")).toBe(91); expect(similarityTone(0.5)).toBe("medium"); expect(formatCandidateDate("not-a-date")).toBe("not-a-date"); }); });
