import api from './index'
import type { Server, ServerGroup } from '@/types'

export default {
  // Servers
  listServers: (): Promise<Server[]> => api.get('/servers'),

  createServer: (data: Partial<Server>): Promise<Server> =>
    api.post('/servers', data),

  getServer: (id: number): Promise<Server> => api.get(`/servers/${id}`),

  updateServer: (id: number, data: Partial<Server>): Promise<Server> =>
    api.put(`/servers/${id}`, data),

  deleteServer: (id: number): Promise<void> => api.delete(`/servers/${id}`),

  testConnection: (id: number): Promise<{ success: boolean; message: string }> =>
    api.post(`/servers/${id}/test-connection`),

  // Server Groups
  listGroups: (): Promise<ServerGroup[]> => api.get('/server-groups'),

  createGroup: (data: Partial<ServerGroup> & { server_ids?: number[] }): Promise<ServerGroup> =>
    api.post('/server-groups', data),

  getGroup: (id: number): Promise<ServerGroup> => api.get(`/server-groups/${id}`),

  updateGroup: (id: number, data: Partial<ServerGroup> & { server_ids?: number[] }): Promise<ServerGroup> =>
    api.put(`/server-groups/${id}`, data),

  deleteGroup: (id: number): Promise<void> => api.delete(`/server-groups/${id}`),
}
