import { Bar } from "react-chartjs-2";
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

export function StatisticsChart({ range, setRange, data }) {
  const chartData = {
    labels: data.map((item) => item.date),
    datasets: [
      { label: "신고 접수", data: data.map((item) => item.reports), backgroundColor: "#4f8fcb", borderRadius: 5 },
      { label: "후보 탐지", data: data.map((item) => item.candidates), backgroundColor: "#d7a642", borderRadius: 5 }
    ]
  };

  return (
    <section className="content-panel chart-panel">
      <div className="section-heading">
        <div>
          <h2>사건 및 후보 탐지 현황</h2>
          <p>기간 필터를 변경하면 Mock API를 다시 조회합니다.</p>
        </div>
        <select value={range} onChange={(e) => setRange(e.target.value)}>
          <option value="7d">최근 7일</option>
          <option value="14d">최근 14일</option>
          <option value="30d">최근 30일</option>
        </select>
      </div>
      <div className="chart-box">
        <Bar
          data={chartData}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: { y: { beginAtZero: true } }
          }}
        />
      </div>
    </section>
  );
}
