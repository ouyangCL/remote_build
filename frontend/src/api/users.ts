import api from './index'
import type { User, UserCreate, UserUpdate, AuditLogFilters, PaginatedAuditLogs } from '@/types'

export default {
  // User Management
  listUsers: (): Promise<User[]> => api.get('/users'),

  createUser: (data: UserCreate): Promise<User> => api.post('/users', data),

  getUser: (id: number): Promise<User> => api.get(`/users/${id}`),

  updateUser: (id: number, data: UserUpdate): Promise<User> => api.put(`/users/${id}`, data),

  toggleUser: (id: number): Promise<User> => api.patch(`/users/${id}/toggle`),

  deleteUser: (id: number): Promise<void> => api.delete(`/users/${id}`),

  // Audit Logs
  getAuditLogs: (filters: AuditLogFilters = {}): Promise<PaginatedAuditLogs> => {
    const params = new URLSearchParams()
    if (filters.user_id) params.append('user_id', filters.user_id.toString())
    if (filters.action) params.append('action', filters.action)
    if (filters.resource_type) params.append('resource_type', filters.resource_type)
    if (filters.start_date) params.append('start_date', filters.start_date)
    if (filters.end_date) params.append('end_date', filters.end_date)
    params.append('page', (filters.page || 1).toString())
    params.append('page_size', (filters.page_size || 20).toString())

    return api.get(`/audit-logs?${params.toString()}`)
  },
}
