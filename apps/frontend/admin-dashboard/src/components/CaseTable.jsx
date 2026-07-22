import { StatusBadge } from "./StatusBadge";

const formatDateTime = (value) => new Intl.DateTimeFormat("ko-KR", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit"
}).format(new Date(value));

export function CaseTable({ cases, onSelect }) {
  return (
    <div className="table-scroll">
      <table className="case-table">
        <thead>
          <tr>
            <th>사건 번호</th>
            <th>실종자 정보</th>
            <th>신고 시각</th>
            <th>마지막 목격 위치</th>
            <th>상태</th>
            <th>담당자</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((item) => (
            <tr key={item.id} onClick={() => onSelect(item)}>
              <td className="mono">{item.caseNumber}</td>
              <td><strong>{item.missingName}</strong><span>{item.genderAge}</span></td>
              <td className="mono">{formatDateTime(item.reportedAt)}</td>
              <td>{item.lastSeenLocation}</td>
              <td><StatusBadge status={item.status} /></td>
              <td>{item.assignee}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
