import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { RunSummary } from '../lib/types'
import { Alert, EmptyState, PageHeader, Spinner, StatusBadge, percent } from '../components/ui'

export default function Runs() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .runs()
      .then(setRuns)
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <Alert>{error}</Alert>
  if (!runs) return <Spinner />

  return (
    <div>
      <PageHeader title="Model registry" subtitle="Every training run, its metrics and deployment state." />
      {runs.length === 0 ? (
        <EmptyState title="No runs yet" hint="Train a model from a dataset to populate the registry." />
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-edge text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-5 py-3">Run</th>
                <th className="px-5 py-3">Algorithm</th>
                <th className="px-5 py-3">Target</th>
                <th className="px-5 py-3">CV score</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-b border-edge/50 last:border-0 hover:bg-white/5">
                  <td className="px-5 py-3 font-mono text-xs">
                    <Link className="text-accent hover:underline" to={`/runs/${run.id}`}>
                      {run.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-5 py-3">
                    {run.algorithm}
                    {run.is_deployed && (
                      <span className="badge ml-2 bg-emerald-500/15 text-emerald-300">deployed</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-slate-300">{run.target_column}</td>
                  <td className="px-5 py-3">{percent(run.cv_score)}</td>
                  <td className="px-5 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-5 py-3 text-slate-400">{new Date(run.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
