export interface User {
  id: number
  username: string
  role: 'admin' | 'operator' | 'viewer'
  email?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface UserCreate {
  username: string
  password: string
  email?: string
  role: 'admin' | 'operator' | 'viewer'
  is_active: boolean
}

export interface UserUpdate {
  username?: string
  password?: string
  email?: string
  role?: 'admin' | 'operator' | 'viewer'
  is_active?: boolean
}

// Environment type
export type Environment = 'development' | 'production'

export interface EnvironmentDisplay {
  value: Environment
  label: string
  color: string
  icon: string
}

export const ENVIRONMENT_DISPLAY: Record<Environment, EnvironmentDisplay> = {
  development: {
    value: 'development',
    label: '开发/测试',
    color: 'success',
    icon: 'ri-code-s-slash-line'
  },
  production: {
    value: 'production',
    label: '生产',
    color: 'danger',
    icon: 'ri-server-line'
  }
}

export interface Project {
  id: number
  name: string
  description?: string
  git_url: string
  project_type: 'frontend' | 'backend' | 'java'
  build_script: string
  deploy_script_path: string
  output_dir: string
  environment: Environment
  created_at: string
  updated_at: string
}

export interface Server {
  id: number
  name: string
  host: string
  port: number
  username: string
  auth_type: 'password' | 'ssh_key'
  deploy_path: string
  is_active: boolean
  connection_status: 'untested' | 'online' | 'offline'
  created_at: string
  updated_at: string
}

export interface ServerGroup {
  id: number
  name: string
  description?: string
  environment: Environment
  created_at: string
  updated_at: string
  servers?: Server[]
}

export interface Deployment {
  id: number
  project_id: number
  branch: string
  status: 'pending' | 'cloning' | 'building' | 'uploading' | 'deploying' | 'success' | 'failed' | 'cancelled' | 'rollback'
  commit_hash?: string
  commit_message?: string
  error_message?: string
  created_at: string
  created_by?: number
  rollback_from?: number
  environment: Environment
  project?: {
    id: number
    name: string
    project_type: string
    environment?: Environment
  }
  server_groups?: {
    id: number
    name: string
    environment?: Environment
  }[]
  logs?: DeploymentLog[]
}

export interface DeploymentLog {
  id: number
  deployment_id: number
  level: string
  content: string
  timestamp: string
}

// Audit Log Types
export interface AuditLog {
  id: number
  user_id: number
  action: string
  resource_type?: string
  resource_id?: number
  details?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
  updated_at: string
  user?: {
    id: number
    username: string
    role: string
  }
}

export interface PaginatedAuditLogs {
  items: AuditLog[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AuditLogFilters {
  user_id?: number
  action?: string
  resource_type?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}
