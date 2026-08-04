export const statusMap = {
  received: { label: "접수", tone: "blue" },
  preparing: { label: "탐색 준비", tone: "gray" },
  searching: { label: "탐색 중", tone: "green" },
  candidate_found: { label: "후보 발견", tone: "rose" },
  closed: { label: "종료", tone: "gray" },
  failed: { label: "실패", tone: "red" },
  cancelled: { label: "취소됨", tone: "gray" },
  online: { label: "정상", tone: "green" },
  unstable: { label: "연결 불안정", tone: "amber" },
  offline: { label: "연결 없음", tone: "red" },
  error: { label: "오류", tone: "amber" }
};

export const dashboardSummary = [
  { id: "total", title: "전체 사건 수", value: 128, delta: "+12" },
  { id: "searching", title: "탐색 중 사건 수", value: 37, delta: "+4" },
  { id: "candidate", title: "후보 발견 사건 수", value: 11, delta: "+3" },
  { id: "today", title: "오늘 접수 신고 수", value: 8, delta: "-2" },
  { id: "cctv", title: "운영 중 CCTV 수", value: 42, delta: "+1" }
];

export const cases = [
  { id: "c1", caseNumber: "CASE-2026-0417", name: "윤현준", gender: "남", age: 26, photo: "실종자 사진", reportedAt: "2026-07-21 09:52", lastSeenLocation: "강남구 테헤란로 152", lastSeenAt: "2026-07-21 09:40", status: "searching", assignee: "김민준", appearance: "네이비색 반팔, 검은 바지", reporter: "윤서진(가족) / 010-1022-3311" },
  { id: "c2", caseNumber: "CASE-2026-0416", name: "이도윤", gender: "남", age: 15, photo: "기준 사진", reportedAt: "2026-07-21 08:14", lastSeenLocation: "송파구 올림픽로 300", lastSeenAt: "2026-07-21 07:50", status: "candidate_found", assignee: "정하늘", appearance: "남색 후드티, 청바지, 빨간 백팩", reporter: "이하린(보호자) / 010-7711-2044" },
  { id: "c3", caseNumber: "CASE-2026-0415", name: "최영호", gender: "남", age: 82, photo: "기준 사진", reportedAt: "2026-07-20 14:03", lastSeenLocation: "서초구 반포대로 12", lastSeenAt: "2026-07-20 13:30", status: "received", assignee: "김민준", appearance: "회색 조끼, 갈색 모자, 보행보조기", reporter: "최지우(딸) / 010-9911-8821" },
  { id: "c4", caseNumber: "CASE-2026-0414", name: "한서연", gender: "여", age: 27, photo: "기준 사진", reportedAt: "2026-07-20 08:20", lastSeenLocation: "강동구 천호대로 1080", lastSeenAt: "2026-07-20 07:55", status: "closed", assignee: "정하늘", appearance: "흰색 코트, 검정 스니커즈", reporter: "한지민 / 010-2922-7242" },
  { id: "c5", caseNumber: "CASE-2026-0413", name: "오민재", gender: "남", age: 63, photo: "기준 사진", reportedAt: "2026-07-19 18:42", lastSeenLocation: "마포구 월드컵북로 396", lastSeenAt: "2026-07-19 17:55", status: "searching", assignee: "박서준", appearance: "검정 점퍼, 흰 운동화", reporter: "오나리 / 010-6221-5500" },
  { id: "c6", caseNumber: "CASE-2026-0412", name: "강유나", gender: "여", age: 34, photo: "기준 사진", reportedAt: "2026-07-19 11:06", lastSeenLocation: "영등포구 여의대로 24", lastSeenAt: "2026-07-19 10:20", status: "candidate_found", assignee: "김민준", appearance: "베이지 재킷, 검정 가방", reporter: "강도윤 / 010-1515-9001" },
  { id: "c7", caseNumber: "CASE-2026-0411", name: "문태식", gender: "남", age: 76, photo: "기준 사진", reportedAt: "2026-07-18 22:31", lastSeenLocation: "관악구 남부순환로 1820", lastSeenAt: "2026-07-18 21:50", status: "searching", assignee: "이수빈", appearance: "녹색 셔츠, 회색 모자", reporter: "문다정 / 010-8282-4001" },
  { id: "c8", caseNumber: "CASE-2026-0410", name: "장해린", gender: "여", age: 41, photo: "기준 사진", reportedAt: "2026-07-18 16:11", lastSeenLocation: "중구 세종대로 110", lastSeenAt: "2026-07-18 15:32", status: "closed", assignee: "정하늘", appearance: "파란 셔츠, 검정 바지", reporter: "장윤호 / 010-1919-2344" },
  { id: "c9", caseNumber: "CASE-2026-0409", name: "배도현", gender: "남", age: 52, photo: "기준 사진", reportedAt: "2026-07-17 20:05", lastSeenLocation: "종로구 대학로 101", lastSeenAt: "2026-07-17 19:21", status: "received", assignee: "박서준", appearance: "남색 정장, 안경", reporter: "배선우 / 010-4441-6711" },
  { id: "c10", caseNumber: "CASE-2026-0408", name: "권미영", gender: "여", age: 84, photo: "기준 사진", reportedAt: "2026-07-17 13:47", lastSeenLocation: "성동구 왕십리로 222", lastSeenAt: "2026-07-17 12:40", status: "searching", assignee: "이수빈", appearance: "분홍 카디건, 지팡이", reporter: "권태윤 / 010-8181-3320" },
  { id: "c11", caseNumber: "CASE-2026-0407", name: "서준호", gender: "남", age: 28, photo: "기준 사진", reportedAt: "2026-07-16 23:15", lastSeenLocation: "광진구 능동로 120", lastSeenAt: "2026-07-16 22:02", status: "candidate_found", assignee: "김민준", appearance: "검은 티셔츠, 청바지", reporter: "서지안 / 010-5400-3333" }
];

export const candidates = [
  { id: "k1", caseId: "c1", caseNumber: "CASE-2026-0417", image: "후보 캡처", camera: "CCTV-04", zone: "Zone A", detectedAt: "2026-07-21 14:32:07", similarity: 91, source: "실시간", review: "pending", location: "테헤란로 2번 출구" },
  { id: "k1-2", caseId: "c1", caseNumber: "CASE-2026-0417", image: "후보 캡처", camera: "CCTV-02", zone: "Zone A", detectedAt: "2026-07-21 14:05:44", similarity: 84, source: "실시간", review: "pending", location: "역삼로 교차로" },
  { id: "k1-3", caseId: "c1", caseNumber: "CASE-2026-0417", image: "후보 캡처", camera: "CCTV-09", zone: "Zone B", detectedAt: "2026-07-21 13:48:18", similarity: 72, source: "녹화", review: "hold", location: "선릉역 4번 출구" },
  { id: "k2", caseId: "c2", caseNumber: "CASE-2026-0416", image: "후보 캡처", camera: "CCTV-11", zone: "Zone B", detectedAt: "2026-07-21 14:18:52", similarity: 83, source: "실시간", review: "confirmed", location: "올림픽공원 북문" },
  { id: "k3", caseId: "c6", caseNumber: "CASE-2026-0412", image: "후보 캡처", camera: "CCTV-02", zone: "Zone A", detectedAt: "2026-07-21 13:57:20", similarity: 76, source: "녹화", review: "hold", location: "여의도 환승센터" },
  { id: "k4", caseId: "c11", caseNumber: "CASE-2026-0407", image: "후보 캡처", camera: "CCTV-09", zone: "Zone B", detectedAt: "2026-07-21 13:40:05", similarity: 68, source: "녹화", review: "rejected", location: "건대입구역" }
];

export const chartSeries = [
  { date: "07-15", reports: 9, candidates: 3 },
  { date: "07-16", reports: 14, candidates: 6 },
  { date: "07-17", reports: 11, candidates: 5 },
  { date: "07-18", reports: 17, candidates: 7 },
  { date: "07-19", reports: 15, candidates: 8 },
  { date: "07-20", reports: 19, candidates: 10 },
  { date: "07-21", reports: 8, candidates: 4 }
];

export const monthlyChartSeries = [
  { date: "06-22", reports: 7, candidates: 2 },
  { date: "06-25", reports: 12, candidates: 5 },
  { date: "06-28", reports: 10, candidates: 4 },
  { date: "07-01", reports: 15, candidates: 7 },
  { date: "07-04", reports: 9, candidates: 3 },
  { date: "07-07", reports: 18, candidates: 9 },
  { date: "07-10", reports: 13, candidates: 6 },
  { date: "07-13", reports: 16, candidates: 8 },
  { date: "07-16", reports: 14, candidates: 6 },
  { date: "07-19", reports: 15, candidates: 8 },
  { date: "07-21", reports: 8, candidates: 4 }
];

export const scanJobs = [
  { id: "scan-1001-01", caseNumber: "CASE-2026-0417", camera: "CCTV-01", range: "07-21 09:00~14:00", status: "searching", progress: 82, createdAt: "14:05", finishedAt: "" },
  { id: "scan-1001-02", caseNumber: "CASE-2026-0417", camera: "CCTV-02", range: "07-21 09:00~14:00", status: "searching", progress: 76, createdAt: "14:05", finishedAt: "" },
  { id: "scan-1001-03", caseNumber: "CASE-2026-0417", camera: "CCTV-03", range: "07-21 09:00~14:00", status: "closed", progress: 100, createdAt: "14:05", finishedAt: "15:21" },
  { id: "scan-1001-04", caseNumber: "CASE-2026-0417", camera: "CCTV-04", range: "07-21 09:00~14:00", status: "candidate_found", progress: 100, createdAt: "14:05", finishedAt: "15:26" },
  { id: "scan-1002-09", caseNumber: "CASE-2026-0416", camera: "CCTV-09", range: "07-21 07:00~12:00", status: "closed", progress: 100, createdAt: "12:20", finishedAt: "13:02" },
  { id: "scan-1002-10", caseNumber: "CASE-2026-0416", camera: "CCTV-10", range: "07-21 07:00~12:00", status: "closed", progress: 100, createdAt: "12:20", finishedAt: "13:02" },
  { id: "scan-1002-11", caseNumber: "CASE-2026-0416", camera: "CCTV-11", range: "07-21 07:00~12:00", status: "failed", progress: 47, createdAt: "12:20", finishedAt: "" },
  { id: "scan-1003", caseNumber: "CASE-2026-0415", camera: "CCTV-04", range: "07-20 13:00~18:00", status: "failed", progress: 47, createdAt: "10:11", finishedAt: "" }
];

export const routePoints = [
  { time: "09:40:12", zone: "Zone A", camera: "CCTV-01", location: "테헤란로 152", note: "최초 목격 지점" },
  { time: "10:05:44", zone: "Zone A", camera: "CCTV-02", location: "역삼로 21", note: "도보 이동 확인" },
  { time: "11:22:03", zone: "Zone B", camera: "CCTV-09", location: "올림픽로 300", note: "구역 이동 확인" },
  { time: "14:18:52", zone: "Zone B", camera: "CCTV-11", location: "백제고분로 40", note: "최근 후보 위치" }
];

export const auditLogs = [
  { id: "l1", time: "07-21 14:32", actor: "김민준", type: "후보 판정", target: "CASE-0417", result: "성공", ip: "10.10.1.44", detail: "후보 k1 대상 확인 처리" },
  { id: "l2", time: "07-21 13:10", actor: "SYSTEM", type: "탐색 조건 변경", target: "CASE-0417", result: "성공", ip: "10.10.1.20", detail: "실시간 탐색 조건을 변경" },
  { id: "l3", time: "07-20 22:40", actor: "정하늘", type: "사건 상태 변경", target: "CASE-0416", result: "성공", ip: "10.10.1.45", detail: "탐색 중에서 후보 발견으로 변경" }
];

export const notifications = [
  { id: "n1", time: "2026-07-23 09:14", type: "실시간 후보 탐지", title: "신규 후보 발견", message: "CASE-2026-0417에서 유사도 91% 후보가 탐지되었습니다.", unread: true, route: "/admin/candidates/k1" },
  { id: "n2", time: "2026-07-23 08:52", type: "사건 상태 변경", title: "상태 변경", message: "CASE-2026-0416 상태가 후보 발견으로 변경되었습니다.", unread: true, route: "/admin/cases/c2" },
  { id: "n3", time: "2026-07-22 22:40", type: "CCTV 연결 없음", title: "CCTV-04 연결 없음", message: "영상 스트림 연결이 지연되고 있습니다.", unread: false, route: "/admin/cameras" }
];

export const users = [
  { id: "u1", name: "김민준", email: "minjun@eyesforu.local", role: "시스템 관리자", phone: "010-1000-2026", status: "활성", lastLogin: "2026-07-21 09:02" },
  { id: "u2", name: "정하늘", email: "haneul@eyesforu.local", role: "관제 관리자", phone: "010-2000-2026", status: "활성", lastLogin: "2026-07-21 08:42" },
  { id: "u3", name: "박서준", email: "seojun@eyesforu.local", role: "일반 관제자", phone: "010-3000-2026", status: "대기", lastLogin: "2026-07-20 22:10" }
];
