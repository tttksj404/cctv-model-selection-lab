import { describe, expect, it } from "vitest";
import { candidateSourceLabel, candidateSourceTone, formatCandidateDate, reviewStatusLabel, reviewStatusTone, similarityPercent, similarityTone } from "./candidateMapper";
describe("candidateMapper", () => { it("maps statuses", () => { expect(reviewStatusLabel("PENDING")).toBe("미판정"); expect(reviewStatusLabel("CONFIRMED")).toBe("확정"); expect(reviewStatusTone("REJECTED")).toBe("gray"); }); it("formats values", () => { expect(similarityPercent("0.913")).toBe(91); expect(similarityTone(0.5)).toBe("medium"); expect(formatCandidateDate("not-a-date")).toBe("not-a-date"); }); });

describe("candidate source mapping", () => {
  it("labels realtime and recording analysis sources", () => {
    expect(candidateSourceLabel("REALTIME")).toBe("실시간");
    expect(candidateSourceTone("REALTIME")).toBe("green");
    expect(candidateSourceLabel("RECORDING_ANALYSIS")).toBe("녹화");
    expect(candidateSourceTone("RECORDING_ANALYSIS")).toBe("blue");
  });
});
