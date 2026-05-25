import client from './client'
import type { Batch, NormalizedRecord, DashboardStats, PaginatedResponse, User } from './types'

export const auth = {
  login: (username: string, password: string) =>
    client.post<{ token: string; user: User }>('/auth/login/', { username, password }),
  logout: () => client.post('/auth/logout/'),
  me: () => client.get<User>('/auth/me/'),
}

export const ingestion = {
  upload: (file: File, sourceType: string) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('source_type', sourceType)
    return client.post<Batch>('/ingestion/upload/', fd)
  },
  batches: (params?: { source_type?: string }) =>
    client.get<PaginatedResponse<Batch>>('/ingestion/batches/', { params }),
}

export const review = {
  records: (params: {
    batch?: number
    status?: string
    scope?: string
    source_type?: string
    has_flags?: boolean
    page?: number
    ordering?: string
  }) => client.get<PaginatedResponse<NormalizedRecord>>('/review/records/', { params }),

  updateRecord: (id: number, data: { status?: string; analyst_notes?: string }) =>
    client.patch<NormalizedRecord>(`/review/records/${id}/`, data),

  bulkAction: (ids: number[], action: 'approve' | 'reject', notes?: string) =>
    client.post<{ updated: number }>('/review/records/bulk-action/', { ids, action, notes }),

  dashboard: () => client.get<DashboardStats>('/review/dashboard/'),
}
