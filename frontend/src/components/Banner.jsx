/** Banner.jsx — inline message box: tone = 'error' | 'warn' | 'ok'. */
import { AlertCircle } from 'lucide-react'

export default function Banner({ tone, children }) {
  const tones = {
    error: ['rgba(239,68,68,0.10)', 'rgba(239,68,68,0.3)', '#f87171'],
    warn: ['rgba(245,158,11,0.10)', 'rgba(245,158,11,0.3)', '#fbbf24'],
    ok: ['rgba(34,197,94,0.10)', 'rgba(34,197,94,0.3)', '#4ade80'],
  }[tone]
  return (
    <div className="flex items-start gap-2 p-3 rounded-lg mb-5 text-sm"
      style={{ background: tones[0], border: `1px solid ${tones[1]}`, color: tones[2] }}>
      <AlertCircle size={16} className="mt-0.5 shrink-0" />
      <div>{children}</div>
    </div>
  )
}
