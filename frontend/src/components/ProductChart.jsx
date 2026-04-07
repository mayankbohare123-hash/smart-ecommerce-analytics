/**
 * ProductChart.jsx  — Top products horizontal bar + Category doughnut
 * ────────────────────────────────────────────────────────────────────
 * Both exported from this file since they share Chart.js config.
 */
import { Bar, Doughnut } from 'react-chartjs-2'

const FONT = "'DM Sans', sans-serif"
const GRID = 'rgba(255,255,255,0.05)'
const TICK = '#4a5568'

const tooltip = {
  backgroundColor: '#111c30',
  borderColor: 'rgba(255,255,255,0.08)',
  borderWidth: 1,
  titleColor: '#e8eaf0',
  bodyColor: '#8892a4',
}

// ── Top Products Bar Chart ─────────────────────────────────────────────────

export function ProductChart({ data, loading }) {
  if (loading) return <div className="skeleton w-full h-64 rounded-xl" />
  if (!data)   return null

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
      legend: { display: false },
      tooltip: {
        ...tooltip,
        callbacks: {
          label: (ctx) => ` $${Number(ctx.raw).toLocaleString()}`,
        },
      },
    },
    scales: {
      x: {
        grid: { color: GRID, drawBorder: false },
        border: { display: false },
        ticks: {
          color: TICK,
          font: { family: FONT, size: 10 },
          callback: (v) => `$${(v / 1000).toFixed(0)}k`,
        },
      },
      y: {
        grid: { display: false },
        border: { display: false },
        ticks: { color: '#8892a4', font: { family: FONT, size: 11 } },
      },
    },
  }

  return (
    <div style={{ height: '280px' }}>
      <Bar data={data} options={options} />
    </div>
  )
}

// ── Category Doughnut Chart ────────────────────────────────────────────────

export function CategoryChart({ data, loading }) {
  if (loading) return <div className="skeleton w-full h-64 rounded-xl" />
  if (!data)   return null

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '68%',
    plugins: {
      legend: {
        position: 'right',
        labels: {
          color: '#8892a4',
          font: { family: FONT, size: 11 },
          boxWidth: 10,
          padding: 12,
          generateLabels: (chart) => {
            const ds  = chart.data.datasets[0]
            const total = ds.data.reduce((a, b) => a + b, 0)
            return chart.data.labels.map((label, i) => ({
              text: `${label}  ${((ds.data[i] / total) * 100).toFixed(1)}%`,
              fillStyle: ds.backgroundColor[i],
              strokeStyle: 'transparent',
              index: i,
            }))
          },
        },
      },
      tooltip: {
        ...tooltip,
        callbacks: {
          label: (ctx) => ` $${Number(ctx.raw).toLocaleString()}`,
        },
      },
    },
  }

  return (
    <div style={{ height: '280px' }}>
      <Doughnut data={data} options={options} />
    </div>
  )
}

// ── Region Bar Chart ───────────────────────────────────────────────────────

export function RegionChart({ data, loading }) {
  if (loading) return <div className="skeleton w-full h-48 rounded-xl" />
  if (!data)   return null

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
      legend: {
        position: 'top',
        labels: { color: '#8892a4', font: { family: FONT, size: 11 }, boxWidth: 10, padding: 14 },
      },
      tooltip: {
        ...tooltip,
        callbacks: {
          label: (ctx) =>
            ctx.datasetIndex === 0
              ? ` Revenue: $${Number(ctx.raw).toLocaleString()}`
              : ` Orders: ${Number(ctx.raw).toLocaleString()}`,
        },
      },
    },
    scales: {
      x: {
        grid: { color: GRID, drawBorder: false },
        border: { display: false },
        ticks: {
          color: TICK,
          font: { family: FONT, size: 10 },
          callback: (v) => `$${(v / 1000).toFixed(0)}k`,
        },
      },
      y: {
        grid: { display: false },
        border: { display: false },
        ticks: { color: '#8892a4', font: { family: FONT, size: 11 } },
      },
    },
  }

  return (
    <div style={{ height: '220px' }}>
      <Bar data={data} options={options} />
    </div>
  )
}
