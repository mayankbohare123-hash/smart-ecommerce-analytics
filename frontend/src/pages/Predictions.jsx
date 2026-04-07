/**
 * Predictions.jsx
 * ───────────────
 * ML predictions page — shows 30-day forecast with model metrics.
 */
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Brain, RefreshCw, TrendingUp, Target, BarChart2, Layers, AlertCircle } from 'lucide-react'
import { useData } from '../context/DataContext'
import PredictionChart from '../components/PredictionChart'
import { getPredictions, retrainModel } from '../services/predictApi'

export default function Predictions() {
  const { selectedFileId, refreshFiles } = useData()
  const [data,     setData]     = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [retraining,setRetraining] = useState(false)
  const [error,    setError]    = useState(null)

  useEffect(() => { refreshFiles() }, [])

  useEffect(() => {
    if (!selectedFileId) return
    setData(null); setError(null); setLoading(true)
    getPredictions(selectedFileId)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selectedFileId])

  const handleRetrain = async () => {
    setRetraining(true); setError(null)
    try {
      const result = await retrainModel(selectedFileId)
      setData(result)
    } catch (e) { setError(e.message) }
    finally { setRetraining(false) }
  }

  if (!selectedFileId) {
    return (
      <div className="flex flex-col items-center justify-center flex-1 gap-4 py-20">
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          No dataset selected.{' '}
          <Link to="/upload" className="underline" style={{ color: 'var(--accent)' }}>Upload a file</Link>{' '}
          or select one from the sidebar.
        </p>
      </div>
    )
  }

  return (
    <div className="flex-1 p-6 space-y-6 page-enter overflow-y-auto">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            Sales Predictions
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
            30-day revenue forecast powered by machine learning
          </p>
        </div>
        <button
          onClick={handleRetrain}
          disabled={retraining || loading}
          className="btn-ghost text-sm"
        >
          <RefreshCw size={14} className={retraining ? 'animate-spin' : ''} />
          {retraining ? 'Retraining…' : 'Retrain Model'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="card p-4" style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
          <div className="flex items-center gap-2">
            <AlertCircle size={16} style={{ color: 'var(--danger)' }} />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{error}</p>
          </div>
        </div>
      )}

      {/* Model metrics */}
      {(loading || data) && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { icon: Brain,    label: 'Model Type',     value: loading ? '…' : data?.model_metrics?.model_type?.replace('_', ' '), color: '#6366f1' },
            { icon: Target,   label: 'Mean Abs. Error', value: loading ? '…' : `$${data?.model_metrics?.mae?.toLocaleString()}`, color: '#f59e0b' },
            { icon: BarChart2, label: 'R² Score',       value: loading ? '…' : data?.model_metrics?.r2_score?.toFixed(3), color: '#22c55e' },
            { icon: Layers,   label: 'Forecast Days',  value: loading ? '…' : data?.prediction_days, color: '#06b6d4' },
          ].map(({ icon: Icon, label, value, color }, i) => (
            <div key={label} className="card p-4">
              <div className="flex items-center gap-2 mb-2">
                <Icon size={14} style={{ color }} />
                <span className="section-label">{label}</span>
              </div>
              {loading
                ? <div className="skeleton h-6 w-24 rounded" />
                : <div className="stat-number text-lg font-semibold capitalize"
                    style={{ color: 'var(--text-primary)' }}>{value}</div>
              }
            </div>
          ))}
        </div>
      )}

      {/* Prediction chart */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Revenue Forecast
            </h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              60-day history + 30-day prediction with confidence interval
            </p>
          </div>
          {data && (
            <span className="badge-accent text-xs">
              <TrendingUp size={11} />
              {data.predictions?.length} days forecast
            </span>
          )}
        </div>
        <PredictionChart data={data?.chart_data} loading={loading} />
      </div>

      {/* Prediction table */}
      {data && (
        <div className="card">
          <div className="px-5 py-4 border-b flex items-center justify-between"
            style={{ borderColor: 'var(--border)' }}>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Daily Predictions
            </h3>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Total: ${data.predictions?.reduce((s, p) => s + p.predicted_revenue, 0)
                .toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </span>
          </div>
          <div className="overflow-x-auto max-h-72 overflow-y-auto">
            <table className="w-full text-sm border-collapse">
              <thead className="sticky top-0" style={{ background: 'var(--bg-elevated)' }}>
                <tr>
                  {['Date', 'Predicted Revenue', 'Lower Bound', 'Upper Bound'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide"
                      style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.predictions?.map((p, i) => (
                  <tr key={i} className="hover:bg-white/[0.02] transition-colors"
                    style={{ borderBottom: i < data.predictions.length - 1 ? '1px solid var(--border)' : 'none' }}>
                    <td className="px-4 py-2.5 stat-number text-xs" style={{ color: 'var(--text-secondary)' }}>{p.date}</td>
                    <td className="px-4 py-2.5 stat-number text-xs font-medium" style={{ color: '#818cf8' }}>
                      ${p.predicted_revenue.toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 stat-number text-xs" style={{ color: 'var(--text-muted)' }}>
                      ${p.lower_bound.toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 stat-number text-xs" style={{ color: 'var(--text-muted)' }}>
                      ${p.upper_bound.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
