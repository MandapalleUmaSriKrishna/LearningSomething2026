import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Dataset } from '../lib/types'
import { Alert, PageHeader, Spinner } from '../components/ui'

export default function DatasetDetail() {
  const { datasetId = '' } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [preview, setPreview] = useState<{ columns: string[]; rows: Record<string, unknown>[] } | null>(null)
  const [algorithms, setAlgorithms] = useState<{ value: string; label: string }[]>([])
  const [error, setError] = useState('')
  const [training, setTraining] = useState(false)

  const [target, setTarget] = useState('')
  const [algorithm, setAlgorithm] = useState('auto')
  const [scoring, setScoring] = useState('f1_weighted')
  const [testSize, setTestSize] = useState(0.2)
  const [folds, setFolds] = useState(5)
  const [tune, setTune] = useState(true)

  const canTrain = user?.role === 'admin' || user?.role === 'analyst'

  useEffect(() => {
    Promise.all([api.dataset(datasetId), api.datasetPreview(datasetId), api.algorithms()])
      .then(([data, previewData, algos]) => {
        setDataset(data)
        setPreview(previewData)
        setAlgorithms(algos)
        const candidate =
          data.profile.column_profiles.find((column) => column.candidate_target) ??
          data.profile.column_profiles[data.profile.column_profiles.length - 1]
        setTarget(candidate?.name ?? '')
      })
      .catch((err) => setError(err.message))
  }, [datasetId])

  async function onTrain(event: FormEvent) {
    event.preventDefault()
    setError('')
    setTraining(true)
    try {
      const run = await api.train({
        dataset_id: datasetId,
        target_column: target,
        algorithm,
        scoring,
        test_size: testSize,
        cv_folds: folds,
        tune_hyperparameters: tune,
      })
      navigate(`/runs/${run.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Training failed')
    } finally {
      setTraining(false)
    }
  }

  if (error && !dataset) return <Alert>{error}</Alert>
  if (!dataset) return <Spinner />

  return (
    <div>
      <PageHeader
        title={dataset.name}
        subtitle={`${dataset.row_count.toLocaleString()} rows · ${dataset.column_count} columns · sha256 ${dataset.checksum_sha256.slice(0, 12)}…`}
      />

      <div className="grid gap-6 lg:grid-cols-[1.4fr,1fr]">
        <div className="card overflow-hidden p-0">
          <h2 className="border-b border-edge px-5 py-3 text-sm font-semibold">Column profile</h2>
          <div className="max-h-[420px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-panel text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-5 py-2">Column</th>
                  <th className="px-5 py-2">Type</th>
                  <th className="px-5 py-2">Unique</th>
                  <th className="px-5 py-2">Missing</th>
                </tr>
              </thead>
              <tbody>
                {dataset.profile.column_profiles.map((column) => (
                  <tr key={column.name} className="border-b border-edge/40 last:border-0">
                    <td className="px-5 py-2 font-medium">
                      {column.name}
                      {column.candidate_target && (
                        <span className="badge ml-2 bg-sky-500/15 text-sky-300">target?</span>
                      )}
                    </td>
                    <td className="px-5 py-2 text-slate-400">{column.kind}</td>
                    <td className="px-5 py-2 text-slate-300">{column.unique}</td>
                    <td className="px-5 py-2 text-slate-300">{column.missing_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <form onSubmit={onTrain} className="card space-y-4">
          <h2 className="text-sm font-semibold">Train a classifier</h2>
          {error && <Alert>{error}</Alert>}
          <div>
            <label className="label" htmlFor="target">
              Target column
            </label>
            <select
              id="target"
              className="input"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
            >
              {dataset.profile.column_profiles.map((column) => (
                <option key={column.name} value={column.name}>
                  {column.name} ({column.unique} classes)
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="algorithm">
              Algorithm
            </label>
            <select
              id="algorithm"
              className="input"
              value={algorithm}
              onChange={(event) => setAlgorithm(event.target.value)}
            >
              {algorithms.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="scoring">
                CV metric
              </label>
              <select
                id="scoring"
                className="input"
                value={scoring}
                onChange={(event) => setScoring(event.target.value)}
              >
                <option value="f1_weighted">F1 (weighted)</option>
                <option value="accuracy">Accuracy</option>
                <option value="balanced_accuracy">Balanced accuracy</option>
                <option value="roc_auc">ROC AUC</option>
              </select>
            </div>
            <div>
              <label className="label" htmlFor="folds">
                CV folds
              </label>
              <input
                id="folds"
                className="input"
                type="number"
                min={2}
                max={10}
                value={folds}
                onChange={(event) => setFolds(Number(event.target.value))}
              />
            </div>
          </div>
          <div>
            <label className="label" htmlFor="testSize">
              Test split: {(testSize * 100).toFixed(0)}%
            </label>
            <input
              id="testSize"
              type="range"
              className="w-full accent-sky-400"
              min={0.1}
              max={0.5}
              step={0.05}
              value={testSize}
              onChange={(event) => setTestSize(Number(event.target.value))}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              className="h-4 w-4 accent-sky-400"
              checked={tune}
              onChange={(event) => setTune(event.target.checked)}
            />
            Tune hyperparameters (randomized search)
          </label>
          <button className="btn-primary w-full" type="submit" disabled={!canTrain || training}>
            {training ? 'Training…' : canTrain ? 'Train model' : 'Viewer role cannot train'}
          </button>
        </form>
      </div>

      {preview && (
        <>
          <h2 className="mb-3 mt-8 text-lg font-semibold">Data preview</h2>
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-edge uppercase tracking-wide text-slate-400">
                <tr>
                  {preview.columns.map((column) => (
                    <th key={column} className="px-4 py-2">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.slice(0, 10).map((row, index) => (
                  <tr key={index} className="border-b border-edge/40 last:border-0">
                    {preview.columns.map((column) => (
                      <td key={column} className="px-4 py-2 text-slate-300">
                        {String(row[column] ?? '')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
