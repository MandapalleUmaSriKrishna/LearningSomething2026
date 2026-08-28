import type { ReactNode } from 'react'

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
      </div>
      {actions}
    </div>
  )
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="card">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-50">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

export function Alert({ kind = 'error', children }: { kind?: 'error' | 'info' | 'success'; children: ReactNode }) {
  const styles = {
    error: 'border-rose-500/40 bg-rose-500/10 text-rose-200',
    info: 'border-sky-500/40 bg-sky-500/10 text-sky-200',
    success: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200',
  }[kind]
  return <div className={`rounded-lg border px-4 py-3 text-sm ${styles}`}>{children}</div>
}

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    succeeded: 'bg-emerald-500/15 text-emerald-300',
    failed: 'bg-rose-500/15 text-rose-300',
    running: 'bg-amber-500/15 text-amber-300',
    pending: 'bg-slate-500/15 text-slate-300',
  }
  return <span className={`badge ${styles[status] ?? 'bg-slate-500/15 text-slate-300'}`}>{status}</span>
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-sm text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-accent" />
      {label}
    </div>
  )
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card border-dashed text-center">
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

export const percent = (value: number | null | undefined) =>
  value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`
