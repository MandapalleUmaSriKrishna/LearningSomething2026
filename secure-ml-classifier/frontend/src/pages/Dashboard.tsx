import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { Stats } from '../lib/types'
import { Alert, EmptyState, PageHeader, Spinner, Stat, StatusBadge, percent } from '../components/ui'

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <Alert>{error}</Alert>
  if (!stats) return <Spinner />

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Datasets, training runs and deployed classifiers at a glance."
        actions={
          <Link className="btn-primary" to="/datasets">
            Upload dataset
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Datasets" value={stats.datasets} />
        <Stat label="Training runs" value={stats.runs} />
        <Stat label="Deployed models" value={stats.deployed_models} />
        <Stat
          label="Best CV score"
          value={percent(stats.best_cv_score)}
          hint="Cross-validated, held out from the test split"
        />
      </div>

      <h2 className="mb-3 mt-8 text-lg font-semibold">Recent runs</h2>
      {stats.recent_runs.length === 0 ? (
        <EmptyState title="No training runs yet" hint="Upload a CSV and train your first classifier." />
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-edge text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-5 py-3">Algorithm</th>
                <th className="px-5 py-3">Target</th>
                <th className="px-5 py-3">CV score</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_runs.map((run) => (
                <tr key={run.id} className="border-b border-edge/50 last:border-0 hover:bg-white/5">
                  <td className="px-5 py-3">
                    <Link className="text-accent hover:underline" to={`/runs/${run.id}`}>
                      {run.algorithm}
                    </Link>
                    {run.is_deployed && (
                      <span className="badge ml-2 bg-emerald-500/15 text-emerald-300">deployed</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-slate-300">{run.target_column}</td>
                  <td className="px-5 py-3">{percent(run.cv_score)}</td>
                  <td className="px-5 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-5 py-3 text-slate-400">
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
