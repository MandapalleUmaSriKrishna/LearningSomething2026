import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../lib/api'
import type { Dataset, Prediction, Run } from '../lib/types'
import { Alert, PageHeader, Spinner, Stat, StatusBadge, percent } from '../components/ui'

const chartTheme = {
  grid: '#1e2a45',
  axis: '#64748b',
  tooltip: { background: '#111c33', border: '1px solid #1e2a45', borderRadius: 8, color: '#e2e8f0' },
}

export default function RunDetail() {
  const { runId = '' } = useParams()
  const [run, setRun] = useState<Run | null>(null)
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  const [predictions, setPredictions] = useState<Prediction[] | null>(null)
  const [predicting, setPredicting] = useState(false)

  useEffect(() => {
    api
      .run(runId)
      .then(async (data) => {
        setRun(data)
        setDataset(await api.dataset(data.dataset_id))
      })
      .catch((err) => setError(err.message))
  }, [runId])

  const featureColumns = useMemo(() => {
    if (!dataset || !run) return []
    return dataset.profile.column_profiles
      .filter((column) => column.name !== run.target_column)
      .slice(0, 12)
  }, [dataset, run])

  if (error && !run) return <Alert>{error}</Alert>
  if (!run || !dataset) return <Spinner />

  const metrics = run.metrics
  const roc = metrics.roc_curve ?? []
  const importances = [...(metrics.feature_importances ?? [])].reverse()

  async function onDeploy() {
    try {
      setRun(await api.deploy(runId))
      setNotice('Model deployed as the active classifier for this dataset.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deploy failed')
    }
  }

  async function onPredict() {
    setPredicting(true)
    setError('')
    try {
      const record: Record<string, unknown> = {}
      for (const column of featureColumns) {
        const raw = formValues[column.name] ?? ''
        record[column.name] = column.kind === 'numeric' && raw !== '' ? Number(raw) : raw
      }
      const response = await api.predict(runId, [record])
      setPredictions(response.predictions)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Prediction failed')
    } finally {
      setPredicting(false)
    }
  }

  return (
    <div>
      <PageHeader
        title={`${run.algorithm} · ${run.target_column}`}
        subtitle={`Trained ${new Date(run.created_at).toLocaleString()} on “${dataset.name}” in ${run.duration_seconds ?? '—'}s`}
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={run.status} />
            {run.is_deployed ? (
              <span className="badge bg-emerald-500/15 text-emerald-300">deployed</span>
            ) : (
              <button className="btn-primary" onClick={onDeploy} type="button">
                Deploy
              </button>
            )}
          </div>
        }
      />

      {notice && (
        <div className="mb-4">
          <Alert kind="success">{notice}</Alert>
        </div>
      )}
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Accuracy" value={percent(metrics.accuracy)} hint={`baseline ${percent(metrics.baseline.accuracy)}`} />
        <Stat label="F1" value={percent(metrics.f1)} />
        <Stat label="Precision" value={percent(metrics.precision)} />
        <Stat label="Recall" value={percent(metrics.recall)} />
        <Stat
          label="ROC AUC"
          value={percent(metrics.roc_auc ?? null)}
          hint={`${metrics.cv.folds}-fold CV ${percent(metrics.cv.mean_score)}`}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {roc.length > 0 && (
          <div className="card">
            <h2 className="mb-4 text-sm font-semibold">ROC curve</h2>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={roc}>
                <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
                <XAxis dataKey="fpr" stroke={chartTheme.axis} tickFormatter={(v) => v.toFixed(1)} />
                <YAxis stroke={chartTheme.axis} tickFormatter={(v) => v.toFixed(1)} />
                <Tooltip contentStyle={chartTheme.tooltip} />
                <Line type="monotone" dataKey="tpr" stroke="#38bdf8" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        <div className="card">
          <h2 className="mb-4 text-sm font-semibold">Top feature importances</h2>
          {importances.length === 0 ? (
            <p className="text-sm text-slate-400">Not available for this model.</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(260, importances.length * 22)}>
              <BarChart data={importances} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" stroke={chartTheme.axis} />
                <YAxis type="category" dataKey="feature" width={150} stroke={chartTheme.axis} fontSize={11} />
                <Tooltip contentStyle={chartTheme.tooltip} />
                <Bar dataKey="importance" fill="#38bdf8" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card">
          <h2 className="mb-4 text-sm font-semibold">Algorithm leaderboard (CV {metrics.cv.scoring})</h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={metrics.leaderboard}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke={chartTheme.axis} fontSize={11} />
              <YAxis stroke={chartTheme.axis} domain={[0, 1]} />
              <Tooltip contentStyle={chartTheme.tooltip} />
              <Legend />
              <Bar dataKey="cv_score" name="CV score" radius={[4, 4, 0, 0]}>
                {metrics.leaderboard.map((entry) => (
                  <Cell key={entry.algorithm} fill={entry.algorithm === run.algorithm ? '#38bdf8' : '#334155'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2 className="mb-4 text-sm font-semibold">Confusion matrix (test split)</h2>
          <div className="overflow-x-auto">
            <table className="text-sm">
              <thead>
                <tr>
                  <th className="px-3 py-2 text-left text-xs uppercase text-slate-400">actual \ pred</th>
                  {metrics.classes.map((label) => (
                    <th key={label} className="px-3 py-2 text-xs uppercase text-slate-400">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metrics.confusion_matrix.map((row, rowIndex) => {
                  const total = row.reduce((sum, value) => sum + value, 0) || 1
                  return (
                    <tr key={metrics.classes[rowIndex]}>
                      <td className="px-3 py-2 text-xs uppercase text-slate-400">
                        {metrics.classes[rowIndex]}
                      </td>
                      {row.map((value, columnIndex) => (
                        <td key={columnIndex} className="px-1 py-1">
                          <div
                            className="rounded-md px-4 py-3 text-center font-medium"
                            style={{
                              background: `rgba(56, 189, 248, ${Math.min(0.85, value / total)})`,
                              color: value / total > 0.45 ? '#0f172a' : '#e2e8f0',
                            }}
                          >
                            {value}
                          </div>
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            {metrics.train_samples} train / {metrics.test_samples} test samples · tuned params:{' '}
            {Object.keys(run.best_params).length ? JSON.stringify(run.best_params) : 'defaults'}
          </p>
        </div>
      </div>

      <h2 className="mb-3 mt-8 text-lg font-semibold">Score a record</h2>
      <div className="card grid gap-4 lg:grid-cols-[2fr,1fr]">
        <div className="grid gap-3 sm:grid-cols-2">
          {featureColumns.map((column) => (
            <div key={column.name}>
              <label className="label" htmlFor={`f-${column.name}`}>
                {column.name}
              </label>
              <input
                id={`f-${column.name}`}
                className="input"
                type={column.kind === 'numeric' ? 'number' : 'text'}
                step="any"
                value={formValues[column.name] ?? ''}
                placeholder={column.kind === 'numeric' ? String(column.mean ?? 0) : column.top_values?.[0]?.value}
                onChange={(event) =>
                  setFormValues((current) => ({ ...current, [column.name]: event.target.value }))
                }
              />
            </div>
          ))}
        </div>
        <div className="flex flex-col justify-between gap-4">
          <button className="btn-primary" onClick={onPredict} type="button" disabled={predicting}>
            {predicting ? 'Scoring…' : 'Predict'}
          </button>
          {predictions?.[0] && (
            <div className="rounded-lg border border-edge bg-slate-900/60 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-400">Prediction</p>
              <p className="mt-1 text-2xl font-semibold text-accent">{predictions[0].prediction}</p>
              <p className="text-xs text-slate-400">confidence {percent(predictions[0].confidence)}</p>
              <div className="mt-3 space-y-1">
                {Object.entries(predictions[0].probabilities).map(([label, probability]) => (
                  <div key={label} className="text-xs">
                    <div className="flex justify-between text-slate-400">
                      <span>{label}</span>
                      <span>{percent(probability)}</span>
                    </div>
                    <div className="mt-0.5 h-1.5 rounded bg-edge">
                      <div className="h-1.5 rounded bg-accent" style={{ width: `${probability * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
