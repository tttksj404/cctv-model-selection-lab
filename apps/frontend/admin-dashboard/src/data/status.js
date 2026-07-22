import { CheckCircle2, Clock3, Eye, Search, Siren } from "lucide-react";

export const caseStatusMap = {
  all: { label: "전체", icon: Eye, tone: "neutral" },
  received: { label: "접수", icon: Siren, tone: "blue" },
  searching: { label: "탐색 중", icon: Search, tone: "green" },
  candidate_found: { label: "후보 발견", icon: Eye, tone: "amber" },
  closed: { label: "종료", icon: CheckCircle2, tone: "gray" },
  scan_error: { label: "탐색 오류", icon: Clock3, tone: "red" }
};

export const statusOptions = ["all", "received", "searching", "candidate_found", "closed"];
