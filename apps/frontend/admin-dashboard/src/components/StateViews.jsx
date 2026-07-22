import { AlertCircle, Loader2, SearchX } from "lucide-react";

export function LoadingView() {
  return <div className="state-view"><Loader2 className="spin" size={24} /><strong>데이터를 불러오는 중입니다.</strong></div>;
}

export function ErrorView({ onRetry }) {
  return (
    <div className="state-view error">
      <AlertCircle size={24} />
      <strong>요청을 처리하지 못했습니다.</strong>
      <button onClick={onRetry}>다시 시도</button>
    </div>
  );
}

export function EmptyState() {
  return <div className="state-view"><SearchX size={26} /><strong>조건에 맞는 사건이 없습니다.</strong><p>검색 조건을 변경하거나 초기화해 주세요.</p></div>;
}
