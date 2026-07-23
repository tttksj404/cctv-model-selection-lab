import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import LoginView from "../views/LoginView.vue";
import AdminLayout from "../layouts/AdminLayout.vue";
import DashboardView from "../views/DashboardView.vue";
import CasesView from "../views/CasesView.vue";
import CaseFormView from "../views/CaseFormView.vue";
import CaseDetailView from "../views/CaseDetailView.vue";
import LiveMonitoringView from "../views/LiveMonitoringView.vue";
import RecordingSearchView from "../views/RecordingSearchView.vue";
import CandidatesView from "../views/CandidatesView.vue";
import CandidateDetailView from "../views/CandidateDetailView.vue";
import RoutesView from "../views/RoutesView.vue";
import CamerasView from "../views/CamerasView.vue";
import CameraFormView from "../views/CameraFormView.vue";
import UsersView from "../views/UsersView.vue";
import LogsView from "../views/LogsView.vue";
import NotificationsView from "../views/NotificationsView.vue";
import NotificationSettingsView from "../views/NotificationSettingsView.vue";
import SettingsView from "../views/SettingsView.vue";
import ProfileView from "../views/ProfileView.vue";
import ReportLookupView from "../views/ReportLookupView.vue";
import ReportCaseView from "../views/ReportCaseView.vue";
import NotFoundView from "../views/NotFoundView.vue";

export const adminMenu = [
  { path: "/admin/dashboard", label: "대시보드", title: "관리자 대시보드" },
  { path: "/admin/cases", label: "사건 관리", title: "사건 관리" },
  { path: "/admin/live-monitoring", label: "실시간 CCTV 모니터링", title: "실시간 CCTV 모니터링" },
  { path: "/admin/recording-search", label: "녹화 영상 탐색", title: "녹화 영상 탐색" },
  { path: "/admin/candidates", label: "후보 검토", title: "후보 검토" },
  { path: "/admin/routes", label: "추정 동선", title: "추정 동선" },
  { path: "/admin/cameras", label: "CCTV 관리", title: "CCTV 관리" },
  { path: "/admin/users", label: "사용자 관리", title: "사용자 관리" },
  { path: "/admin/logs", label: "시스템 로그", title: "시스템 로그" },
  { path: "/admin/notifications", label: "알림", title: "알림" },
  { path: "/admin/settings", label: "설정", title: "설정" }
];

const routes = [
  { path: "/", redirect: "/admin/dashboard" },
  { path: "/login", component: LoginView, meta: { public: true, title: "로그인" } },
  {
    path: "/admin",
    component: AdminLayout,
    redirect: "/admin/dashboard",
    children: [
      { path: "dashboard", component: DashboardView, meta: { title: "관리자 대시보드" } },
      { path: "cases", component: CasesView, meta: { title: "사건 관리" } },
      { path: "cases/new", component: CaseFormView, meta: { title: "신규 사건 등록" } },
      { path: "cases/:caseId/edit", component: CaseFormView, meta: { title: "사건 정보 수정" } },
      { path: "cases/:caseId", component: CaseDetailView, meta: { title: "사건 상세" } },
      { path: "live-monitoring", component: LiveMonitoringView, meta: { title: "실시간 CCTV 모니터링" } },
      { path: "recording-search", component: RecordingSearchView, meta: { title: "녹화 영상 탐색" } },
      { path: "recording-search/:taskId", component: RecordingSearchView, meta: { title: "탐색 작업 상세" } },
      { path: "candidates", component: CandidatesView, meta: { title: "후보 검토" } },
      { path: "candidates/:candidateId", component: CandidateDetailView, meta: { title: "후보 상세 검토" } },
      { path: "routes", component: RoutesView, meta: { title: "추정 동선" } },
      { path: "cameras", component: CamerasView, meta: { title: "CCTV 관리" } },
      { path: "cameras/new", component: CameraFormView, meta: { title: "CCTV 등록" } },
      { path: "cameras/:cameraId/edit", component: CameraFormView, meta: { title: "CCTV 수정" } },
      { path: "users", component: UsersView, meta: { title: "사용자 관리" } },
      { path: "logs", component: LogsView, meta: { title: "시스템 로그" } },
      { path: "notifications", component: NotificationsView, meta: { title: "알림" } },
      { path: "notifications/settings", component: NotificationSettingsView, meta: { title: "알림 설정" } },
      { path: "settings", component: SettingsView, meta: { title: "설정" } },
      { path: "profile", component: ProfileView, meta: { title: "프로필 관리" } }
    ]
  },
  { path: "/report/lookup", component: ReportLookupView, meta: { public: true, title: "신고자 사건 조회" } },
  { path: "/report/cases/:accessToken", component: ReportCaseView, meta: { public: true, title: "사건 진행 현황" } },
  { path: "/:pathMatch(.*)*", component: NotFoundView, meta: { public: true, title: "404" } }
];

export const router = createRouter({ history: createWebHistory(), routes });

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (!to.meta.public && !auth.isAuthenticated) return "/login";
  document.title = `${to.meta.title || "관리자"} | Eyes On U`;
});
