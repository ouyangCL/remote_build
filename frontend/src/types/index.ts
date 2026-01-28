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
  git_token?: string
  git_ssh_key?: string
  project_type: 'frontend' | 'java'
  build_script: string
  deploy_script_path: string
  upload_path: string
  restart_script_path: string
  restart_only_script_path?: string | null
  output_dir: string
  environment: Environment
  health_check_enabled: boolean
  health_check_type: 'http' | 'tcp' | 'command'
  health_check_url?: string | null
  health_check_port?: number | null
  health_check_command?: string | null
  health_check_timeout: number
  health_check_retries: number
  health_check_interval: number
  has_git_credentials?: boolean
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
  status: 'pending' | 'cloning' | 'building' | 'uploading' | 'deploying' | 'success' | 'failed' | 'cancelled' | 'rollback' | 'queued' | 'restarting' | 'health_checking'
  deployment_type?: 'full' | 'restart_only'
  progress: number
  current_step?: string
  total_steps: number
  commit_hash?: string
  commit_message?: string
  error_message?: string
  created_at: string
  created_by?: number
  rollback_from?: number
  environment: Environment
  max_log_id?: number  // 新增：最大日志ID，用于增量查询
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
