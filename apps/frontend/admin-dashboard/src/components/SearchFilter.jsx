import { RotateCcw, Search } from "lucide-react";
import { statusOptions } from "../data/status";
import { caseStatusMap } from "../data/status";

export function SearchFilter({ filters, setFilters, onReset }) {
  return (
    <section className="filter-bar">
      <label>
        상태
        <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
          {statusOptions.map((status) => <option key={status} value={status}>{caseStatusMap[status].label}</option>)}
        </select>
      </label>
      <label>
        접수 시작일
        <input type="date" value={filters.from} onChange={(e) => setFilters({ ...filters, from: e.target.value })} />
      </label>
      <label>
        접수 종료일
        <input type="date" value={filters.to} onChange={(e) => setFilters({ ...filters, to: e.target.value })} />
      </label>
      <label className="search-input">
        사건 번호 또는 이름
        <div><Search size={16} /><input value={filters.keyword} onChange={(e) => setFilters({ ...filters, keyword: e.target.value })} placeholder="CASE-2026 또는 실종자명" /></div>
      </label>
      <button className="reset-button" onClick={onReset}><RotateCcw size={16} />초기화</button>
    </section>
  );
}
