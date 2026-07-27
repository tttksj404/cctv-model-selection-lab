import { AlertTriangle, CheckCircle2, Clock3, Eye, FileWarning, Search } from "lucide-react";

export const summaryCards = [
  { id: "total", title: "전체 사건 수", value: 128, icon: FileWarning, delta: "+12", trend: "up" },
  { id: "searching", title: "탐색 중 사건 수", value: 37, icon: Search, delta: "+4", trend: "up" },
  { id: "candidate", title: "후보 발견 사건 수", value: 11, icon: Eye, delta: "+3", trend: "up" },
  { id: "today", title: "금일 신규 신고 수", value: 8, icon: Clock3, delta: "-2", trend: "down" }
];

export const cases = [
  { id: "c1", caseNumber: "CASE-2026-0417", missingName: "박순자", genderAge: "여 · 70대", reportedAt: "2026-07-21T09:52:00", lastSeenLocation: "강남구 테헤란로 152", status: "searching", assignee: "김민준" },
  { id: "c2", caseNumber: "CASE-2026-0416", missingName: "이도윤", genderAge: "남 · 10대", reportedAt: "2026-07-21T08:14:00", lastSeenLocation: "송파구 올림픽로 300", status: "candidate_found", assignee: "정하늘" },
  { id: "c3", caseNumber: "CASE-2026-0415", missingName: "최영호", genderAge: "남 · 80대", reportedAt: "2026-07-20T14:03:00", lastSeenLocation: "서초구 반포대로 12", status: "received", assignee: "김민준" },
  { id: "c4", caseNumber: "CASE-2026-0414", missingName: "한서연", genderAge: "여 · 20대", reportedAt: "2026-07-20T08:20:00", lastSeenLocation: "강동구 천호대로 1080", status: "closed", assignee: "정하늘" },
  { id: "c5", caseNumber: "CASE-2026-0413", missingName: "오민재", genderAge: "남 · 60대", reportedAt: "2026-07-19T18:42:00", lastSeenLocation: "마포구 월드컵북로 396", status: "searching", assignee: "박서준" },
  { id: "c6", caseNumber: "CASE-2026-0412", missingName: "강유나", genderAge: "여 · 30대", reportedAt: "2026-07-19T11:06:00", lastSeenLocation: "영등포구 여의대로 24", status: "candidate_found", assignee: "김민준" },
  { id: "c7", caseNumber: "CASE-2026-0411", missingName: "문태식", genderAge: "남 · 70대", reportedAt: "2026-07-18T22:31:00", lastSeenLocation: "관악구 남부순환로 1820", status: "searching", assignee: "이수빈" },
  { id: "c8", caseNumber: "CASE-2026-0410", missingName: "장해린", genderAge: "여 · 40대", reportedAt: "2026-07-18T16:11:00", lastSeenLocation: "중구 세종대로 110", status: "closed", assignee: "정하늘" },
  { id: "c9", caseNumber: "CASE-2026-0409", missingName: "배도현", genderAge: "남 · 50대", reportedAt: "2026-07-17T20:05:00", lastSeenLocation: "종로구 대학로 101", status: "received", assignee: "박서준" },
  { id: "c10", caseNumber: "CASE-2026-0408", missingName: "권미영", genderAge: "여 · 80대", reportedAt: "2026-07-17T13:47:00", lastSeenLocation: "성동구 왕십리로 222", status: "searching", assignee: "이수빈" },
  { id: "c11", caseNumber: "CASE-2026-0407", missingName: "서준호", genderAge: "남 · 20대", reportedAt: "2026-07-16T23:15:00", lastSeenLocation: "광진구 능동로 120", status: "candidate_found", assignee: "김민준" },
  { id: "c12", caseNumber: "CASE-2026-0406", missingName: "임가은", genderAge: "여 · 10대", reportedAt: "2026-07-16T07:34:00", lastSeenLocation: "노원구 동일로 1414", status: "closed", assignee: "정하늘" }
];

export const chartSeries = {
  "7d": [
    { date: "07-15", reports: 9, candidates: 3 },
    { date: "07-16", reports: 14, candidates: 6 },
    { date: "07-17", reports: 11, candidates: 5 },
    { date: "07-18", reports: 17, candidates: 7 },
    { date: "07-19", reports: 15, candidates: 8 },
    { date: "07-20", reports: 19, candidates: 10 },
    { date: "07-21", reports: 8, candidates: 4 }
  ],
  "14d": Array.from({ length: 14 }, (_, index) => ({
    date: `07-${String(index + 8).padStart(2, "0")}`,
    reports: 7 + ((index * 5) % 13),
    candidates: 2 + ((index * 3) % 8)
  })),
  "30d": Array.from({ length: 30 }, (_, index) => ({
    date: `D-${29 - index}`,
    reports: 5 + ((index * 7) % 18),
    candidates: 1 + ((index * 4) % 10)
  }))
};

export const notifications = [
  { id: "n1", title: "신규 후보 발견", message: "CASE-2026-0417에서 유사도 91% 후보가 탐지되었습니다.", type: "candidate", unread: true, icon: Eye },
  { id: "n2", title: "사건 상태 변경", message: "CASE-2026-0416 상태가 후보 발견으로 변경되었습니다.", type: "status", unread: true, icon: CheckCircle2 },
  { id: "n3", title: "탐색 오류", message: "CCTV-04 영상 스트림 연결이 지연되고 있습니다.", type: "error", unread: false, icon: AlertTriangle }
];
