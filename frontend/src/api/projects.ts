import api from './index'
import type { Project } from '@/types'

export default {
  list: (): Promise<Project[]> => api.get('/projects'),

  create: (data: Partial<Project>): Promise<Project> =>
    api.post('/projects', data),

  get: (id: number): Promise<Project> => api.get(`/projects/${id}`),

  update: (id: number, data: Partial<Project>): Promise<Project> =>
    api.put(`/projects/${id}`, data),

  delete: (id: number): Promise<void> => api.delete(`/projects/${id}`),

  getBranches: (id: number): Promise<{ branches: string[] }> =>
    api.get(`/projects/${id}/branches`),
}
