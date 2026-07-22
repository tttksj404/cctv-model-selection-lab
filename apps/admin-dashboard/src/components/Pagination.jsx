import { ChevronLeft, ChevronRight } from "lucide-react";

export function Pagination({ page, totalPages, setPage }) {
  return (
    <div className="pagination">
      <button onClick={() => setPage(page - 1)} disabled={page === 1}><ChevronLeft size={16} />이전</button>
      <span>{page} / {totalPages}</span>
      <button onClick={() => setPage(page + 1)} disabled={page === totalPages}>다음<ChevronRight size={16} /></button>
    </div>
  );
}
