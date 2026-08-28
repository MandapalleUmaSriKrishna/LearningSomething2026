import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Alert, PageHeader } from '../components/ui'

export default function Account() {
  const { user, logout } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')
    try {
      await api.changePassword(current, next)
      setNotice('Password changed. All other sessions were signed out.')
      setCurrent('')
      setNext('')
      setTimeout(() => void logout(), 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not change password')
    }
  }

  return (
    <div className="max-w-xl">
      <PageHeader title="Account" subtitle={`${user?.email} · role ${user?.role}`} />
      <form onSubmit={onSubmit} className="card space-y-4">
        {error && <Alert>{error}</Alert>}
        {notice && <Alert kind="success">{notice}</Alert>}
        <div>
          <label className="label" htmlFor="current">
            Current password
          </label>
          <input
            id="current"
            className="input"
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="next">
            New password
          </label>
          <input
            id="next"
            className="input"
            type="password"
            autoComplete="new-password"
            minLength={12}
            required
            value={next}
            onChange={(event) => setNext(event.target.value)}
          />
          <p className="mt-1 text-xs text-slate-500">
            Minimum 12 characters with upper case, lower case, a digit and a symbol.
          </p>
        </div>
        <button className="btn-primary" type="submit">
          Update password
        </button>
      </form>
    </div>
  )
}
