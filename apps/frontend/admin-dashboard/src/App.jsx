import { useEffect, useMemo, useState } from "react";
import { CaseTable } from "./components/CaseTable";
import { EmptyState, ErrorView, LoadingView } from "./components/StateViews";
import { Header } from "./components/Header";
import { Pagination } from "./components/Pagination";
import { SearchFilter } from "./components/SearchFilter";
import { menuItems, Sidebar } from "./components/Sidebar";
import { StatisticsChart } from "./components/StatisticsChart";
import { SummaryCard } from "./components/SummaryCard";
import { fetchChartData, fetchDashboardData } from "./services/dashboardService";

const initialFilters = { status: "all", from: "", to: "", keyword: "" };
const pageSize = 10;

function SectionPlaceholder({ activeScreen }) {
  const meta = menuItems.find((item) => item.id === activeScreen);

  return (
    <section className="content-panel placeholder-panel">
      <div className="section-heading">
        <div>
          <h2>{meta?.title}</h2>
          <p>{meta?.description}</p>
        </div>
      </div>
      <div className="state-view">
        <strong>{meta?.label} 화면</strong>
        <p>메뉴 이동이 연결되어 있으며, 이후 API와 상세 컴포넌트를 붙일 수 있는 영역입니다.</p>
      </div>
    </section>
  );
}

export default function App() {
  const [dashboard, setDashboard] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [chartRange, setChartRange] = useState("7d");
  const [filters, setFilters] = useState(initialFilters);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [activeScreen, setActiveScreen] = useState("dashboard");

  const loadDashboard = async () => {
    setLoading(true);
    setError(false);
    try {
      setDashboard(await fetchDashboardData());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadDashboard(); }, []);
  useEffect(() => { fetchChartData(chartRange).then(setChartData); }, [chartRange]);
  useEffect(() => setPage(1), [filters]);

  useEffect(() => {
    const close = (event) => {
      if (!event.target.closest(".notification-wrap")) setNotificationOpen(false);
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  const filteredCases = useMemo(() => {
    const keyword = filters.keyword.trim().toLowerCase();
    return (dashboard?.cases ?? []).filter((item) => {
      const reported = item.reportedAt.slice(0, 10);
      const statusMatch = filters.status === "all" || item.status === filters.status;
      const fromMatch = !filters.from || reported >= filters.from;
      const toMatch = !filters.to || reported <= filters.to;
      const keywordMatch = !keyword || `${item.caseNumber} ${item.missingName}`.toLowerCase().includes(keyword);
      return statusMatch && fromMatch && toMatch && keywordMatch;
    });
  }, [dashboard, filters]);

  const totalPages = Math.max(1, Math.ceil(filteredCases.length / pageSize));
  const visibleCases = filteredCases.slice((page - 1) * pageSize, page * pageSize);
  const screenMeta = menuItems.find((item) => item.id === activeScreen) ?? menuItems[0];
  const showDashboardWidgets = activeScreen === "dashboard";
  const showCaseList = activeScreen === "dashboard" || activeScreen === "cases";

  const handleSelectCase = (item) => {
    setActiveScreen("cases");
    window.location.hash = `/cases/${item.id}`;
  };

  return (
    <div className={`app-shell ${sidebarCollapsed ? "is-collapsed" : ""}`}>
      <Sidebar
        collapsed={sidebarCollapsed}
        setCollapsed={setSidebarCollapsed}
        mobileOpen={mobileSidebarOpen}
        setMobileOpen={setMobileSidebarOpen}
        activeScreen={activeScreen}
        onSelect={setActiveScreen}
      />
      <main>
        <button className="mobile-sidebar-button" onClick={() => setMobileSidebarOpen(true)} aria-label="사이드바 열기">
          메뉴
        </button>
        <Header
          title={screenMeta.title}
          description={screenMeta.description}
          notifications={dashboard?.notifications ?? []}
          isOpen={notificationOpen}
          setOpen={setNotificationOpen}
          onRetry={loadDashboard}
        />
        {loading && <LoadingView />}
        {error && <ErrorView onRetry={loadDashboard} />}
        {!loading && !error && dashboard && (
          <>
            {showDashboardWidgets && (
              <>
                <section className="summary-grid">
                  {dashboard.summaryCards.map((card) => <SummaryCard card={card} key={card.id} />)}
                </section>
                <StatisticsChart range={chartRange} setRange={setChartRange} data={chartData} />
              </>
            )}
            {showCaseList ? (
              <section className="content-panel">
                <div className="section-heading">
                  <div>
                    <h2>최근 접수 사건</h2>
                    <p>상태 변경 및 신규 접수 기준으로 정렬된 목록입니다.</p>
                  </div>
                </div>
                <SearchFilter filters={filters} setFilters={setFilters} onReset={() => setFilters(initialFilters)} />
                {visibleCases.length === 0 ? <EmptyState /> : <CaseTable cases={visibleCases} onSelect={handleSelectCase} />}
                <Pagination page={page} totalPages={totalPages} setPage={setPage} />
              </section>
            ) : (
              <SectionPlaceholder activeScreen={activeScreen} />
            )}
          </>
        )}
      </main>
    </div>
  );
}
