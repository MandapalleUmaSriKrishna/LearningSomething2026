export type Role = 'admin' | 'analyst' | 'viewer'

export interface User {
  id: string
  email: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface ColumnProfile {
  name: string
  dtype: string
  kind: 'numeric' | 'categorical'
  missing: number
  missing_pct: number
  unique: number
  candidate_target: boolean
  min?: number | null
  max?: number | null
  mean?: number | null
  top_values?: { value: string; count: number }[]
}

export interface Dataset {
  id: string
  name: string
  original_filename: string
  size_bytes: number
  row_count: number
  column_count: number
  checksum_sha256: string
  created_at: string
  owner_id: string
  profile: { rows: number; columns: number; column_profiles: ColumnProfile[] }
}

export interface DatasetSummary {
  id: string
  name: string
  row_count: number
  column_count: number
  created_at: string
}

export interface Metrics {
  accuracy: number
  balanced_accuracy: number
  precision: number
  recall: number
  f1: number
  roc_auc?: number | null
  classes: string[]
  train_samples: number
  test_samples: number
  confusion_matrix: number[][]
  class_distribution: Record<string, number>
  roc_curve?: { fpr: number; tpr: number }[]
  pr_curve?: { recall: number; precision: number }[]
  feature_importances: { feature: string; importance: number }[]
  leaderboard: { algorithm: string; label: string; cv_score: number }[]
  cv: { folds: number; scoring: string; mean_score: number }
  baseline: { strategy: string; class: string; accuracy: number; f1_weighted: number }
}

export interface Run {
  id: string
  dataset_id: string
  target_column: string
  algorithm: string
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  config: Record<string, unknown>
  metrics: Metrics
  best_params: Record<string, unknown>
  cv_score: number | null
  duration_seconds: number | null
  error_message: string | null
  is_deployed: boolean
  created_at: string
}

export interface RunSummary {
  id: string
  dataset_id: string
  algorithm: string
  target_column: string
  status: Run['status']
  cv_score: number | null
  is_deployed: boolean
  created_at: string
}

export interface Stats {
  datasets: number
  runs: number
  deployed_models: number
  users: number
  best_cv_score: number | null
  recent_runs: RunSummary[]
}

export interface AuditEntry {
  id: string
  actor_email: string | null
  action: string
  resource: string | null
  status: string
  ip_address: string | null
  detail: Record<string, unknown>
  created_at: string
}

export interface Prediction {
  prediction: string
  confidence: number | null
  probabilities: Record<string, number>
}
