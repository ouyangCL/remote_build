import api from './index'
import type { Deployment } from '@/types'

export default {
  list: (projectId?: number): Promise<Deployment[]> =>
    api.get('/deployments', { params: { project_id: projectId } }),

  create: (data: {
    project_id: number
    branch: string
    server_group_ids: number[]
    deployment_type?: 'full' | 'restart_only'
  }): Promise<Deployment> => api.post('/deployments', data),

  get: (id: number): Promise<Deployment> => api.get(`/deployments/${id}`),

  cancel: (id: number): Promise<void> => api.delete(`/deployments/${id}`),

  rollback: (id: number, serverGroupIds: number[]): Promise<Deployment> =>
    api.post(`/deployments/${id}/rollback`, { server_group_ids: serverGroupIds }),

  // SSE log stream
  streamLogs: (id: number) => {
    const token = localStorage.getItem('access_token')
    const baseUrl = import.meta.env.VITE_API_URL || '/api'
    // 将 token 作为查询参数传递，因为 EventSource 不支持自定义 headers
    const url = `${baseUrl}/deployments/${id}/logs?token=${token}`

    return new EventSource(url)
  },
}
