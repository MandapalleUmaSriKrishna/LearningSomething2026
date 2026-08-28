const BASE = '/api/v1'
const ACCESS_KEY = 'secureml.access'
const REFRESH_KEY = 'secureml.refresh'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export const tokens = {
  access: () => sessionStorage.getItem(ACCESS_KEY),
  refresh: () => sessionStorage.getItem(REFRESH_KEY),
  set(access: string, refresh: string) {
    sessionStorage.setItem(ACCESS_KEY, access)
    sessionStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    sessionStorage.removeItem(ACCESS_KEY)
    sessionStorage.removeItem(REFRESH_KEY)
  },
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') return body.detail
    if (Array.isArray(body?.errors) && body.errors[0]?.msg) return body.errors[0].msg
  } catch {
    /* fall through to the status text */
  }
  return response.statusText || 'Request failed'
}

async function refreshSession(): Promise<boolean> {
  const refresh = tokens.refresh()
  if (!refresh) return false
  const response = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  })
  if (!response.ok) {
    tokens.clear()
    return false
  }
  const body = await response.json()
  tokens.set(body.access_token, body.refresh_token)
  return true
}

interface RequestOptions {
  method?: string
  body?: unknown
  form?: FormData
  retry?: boolean
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, form, retry = true } = options
  const headers: Record<string, string> = {}
  const access = tokens.access()
  if (access) headers.Authorization = `Bearer ${access}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
  })

  if (response.status === 401 && retry && tokens.refresh()) {
    if (await refreshSession()) return request<T>(path, { ...options, retry: false })
  }
  if (!response.ok) throw new ApiError(await parseError(response), response.status)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string; expires_in: number }>('/auth/login', {
      method: 'POST',
      body: { email, password },
    }),
  logout: (refresh_token: string) =>
    request<void>('/auth/logout', { method: 'POST', body: { refresh_token } }),
  me: () => request<import('./types').User>('/auth/me'),
  changePassword: (current_password: string, new_password: string) =>
    request<void>('/auth/password', { method: 'POST', body: { current_password, new_password } }),
  createUser: (email: string, password: string, role: string) =>
    request<import('./types').User>('/auth/register', {
      method: 'POST',
      body: { email, password, role },
    }),
  users: () => request<import('./types').User[]>('/users'),
  updateUser: (id: string, patch: { role?: string; is_active?: boolean }) =>
    request<import('./types').User>(`/users/${id}`, { method: 'PATCH', body: patch }),
  auditLogs: (limit = 100) => request<import('./types').AuditEntry[]>(`/audit-logs?limit=${limit}`),
  stats: () => request<import('./types').Stats>('/stats'),
  datasets: () => request<import('./types').DatasetSummary[]>('/datasets'),
  dataset: (id: string) => request<import('./types').Dataset>(`/datasets/${id}`),
  datasetPreview: (id: string) =>
    request<{ columns: string[]; rows: Record<string, unknown>[] }>(`/datasets/${id}/preview`),
  uploadDataset: (file: File, name: string) => {
    const form = new FormData()
    form.append('file', file)
    if (name) form.append('name', name)
    return request<import('./types').Dataset>('/datasets', { method: 'POST', form })
  },
  deleteDataset: (id: string) => request<void>(`/datasets/${id}`, { method: 'DELETE' }),
  algorithms: () => request<{ value: string; label: string }[]>('/runs/algorithms'),
  runs: () => request<import('./types').RunSummary[]>('/runs'),
  run: (id: string) => request<import('./types').Run>(`/runs/${id}`),
  train: (payload: Record<string, unknown>) =>
    request<import('./types').Run>('/runs', { method: 'POST', body: payload }),
  deploy: (id: string) => request<import('./types').Run>(`/runs/${id}/deploy`, { method: 'POST' }),
  deleteRun: (id: string) => request<void>(`/runs/${id}`, { method: 'DELETE' }),
  predict: (id: string, records: Record<string, unknown>[]) =>
    request<{ run_id: string; algorithm: string; predictions: import('./types').Prediction[] }>(
      `/runs/${id}/predict`,
      { method: 'POST', body: { records } },
    ),
}
