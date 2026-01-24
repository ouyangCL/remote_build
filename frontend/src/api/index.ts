import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'
import auth from './auth'
import projects from './projects'
import servers from './servers'
import deployments from './deployments'
import users from './users'

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
      const { status, data, config } = error.response

      // 处理 401 未授权错误
      if (status === 401) {
        localStorage.removeItem('access_token')
        // 登录接口的错误由页面组件处理，不在这里显示提示
        if (!config?.url?.includes('/auth/login')) {
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }

      // 登录接口的错误由页面组件处理，不显示通用提示
      if (!config?.url?.includes('/auth/login')) {
        ElMessage.error(data.detail || '请求失败')
      }
    } else {
      ElMessage.error('网络错误，请检查网络连接')
    }

    return Promise.reject(error)
  }
)

export default api
export { auth, projects, servers, deployments, users }
