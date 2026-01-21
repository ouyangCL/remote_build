import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

const baseURL = import.meta.env.VITE_API_URL || '/api'

const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      const { status, data } = error.response

      if (status === 401) {
        localStorage.removeItem('access_token')
        window.location.href = '/login'
      }

      ElMessage.error(data.detail || 'An error occurred')
    } else {
      ElMessage.error('Network error')
    }

    return Promise.reject(error)
  }
)

export default api
