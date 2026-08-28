import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { DatasetSummary } from '../lib/types'
import { Alert, EmptyState, PageHeader, Spinner } from '../components/ui'

const MAX_MB = 25

export default function Datasets() {
  const { user } = useAuth()
  const [datasets, setDatasets] = useState<DatasetSummary[] | null>(null)
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const canWrite = user?.role === 'admin' || user?.role === 'analyst'

  const load = () =>
    api
      .datasets()
      .then(setDatasets)
      .catch((err) => setError(err.message))

  useEffect(() => {
    void load()
  }, [])

  async function onUpload(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')
    if (!file) return setError('Choose a .csv file first.')
    if (!file.name.toLowerCase().endsWith('.csv')) return setError('Only .csv files are accepted.')
    if (file.size > MAX_MB * 1024 * 1024) return setError(`File must be smaller than ${MAX_MB} MB.`)

    setBusy(true)
    try {
      const dataset = await api.uploadDataset(file, name)
      setNotice(`Uploaded “${dataset.name}” — ${dataset.row_count} rows × ${dataset.column_count} columns.`)
      setName('')
      setFile(null)
      if (inputRef.current) inputRef.current.value = ''
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  async function onDelete(id: string) {
    if (!confirm('Delete this dataset and its training runs?')) return
    try {
      await api.deleteDataset(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  return (
    <div>
      <PageHeader title="Datasets" subtitle="Upload your own CSV files — nothing is bundled or shared." />

      {canWrite && (
        <form onSubmit={onUpload} className="card mb-6 space-y-4">
          <div className="grid gap-4 md:grid-cols-[2fr,1fr,auto] md:items-end">
            <div>
              <label className="label" htmlFor="file">
                CSV file (max {MAX_MB} MB)
              </label>
              <input
                id="file"
                ref={inputRef}
                className="input file:mr-3 file:rounded file:border-0 file:bg-edge file:px-3 file:py-1 file:text-slate-200"
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </div>
            <div>
              <label className="label" htmlFor="name">
                Display name (optional)
              </label>
              <input
                id="name"
                className="input"
                value={name}
                maxLength={120}
                onChange={(event) => setName(event.target.value)}
                placeholder="Customer churn Q3"
              />
            </div>
            <button className="btn-primary" type="submit" disabled={busy}>
              {busy ? 'Uploading…' : 'Upload'}
            </button>
          </div>
          <p className="text-xs text-slate-500">
            Files are validated, checksummed (SHA-256) and sanitized against CSV formula injection before
            storage.
          </p>
          {error && <Alert>{error}</Alert>}
          {notice && <Alert kind="success">{notice}</Alert>}
        </form>
      )}

      {!datasets ? (
        <Spinner />
      ) : datasets.length === 0 ? (
        <EmptyState title="No datasets yet" hint="Upload a CSV to get started." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {datasets.map((dataset) => (
            <div key={dataset.id} className="card flex flex-col justify-between">
              <div>
                <h3 className="text-base font-semibold text-slate-100">{dataset.name}</h3>
                <p className="mt-1 text-xs text-slate-400">
                  {dataset.row_count.toLocaleString()} rows · {dataset.column_count} columns
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {new Date(dataset.created_at).toLocaleString()}
                </p>
              </div>
              <div className="mt-4 flex gap-2">
                <Link className="btn-ghost flex-1" to={`/datasets/${dataset.id}`}>
                  Explore & train
                </Link>
                {canWrite && (
                  <button className="btn-danger" onClick={() => onDelete(dataset.id)} type="button">
                    Delete
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
