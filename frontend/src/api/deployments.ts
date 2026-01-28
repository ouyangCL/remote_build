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
  }): Promise<Deployment> => api.post('/deployments', data, { timeout: 30000 }), // 30 seconds timeout - should return immediately

  get: (id: number, sinceId?: number): Promise<Deployment> =>
    api.get(`/deployments/${id}`, { params: sinceId !== undefined ? { since_id: sinceId } : {} }),

  cancel: (id: number): Promise<void> => api.delete(`/deployments/${id}`),

  rollback: (id: number, serverGroupIds: number[]): Promise<Deployment> =>
    api.post(`/deployments/${id}/rollback`, { server_group_ids: serverGroupIds }, { timeout: 120000 }), // 2 minutes timeout

  // 上传部署包创建部署
  createUploadDeployment: (
    projectId: number,
    serverGroupIds: number[],
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<Deployment> => {
    const formData = new FormData()
    formData.append('project_id', projectId.toString())
    formData.append('server_group_ids', serverGroupIds.join(','))
    formData.append('file', file)

    return api.post<Deployment>('/deployments/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      }
    })
  },

  // SSE log stream
  streamLogs: (id: number) => {
    const token = localStorage.getItem('access_token')
    const baseUrl = import.meta.env.VITE_API_URL || '/api'
    // 将 token 作为查询参数传递，因为 EventSource 不支持自定义 headers
    const url = `${baseUrl}/deployments/${id}/logs?token=${token}`

    return new EventSource(url)
  },
}
