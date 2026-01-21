import api from './index'
import type { User } from '@/types'

export default {
  login: (credentials: { username: string; password: string }) =>
    api.post('/auth/login', credentials),

  getMe: (): Promise<User> => api.get('/auth/me'),

  initAdmin: (): Promise<User> => api.post('/auth/init'),
}
