import {
  ClipboardList,
  History,
  Home,
  MapPinned,
  PanelLeftClose,
  PanelLeftOpen,
  Radar,
  Search,
  Settings,
  Video
} from "lucide-react";

export const menuItems = [
  { id: "dashboard", label: "대시보드", title: "관리자 대시보드", description: "실종 사건 접수, 탐색, 후보 탐지 현황", icon: Home },
  { id: "cases", label: "사건 목록/상세", title: "사건 목록 및 상세", description: "최근 접수되거나 상태가 변경된 사건을 조회합니다.", icon: ClipboardList },
  { id: "search", label: "탐색 조건 설정", title: "탐색 조건 설정", description: "사건별 탐색 조건과 CCTV 범위를 관리합니다.", icon: Search },
  { id: "timeline", label: "후보 타임라인", title: "후보 타임라인 및 판정", description: "실시간 후보 탐지 결과를 확인하고 판정합니다.", icon: Radar },
  { id: "cctv", label: "CCTV 지도/상태", title: "CCTV 지도 및 상태", description: "카메라 위치와 연결 상태를 모니터링합니다.", icon: MapPinned },
  { id: "scan", label: "녹화영상 스캔", title: "녹화영상 스캔", description: "백그라운드 영상 스캔 진행률을 확인합니다.", icon: Video },
  { id: "history", label: "사건 이력/감사로그", title: "사건 이력 및 감사로그", description: "운영자 작업 이력과 상태 변경 로그를 조회합니다.", icon: History },
  { id: "settings", label: "관리 설정", title: "관리 설정", description: "운영 정책과 관리자 권한을 설정합니다.", icon: Settings }
];

export function Sidebar({ collapsed, setCollapsed, mobileOpen, setMobileOpen, activeScreen, onSelect }) {
  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;

  const handleSelect = (id) => {
    onSelect(id);
    setMobileOpen(false);
  };

  return (
    <>
      {mobileOpen && <div className="sidebar-backdrop" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}>
        <div className="brand">
          <div className="brand-main">
            <div className="brand-mark">EF</div>
            {!collapsed && <div><strong>EyesForU</strong><span>Admin Console</span></div>}
          </div>
          <button className="sidebar-toggle" onClick={() => setCollapsed((value) => !value)} aria-label="사이드바 접기/펼치기">
            <ToggleIcon size={18} />
          </button>
        </div>
        <nav>
          {menuItems.map((item) => {
            const Icon = item.icon;
            const active = item.id === activeScreen;
            return (
              <button className={active ? "active" : ""} key={item.id} onClick={() => handleSelect(item.id)} title={collapsed ? item.label : undefined}>
                <Icon size={19} />
                {!collapsed && <span>{item.label}</span>}
              </button>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
