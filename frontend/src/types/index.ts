export interface User {
  id: number
  username: string
  role: 'admin' | 'operator' | 'viewer'
  email?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Project {
  id: number
  name: string
  description?: string
  git_url: string
  project_type: 'frontend' | 'backend'
  build_script: string
  deploy_script_path: string
  output_dir: string
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
  auth_value: string
  deploy_path: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ServerGroup {
  id: number
  name: string
  description?: string
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
  project?: {
    id: number
    name: string
    project_type: string
  }
  server_groups?: {
    id: number
    name: string
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
