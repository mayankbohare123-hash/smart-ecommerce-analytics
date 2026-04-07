/**
 * PredictionChart.jsx
 * ────────────────────
 * Combined historical + forecast line chart with confidence band.
 * Shows a vertical separator between history and forecast regions.
 */
import { Line } from 'react-chartjs-2'

const FONT = "'DM Sans', sans-serif"
const GRID = 'rgba(255,255,255,0.05)'
const TICK = '#4a5568'

export default function PredictionChart({ data, loading }) {
  if (loading) return <div className="skeleton w-full h-72 rounded-xl" />
  if (!data)   return null

  // Find the index where historical data ends (first null in dataset[0])
  const splitIdx = data.datasets[0]?.data?.findIndex(v => v === null)

  // Custom plugin to draw a dashed vertical line at the forecast boundary
  const splitLinePlugin = {
    id: 'splitLine',
    afterDraw(chart) {
      if (splitIdx < 0) return
      const { ctx, chartArea: { top, bottom }, scales: { x } } = chart
      const xPos = x.getPixelForIndex(splitIdx)
      ctx.save()
      ctx.beginPath()
      ctx.setLineDash([4, 4])
      ctx.strokeStyle = 'rgba(245,158,11,0.4)'
      ctx.lineWidth = 1
      ctx.moveTo(xPos, top)
      ctx.lineTo(xPos, bottom)
      ctx.stroke()
      ctx.restore()

      // "Forecast" label
      ctx.save()
      ctx.font = `11px ${FONT}`
      ctx.fillStyle = 'rgba(245,158,11,0.7)'
      ctx.fillText('▶ Forecast', xPos + 6, top + 16)
      ctx.restore()
    },
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    spanGaps: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#8892a4',
          font: { family: FONT, size: 11 },
          boxWidth: 12,
          padding: 16,
          filter: (item) => !['Upper Bound', 'Lower Bound'].includes(item.text),
        },
      },
      tooltip: {
        backgroundColor: '#111c30',
        borderColor: 'rgba(255,255,255,0.08)',
        borderWidth: 1,
        titleColor: '#e8eaf0',
        bodyColor: '#8892a4',
        callbacks: {
          label: (ctx) => {
            if (ctx.raw === null) return null
            const label = ctx.dataset.label || ''
            if (label.includes('Bound')) return null
            return ` ${label}: $${Number(ctx.raw).toLocaleString()}`
          },
          afterBody: (items) => {
            const idx = items[0]?.dataIndex
            if (idx === undefined) return []
            const upper = data.datasets[2]?.data?.[idx]
            const lower = data.datasets[3]?.data?.[idx]
            if (upper != null && lower != null) {
              return [`  Range: $${Number(lower).toLocaleString()} – $${Number(upper).toLocaleString()}`]
            }
            return []
          },
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
          maxTicksLimit: 12,
          maxRotation: 0,
        },
      },
      y: {
        grid: { color: GRID, drawBorder: false },
        border: { display: false },
        ticks: {
          color: TICK,
          font: { family: FONT, size: 11 },
          callback: (v) => `$${(v / 1000).toFixed(0)}k`,
        },
      },
    },
  }

  // Build confidence band: fill between upper and lower
  const chartData = {
    labels: data.labels,
    datasets: [
      { ...data.datasets[0], pointRadius: 0, pointHoverRadius: 4 },
      {
        ...data.datasets[1],
        pointRadius: 3,
        pointHoverRadius: 6,
        borderDash: [6, 3],
      },
      {
        ...data.datasets[2],
        fill: '+1',
        backgroundColor: 'rgba(245,158,11,0.08)',
        pointRadius: 0,
      },
      {
        ...data.datasets[3],
        fill: false,
        backgroundColor: 'transparent',
        pointRadius: 0,
      },
    ],
  }

  return (
    <div style={{ height: '300px' }}>
      <Line data={chartData} options={options} plugins={[splitLinePlugin]} />
    </div>
  )
}
