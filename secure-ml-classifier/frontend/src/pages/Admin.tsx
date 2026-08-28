import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../lib/api'
import type { AuditEntry, Role, User } from '../lib/types'
import { Alert, PageHeader, Spinner } from '../components/ui'

const ROLES: Role[] = ['admin', 'analyst', 'viewer']

export default function Admin() {
  const [users, setUsers] = useState<User[] | null>(null)
  const [logs, setLogs] = useState<AuditEntry[] | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('analyst')
  const [busy, setBusy] = useState(false)

  const load = () =>
    Promise.all([api.users(), api.auditLogs(100)])
      .then(([userList, logList]) => {
        setUsers(userList)
        setLogs(logList)
      })
      .catch((err) => setError(err.message))

  useEffect(() => {
    void load()
  }, [])

  async function onCreate(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')
    setBusy(true)
    try {
      const user = await api.createUser(email, password, role)
      setNotice(`Created ${user.email} as ${user.role}.`)
      setEmail('')
      setPassword('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create user')
    } finally {
      setBusy(false)
    }
  }

  async function onUpdate(id: string, patch: { role?: Role; is_active?: boolean }) {
    setError('')
    try {
      await api.updateUser(id, patch)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed')
    }
  }

  return (
    <div>
      <PageHeader title="Security & access" subtitle="User administration and the immutable audit trail." />
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {notice && (
        <div className="mb-4">
          <Alert kind="success">{notice}</Alert>
        </div>
      )}

      <form onSubmit={onCreate} className="card mb-6 grid gap-4 md:grid-cols-[1.5fr,1.5fr,1fr,auto] md:items-end">
        <div>
          <label className="label" htmlFor="new-email">
            Email
          </label>
          <input
            id="new-email"
            className="input"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="new-password">
            Temporary password (12+ chars, mixed case, digit, symbol)
          </label>
          <input
            id="new-password"
            className="input"
            type="password"
            required
            minLength={12}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="new-role">
            Role
          </label>
          <select
            id="new-role"
            className="input"
            value={role}
            onChange={(event) => setRole(event.target.value as Role)}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <button className="btn-primary" type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'Add user'}
        </button>
      </form>

      {!users ? (
        <Spinner />
      ) : (
        <div className="card mb-8 overflow-x-auto p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-edge text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-5 py-3">Email</th>
                <th className="px-5 py-3">Role</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b border-edge/50 last:border-0">
                  <td className="px-5 py-3">{user.email}</td>
                  <td className="px-5 py-3">
                    <select
                      className="input py-1"
                      value={user.role}
                      onChange={(event) => onUpdate(user.id, { role: event.target.value as Role })}
                    >
                      {ROLES.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-5 py-3">
                    <button
                      type="button"
                      className={user.is_active ? 'btn-ghost py-1' : 'btn-danger py-1'}
                      onClick={() => onUpdate(user.id, { is_active: !user.is_active })}
                    >
                      {user.is_active ? 'active' : 'disabled'}
                    </button>
                  </td>
                  <td className="px-5 py-3 text-slate-400">{new Date(user.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="mb-3 text-lg font-semibold">Audit trail</h2>
      {!logs ? (
        <Spinner />
      ) : (
        <div className="card max-h-[480px] overflow-auto p-0">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-panel uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-5 py-2">Time</th>
                <th className="px-5 py-2">Actor</th>
                <th className="px-5 py-2">Action</th>
                <th className="px-5 py-2">Resource</th>
                <th className="px-5 py-2">Result</th>
                <th className="px-5 py-2">IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((entry) => (
                <tr key={entry.id} className="border-b border-edge/40 last:border-0">
                  <td className="px-5 py-2 text-slate-400">{new Date(entry.created_at).toLocaleString()}</td>
                  <td className="px-5 py-2">{entry.actor_email ?? '—'}</td>
                  <td className="px-5 py-2 font-medium">{entry.action}</td>
                  <td className="px-5 py-2 font-mono text-slate-400">{entry.resource ?? '—'}</td>
                  <td className="px-5 py-2">
                    <span
                      className={`badge ${
                        entry.status === 'success'
                          ? 'bg-emerald-500/15 text-emerald-300'
                          : 'bg-rose-500/15 text-rose-300'
                      }`}
                    >
                      {entry.status}
                    </span>
                  </td>
                  <td className="px-5 py-2 text-slate-500">{entry.ip_address ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
