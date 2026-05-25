export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  tenant: { id: number; name: string; slug: string }
}

export interface Batch {
  id: number
  source_type: string
  source_type_display: string
  file_name: string
  status: 'processing' | 'completed' | 'failed'
  status_display: string
  row_count: number
  error_count: number
  ingested_by_name: string | null
  ingested_at: string
  notes: string
}

export interface ValidationFlag {
  id: number
  flag_type: string
  flag_type_display: string
  message: string
  severity: 'error' | 'warn' | 'info'
  resolved: boolean
  created_at: string
}

export interface NormalizedRecord {
  id: number
  batch: number
  source_type: string
  source_type_display: string
  scope: '1' | '2' | '3'
  scope_display: string
  activity_date: string | null
  description: string
  quantity: string | null
  unit: string
  co2e_kg: string | null
  emission_factor: string | null
  emission_factor_source: string
  status: 'pending' | 'flagged' | 'approved' | 'rejected'
  status_display: string
  is_locked: boolean
  analyst_notes: string
  edit_history: unknown[]
  flags: ValidationFlag[]
  reviewed_by_name: string | null
  reviewed_at: string | null
  created_at: string
  raw_data: Record<string, unknown> | null
}

export interface DashboardStats {
  total: number
  by_status: Record<string, number>
  by_scope: Record<string, { count: number; co2e_kg: number }>
  by_source: Array<{ source_type: string; label: string; count: number; co2e_kg: number }>
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
