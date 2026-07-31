const REVIEW_STATUS = { PENDING: { label: "미판정", tone: "amber" }, KEPT: { label: "보류", tone: "blue" }, CONFIRMED: { label: "확정", tone: "green" }, REJECTED: { label: "제외", tone: "gray" } };
export const reviewStatusLabel = (status) => REVIEW_STATUS[String(status || "").toUpperCase()]?.label || "알 수 없음";
export const reviewStatusTone = (status) => REVIEW_STATUS[String(status || "").toUpperCase()]?.tone || "gray";
export const formatCandidateDate = (value) => { if (!value) return "-"; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("ko-KR", { dateStyle: "short", timeStyle: "short", hour12: false }).format(date); };
export const similarityPercent = (value) => Math.round(Number(value || 0) * 100);
export const similarityTone = (value) => { const score = similarityPercent(value); return score >= 70 ? "high" : score >= 40 ? "medium" : "low"; };
