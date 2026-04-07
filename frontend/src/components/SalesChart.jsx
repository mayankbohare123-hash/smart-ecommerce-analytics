/**
 * SalesChart.jsx
 * ──────────────
 * Monthly revenue trend — dual Y-axis line chart.
 * Left axis: revenue ($), Right axis: order count.
 */
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement,
  LineElement, BarElement, ArcElement,
  Title, Tooltip, Legend, Filler,
} from 'chart.js'
import { Line } from 'react-chartjs-2'

ChartJS.register(
  CategoryScale, LinearScale, PointElement,
  LineElement, BarElement, ArcElement,
  Title, Tooltip, Legend, Filler,
)

const GRID   = 'rgba(255,255,255,0.05)'
const TICK   = '#4a5568'
const FONT   = "'DM Sans', sans-serif"

function baseScaleOpts(label = '') {
  return {
    grid: { color: GRID, drawBorder: false },
    ticks: {
      color: TICK,
      font: { family: FONT, size: 11 },
      ...(label ? { callback: (v) => `$${(v / 1000).toFixed(0)}k` } : {}),
    },
    border: { display: false },
  }
}

export default function SalesChart({ data, loading }) {
  if (loading) return <div className="skeleton w-full h-64 rounded-xl" />
  if (!data)   return null

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        labels: { color: '#8892a4', font: { family: FONT, size: 11 }, boxWidth: 12, padding: 16 },
      },
      tooltip: {
        backgroundColor: '#111c30',
        borderColor: 'rgba(255,255,255,0.08)',
        borderWidth: 1,
        titleColor: '#e8eaf0',
        bodyColor: '#8892a4',
        callbacks: {
          label: (ctx) =>
            ctx.datasetIndex === 0
              ? ` Revenue: $${Number(ctx.raw).toLocaleString()}`
              : ` Orders: ${Number(ctx.raw).toLocaleString()}`,
        },
      },
    },
    scales: {
      x: baseScaleOpts(),
      y:  { ...baseScaleOpts('$'), position: 'left' },
      y1: {
        ...baseScaleOpts(),
        position: 'right',
        grid: { display: false },
      },
    },
  }

  // Assign second dataset to y1 axis
  const chartData = {
    ...data,
    datasets: data.datasets.map((ds, i) => ({
      ...ds,
      yAxisID: i === 1 ? 'y1' : 'y',
      pointRadius: 3,
      pointHoverRadius: 6,
    })),
  }

  return (
    <div style={{ height: '280px' }}>
      <Line data={chartData} options={options} />
    </div>
  )
}
