import { caseStatusMap } from "../data/status";

export function StatusBadge({ status }) {
  const meta = caseStatusMap[status] ?? caseStatusMap.received;
  return <span className={`status-badge ${meta.tone}`}>{meta.label}</span>;
}
