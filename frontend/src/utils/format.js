/** Shared formatting helpers for billing screens. */

// The API sends naive-UTC ISO strings ("2026-10-22T10:00:00"); without a "Z"
// the browser would read them as LOCAL time and shift dates by the UTC offset.
export function parseUtc(iso) {
  if (!iso) return null
  return new Date(/Z|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
}

export function formatDate(iso) {
  const d = parseUtc(iso)
  return d ? d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '—'
}

export function formatMoney(cents, currency = 'usd') {
  const whole = cents % 100 === 0
  return (cents / 100).toLocaleString('en-US', {
    style: 'currency',
    currency: (currency || 'usd').toUpperCase(),
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: 2,
  })
}

export function formatDateTime(iso) {
  const d = parseUtc(iso)
  return d ? d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'
}

/** '2026-10' → 'Oct 26' for chart labels */
export function monthLabel(ym) {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
}
