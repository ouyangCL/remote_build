<template>
  <div class="deployment-console">
    <el-row :gutter="20">
      <el-col :span="10">
        <el-card>
          <template #header>
            <span>新建部署</span>
          </template>

          <el-form :model="form" label-width="100px">
            <el-form-item label="项目">
              <el-select
                v-model="form.project_id"
                placeholder="请选择项目"
                @change="handleProjectChange"
                style="width: 100%"
              >
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                >
                  <div class="project-option">
                    <span>{{ project.name }}</span>
                    <el-tag
                      size="small"
                      :type="getEnvironmentColor(project.environment)"
                      :icon="getEnvironmentIcon(project.environment)"
                      style="margin-left: 8px"
                    >
                      {{ getEnvironmentLabel(project.environment) }}
                    </el-tag>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>

            <el-form-item label="分支">
              <el-input
                v-model="form.branch"
                placeholder="请输入分支名称（如：main、develop）"
                style="width: 100%"
                clearable
                :disabled="form.deployment_type === 'restart_only'"
              />
              <div v-if="form.deployment_type === 'restart_only'" class="form-tip">
                <el-icon color="#e6a23c"><Warning /></el-icon>
                <span>仅重启模式下分支信息仅用于记录，不进行代码克隆</span>
              </div>
            </el-form-item>

            <el-form-item label="部署模式">
              <el-radio-group v-model="form.deployment_type">
                <el-radio label="full">
                  <div class="radio-option">
                    <span class="radio-label">完整部署</span>
                    <span class="radio-desc">克隆代码 → 构建 → 上传 → 重启</span>
                  </div>
                </el-radio>
                <el-radio label="restart_only">
                  <div class="radio-option">
                    <span class="radio-label">仅重启</span>
                    <span class="radio-desc">跳过构建，直接执行重启脚本</span>
                  </div>
                </el-radio>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="服务器组">
              <el-select
                v-model="form.server_group_ids"
                placeholder="请选择服务器组"
                multiple
                style="width: 100%"
              >
                <el-option
                  v-for="group in filteredServerGroups"
                  :key="group.id"
                  :label="group.name"
                  :value="group.id"
                  :disabled="isEnvironmentMismatch(group)"
                >
                  <div class="server-group-option">
                    <span>{{ group.name }}</span>
                    <el-tag
                      size="small"
                      :type="getEnvironmentColor(group.environment)"
                      :icon="getEnvironmentIcon(group.environment)"
                      style="margin-left: 8px"
                    >
                      {{ getEnvironmentLabel(group.environment) }}
                    </el-tag>
                  </div>
                </el-option>
              </el-select>
              <div v-if="selectedProject" class="form-tip">
                <el-icon color="#409eff"><InfoFilled /></el-icon>
                <span>
                  仅显示与项目环境（{{ getEnvironmentLabel(selectedProject.environment) }}）匹配的服务器组
                </span>
              </div>
              <el-alert
                v-if="hasEnvironmentMismatch"
                title="环境不匹配警告"
                type="warning"
                :closable="false"
                show-icon
                style="margin-top: 8px"
              >
                您选择了环境不匹配的服务器组，部署将被拒绝
              </el-alert>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                @click="handleDeploy"
                :loading="deploying"
                :disabled="!canDeploy || hasEnvironmentMismatch"
              >
                开始部署
              </el-button>
              <el-alert
                v-if="selectedProject?.environment === 'production'"
                title="生产环境部署"
                type="error"
                :closable="false"
                show-icon
                style="margin-top: 12px"
              >
                即将部署到生产环境，请确认操作无误
              </el-alert>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="logs-header">
              <span>部署日志</span>
              <div class="logs-actions">
                <!-- 进度显示 -->
                <div v-if="currentDeployment" class="deployment-progress">
                  <span class="progress-label">进度: {{ currentDeployment.progress }}%</span>
                  <el-progress
                    :percentage="currentDeployment.progress"
                    :status="getProgressStatus(currentDeployment.status)"
                    :stroke-width="8"
                    style="width: 120px; margin: 0 12px"
                  />
                  <el-tag
                    v-if="currentDeployment.current_step"
                    size="small"
                    :type="getStepColor(currentDeployment.current_step)"
                    style="margin-right: 12px"
                  >
                    {{ getStepLabel(currentDeployment.current_step) }}
                  </el-tag>
                </div>

                <!-- 日志过滤 -->
                <el-radio-group v-model="logFilter" size="small" style="margin-right: 12px">
                  <el-radio-button value="all">全部</el-radio-button>
                  <el-radio-button value="info">信息</el-radio-button>
                  <el-radio-button value="warning">警告</el-radio-button>
                  <el-radio-button value="error">错误</el-radio-button>
                </el-radio-group>

                <!-- 日志搜索 -->
                <el-input
                  v-model="searchKeyword"
                  placeholder="搜索日志"
                  size="small"
                  style="width: 150px; margin-right: 12px"
                  clearable
                >
                  <template #prefix>
                    <el-icon><Search /></el-icon>
                  </template>
                </el-input>

                <!-- 折叠开关 -->
                <el-switch
                  v-model="collapseDuplicates"
                  size="small"
                  active-text="折叠重复"
                  style="margin-right: 12px"
                />

                <!-- 下载日志 -->
                <el-button
                  size="small"
                  :icon="Download"
                  :disabled="logs.length === 0"
                  @click="downloadLogs"
                >
                  下载日志
                </el-button>
              </div>
            </div>
          </template>

          <div class="logs-container" ref="logsContainer">
            <div
              v-for="(log, index) in displayLogs"
              :key="index"
              :class="['log-entry', `log-${log.level.toLowerCase()}`]"
            >
              <span class="log-icon">{{ getStepIcon(log.content) }}</span>
              <span
                class="log-time"
                :title="formatFullTime(log.timestamp)"
              >
                {{ formatRelativeTime(log.timestamp) }}
              </span>
              <span
                class="log-content"
                v-html="highlightSearch(log.content)"
              />
              <span
                v-if="log.repeatCount > 1"
                class="log-repeat"
              >
                (重复了{{ log.repeatCount }}次)
              </span>
            </div>

            <el-empty v-if="logs.length === 0 && !deploying" description="暂无日志" />
            <el-empty v-else-if="displayLogs.length === 0" description="没有匹配的日志" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled, Search, Download, Warning } from '@element-plus/icons-vue'
import { projects as projectsApi, servers as serversApi, deployments as deploymentsApi } from '@/api'
import { ENVIRONMENT_DISPLAY } from '@/types'
import type { Project, ServerGroup, DeploymentLog, Environment, Deployment } from '@/types'

interface LogEntry extends DeploymentLog {
  repeatCount?: number
}

const projects = ref<Project[]>([])
const serverGroups = ref<ServerGroup[]>([])
const deploying = ref(false)
const logs = ref<LogEntry[]>([])
const logsContainer = ref<HTMLElement>()
const currentDeployment = ref<Deployment | null>(null)
let pollingTimer: ReturnType<typeof setInterval> | null = null
let usePolling = false
let maxLogId = 0  // 跟踪最大日志ID，用于增量查询
let currentPollingInterval = 2000  // 当前轮询间隔（毫秒）

// 日志过滤
const logFilter = ref<'all' | 'info' | 'warning' | 'error'>('all')

// 日志搜索
const searchKeyword = ref('')

// 折叠重复行
const collapseDuplicates = ref(false)

const form = reactive({
  project_id: null as number | null,
  branch: '',
  server_group_ids: [] as number[],
  deployment_type: 'full' as 'full' | 'restart_only',
})

const canDeploy = computed(
  () => form.project_id && form.server_group_ids.length > 0 &&
       (form.deployment_type === 'full' ? form.branch : true)
)

const selectedProject = computed(() =>
  projects.value.find(p => p.id === form.project_id) || null
)

const filteredServerGroups = computed(() => {
  if (!selectedProject.value) {
    return serverGroups.value
  }
  // 只显示与环境匹配的服务器组
  return serverGroups.value.filter(
    sg => sg.environment === selectedProject.value?.environment
  )
})

const hasEnvironmentMismatch = computed(() => {
  if (!selectedProject.value || form.server_group_ids.length === 0) {
    return false
  }
  // 检查是否有选择的环境不匹配的服务器组
  return form.server_group_ids.some(groupId => {
    const group = serverGroups.value.find(sg => sg.id === groupId)
    return group && group.environment !== selectedProject.value?.environment
  })
})

// 过滤后的日志
const filteredLogs = computed(() => {
  if (logFilter.value === 'all') {
    return logs.value
  }
  return logs.value.filter(log => log.level.toLowerCase() === logFilter.value)
})

// 搜索和过滤后的日志
const displayLogs = computed(() => {
  let result = filteredLogs.value

  // 搜索过滤
  if (searchKeyword.value.trim()) {
    const keyword = searchKeyword.value.toLowerCase().trim()
    result = result.filter(log =>
      log.content.toLowerCase().includes(keyword)
    )
  }

  // 折叠重复行
  if (collapseDuplicates.value) {
    result = collapseLogs(result)
  }

  return result
})

// 折叠重复日志
function collapseLogs(logs: LogEntry[]): LogEntry[] {
  const collapsed: LogEntry[] = []

  for (const log of logs) {
    const lastLog = collapsed[collapsed.length - 1]

    if (lastLog && lastLog.content === log.content) {
      lastLog.repeatCount = (lastLog.repeatCount || 1) + 1
    } else {
      collapsed.push({ ...log, repeatCount: 1 })
    }
  }

  // 移除 repeatCount 为 1 的标记
  return collapsed.map(log => {
    if (log.repeatCount === 1) {
      const { repeatCount, ...rest } = log
      return rest
    }
    return log
  })
}

// 根据日志内容获取步骤图标
function getStepIcon(content: string): string {
  const lowerContent = content.toLowerCase()

  if (lowerContent.includes('ssh') || lowerContent.includes('连接')) return '📡'
  if (lowerContent.includes('git') || lowerContent.includes('拉取') || lowerContent.includes('克隆')) return '📥'
  if (lowerContent.includes('构建') || lowerContent.includes('build') || lowerContent.includes('compile')) return '🔨'
  if (lowerContent.includes('打包') || lowerContent.includes('package') || lowerContent.includes('zip')) return '📦'
  if (lowerContent.includes('上传') || lowerContent.includes('upload') || lowerContent.includes('scp')) return '📤'
  if (lowerContent.includes('解压') || lowerContent.includes('extract') || lowerContent.includes('unzip')) return '📂'
  if (lowerContent.includes('部署') || lowerContent.includes('deploy') || lowerContent.includes('脚本')) return '🚀'
  if (lowerContent.includes('健康检查') || lowerContent.includes('health')) return '❤️'
  if (lowerContent.includes('成功') || lowerContent.includes('success') || lowerContent.includes('完成')) return '✅'
  if (lowerContent.includes('失败') || lowerContent.includes('error') || lowerContent.includes('错误')) return '❌'
  if (lowerContent.includes('警告') || lowerContent.includes('warning') || lowerContent.includes('warn')) return '⚠️'

  return '•'
}

// 高亮搜索关键词
function highlightSearch(content: string): string {
  if (!searchKeyword.value.trim()) {
    return escapeHtml(content)
  }

  const keyword = searchKeyword.value.trim()
  const escapedContent = escapeHtml(content)
  const regex = new RegExp(`(${escapeRegex(keyword)})`, 'gi')

  return escapedContent.replace(regex, '<mark class="search-highlight">$1</mark>')
}

// HTML 转义
function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// 正则转义
function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 格式化相对时间
function formatRelativeTime(timestamp: string): string {
  const now = Date.now()
  const time = new Date(timestamp).getTime()
  const diff = now - time

  if (diff < 1000) return '刚刚'
  if (diff < 60000) return `${Math.floor(diff / 1000)}秒前`
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return `${Math.floor(diff / 86400000)}天前`
}

// 格式化完整时间
function formatFullTime(timestamp: string): string {
  return new Date(timestamp).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

// 下载日志
function downloadLogs() {
  if (logs.value.length === 0) {
    ElMessage.warning('暂无日志可下载')
    return
  }

  const content = logs.value.map(log => {
    const time = formatFullTime(log.timestamp)
    const level = log.level.toUpperCase().padEnd(7)
    return `[${time}] [${level}] ${log.content}`
  }).join('\n')

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `deployment-logs-${new Date().getTime()}.txt`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  ElMessage.success('日志下载成功')
}

function getEnvironmentLabel(env: Environment) {
  return ENVIRONMENT_DISPLAY[env].label
}

function getEnvironmentColor(env: Environment) {
  return ENVIRONMENT_DISPLAY[env].color
}

function getEnvironmentIcon(env: Environment) {
  return ENVIRONMENT_DISPLAY[env].icon
}

function isEnvironmentMismatch(group: ServerGroup): boolean {
  if (!selectedProject.value) return false
  return group.environment !== selectedProject.value.environment
}

let eventSource: EventSource | null = null
let sseReconnectAttempts = 0  // SSE重连尝试次数
const MAX_SSE_RECONNECT_ATTEMPTS = 3  // 最大重连次数
let sseReconnectTimer: ReturnType<typeof setTimeout> | null = null  // 重连定时器
let currentDeploymentId: number | null = null  // 当前部署ID，用于重连

// 增强的SSE连接函数，支持自动重连
function connectSSEWithRetry(deploymentId: number): boolean {
  // 清理现有连接
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }

  currentDeploymentId = deploymentId

  try {
    eventSource = deploymentsApi.streamLogs(deploymentId)

    eventSource.onmessage = (e) => {
      if (e.data === ': keepalive') return

      const [level, timestamp, ...contentParts] = e.data.split(' ')
      const content = contentParts.join(' ')

      logs.value.push({ level, timestamp, content, id: Date.now() })

      // 检测错误日志并显示通知
      if (level === 'ERROR') {
        ElMessage.error({
          message: `部署错误: ${content}`,
          duration: 5000,
          showClose: true,
        })
      }

      nextTick(() => {
        if (logsContainer.value) {
          logsContainer.value.scrollTop = logsContainer.value.scrollHeight
        }
      })

      // 成功接收消息，重置重连计数
      sseReconnectAttempts = 0
    }

    eventSource.onerror = async () => {
      console.warn(`SSE连接错误 (尝试 ${sseReconnectAttempts + 1}/${MAX_SSE_RECONNECT_ATTEMPTS})`)

      // 关闭错误的连接
      if (eventSource) {
        eventSource.close()
        eventSource = null
      }

      // 尝试重连
      if (sseReconnectAttempts < MAX_SSE_RECONNECT_ATTEMPTS) {
        sseReconnectAttempts++

        // 指数退避策略：1s, 2s, 4s
        const retryDelay = Math.pow(2, sseReconnectAttempts - 1) * 1000

        console.log(`将在 ${retryDelay}ms 后尝试重连...`)

        sseReconnectTimer = setTimeout(() => {
          if (currentDeploymentId && !usePolling) {
            const reconnected = connectSSEWithRetry(currentDeploymentId)
            if (!reconnected) {
              // 重连失败，降级到轮询
              fallbackToPolling(currentDeploymentId)
            }
          }
        }, retryDelay)
      } else {
        // 达到最大重连次数，降级到轮询模式
        console.error('SSE重连失败，降级到轮询模式')
        fallbackToPolling(deploymentId)
      }
    }

    return true
  } catch (error) {
    console.error('SSE连接创建失败:', error)
    return false
  }
}

// 降级到轮询模式
async function fallbackToPolling(deploymentId: number) {
  if (usePolling) return  // 已经在轮询模式

  usePolling = true
  sseReconnectAttempts = 0

  // 清理SSE重连定时器
  if (sseReconnectTimer) {
    clearTimeout(sseReconnectTimer)
    sseReconnectTimer = null
  }

  ElMessage.warning({
    message: 'SSE连接不可用，已切换到轮询模式',
    duration: 3000,
    showClose: true,
  })

  await startPolling(deploymentId)
}

// 清理SSE连接
function cleanupSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }

  if (sseReconnectTimer) {
    clearTimeout(sseReconnectTimer)
    sseReconnectTimer = null
  }

  sseReconnectAttempts = 0
  currentDeploymentId = null
}

async function loadData() {
  projects.value = await projectsApi.list()
  serverGroups.value = await serversApi.listGroups()
}

function handleProjectChange() {
  if (!form.project_id) return

  // 清空服务器组选择，因为环境可能不匹配
  form.server_group_ids = []
}

async function handleDeploy() {
  deploying.value = true
  logs.value = []
  searchKeyword.value = ''
  logFilter.value = 'all'
  currentDeployment.value = null
  usePolling = false  // 重置轮询标志
  sseReconnectAttempts = 0  // 重置SSE重连计数

  try {
    const deployment = await deploymentsApi.create({
      project_id: form.project_id!,
      branch: form.branch,
      server_group_ids: form.server_group_ids,
      deployment_type: form.deployment_type,
    })

    currentDeployment.value = deployment

    // 检查部署是否排队
    if (deployment.status === 'queued') {
      ElMessage.warning({
        message: '部署已加入队列，请等待前面的部署完成',
        duration: 5000,
        showClose: true,
      })
    } else {
      ElMessage.success('部署已启动')
    }

    // 使用增强的SSE连接（带自动重连）
    const sseConnected = connectSSEWithRetry(deployment.id)

    // 如果SSE连接失败，立即降级到轮询
    if (!sseConnected && !usePolling) {
      await fallbackToPolling(deployment.id)
    }

    // 启动状态轮询以更新进度
    startStatusPolling(deployment.id)

    // 监听部署完成
    monitorDeploymentCompletion(deployment.id)
  } catch (err: any) {
    ElMessage.error({
      message: err?.response?.data?.detail || '启动部署失败',
      duration: 5000,
      showClose: true,
    })
    deploying.value = false
    cleanupSSE()  // 清理SSE资源
  }
}

// 监听部署完成并显示结果通知
async function monitorDeploymentCompletion(deploymentId: number) {
  const checkInterval = setInterval(async () => {
    try {
      const deployment = await deploymentsApi.get(deploymentId)

      if (['success', 'failed', 'cancelled'].includes(deployment.status)) {
        clearInterval(checkInterval)

        // 清理SSE连接
        cleanupSSE()

        // 停止状态轮询，避免重复请求
        stopStatusPolling()

        if (deployment.status === 'success') {
          ElMessage.success({
            message: '部署成功完成！',
            duration: 3000,
            showClose: true,
          })
        } else if (deployment.status === 'failed') {
          ElMessage.error({
            message: `部署失败: ${deployment.error_message || '未知错误'}`,
            duration: 0, // 不自动关闭
            showClose: true,
          })
        } else if (deployment.status === 'cancelled') {
          ElMessage.warning({
            message: '部署已取消',
            duration: 3000,
            showClose: true,
          })
        }

        deploying.value = false
      }
    } catch (error) {
      console.error('检查部署状态失败:', error)
    }
  }, 2000)
}

// 进度相关方法
function getProgressStatus(status: string): '' | 'success' | 'exception' | 'warning' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'exception'
  if (status === 'cancelled') return 'warning'
  return ''
}

// 状态轮询以更新进度（使用增量查询 + 动态频率）
async function startStatusPolling(deploymentId: number) {
  if (pollingTimer) {
    clearInterval(pollingTimer)
  }

  // 首次加载：获取所有数据
  try {
    const initialDeployment = await deploymentsApi.get(deploymentId)
    if (initialDeployment) {
      currentDeployment.value = initialDeployment
      maxLogId = initialDeployment.max_log_id || 0

      // 加载初始日志
      if (initialDeployment.logs && initialDeployment.logs.length > 0) {
        logs.value = []
        initialDeployment.logs.forEach((log: DeploymentLog) => {
          logs.value.push({
            level: log.level,
            timestamp: log.timestamp,
            content: log.content,
            id: log.id,
          })
        })
      }
    }
  } catch (error) {
    console.error('初始加载失败:', error)
  }

  // 增量轮询：动态调整频率
  const poll = async () => {
    try {
      // 使用增量查询
      const deployment = await deploymentsApi.get(deploymentId, maxLogId)
      if (currentDeployment.value && deployment) {
        // 更新部署状态
        currentDeployment.value = deployment

        // 处理增量日志
        const hasNewLogs = deployment.logs && deployment.logs.length > 0
        if (hasNewLogs) {
          deployment.logs.forEach((log: DeploymentLog) => {
            logs.value.push({
              level: log.level,
              timestamp: log.timestamp,
              content: log.content,
              id: log.id,
            })
          })

          // 更新max_log_id
          if (deployment.max_log_id !== undefined) {
            maxLogId = deployment.max_log_id
          }
        }

        // 动态调整轮询频率
        adjustPollingInterval(deployment.status, hasNewLogs)

        // 如果部署完成，停止轮询
        if (['success', 'failed', 'cancelled'].includes(deployment.status)) {
          stopStatusPolling()
          deploying.value = false
          return
        }

        // 重新安排下一次轮询
        pollingTimer = setTimeout(poll, currentPollingInterval)
      }
    } catch (error) {
      console.error('状态轮询失败:', error)
      // 出错时使用较长间隔重试
      currentPollingInterval = 5000
      pollingTimer = setTimeout(poll, currentPollingInterval)
    }
  }

  // 开始轮询
  pollingTimer = setTimeout(poll, currentPollingInterval)
}

// 根据部署状态和新日志情况动态调整轮询频率
function adjustPollingInterval(status: string, hasNewLogs: boolean) {
  // 如果有新日志，使用较短间隔快速获取
  if (hasNewLogs) {
    currentPollingInterval = 1000  // 1秒
    return
  }

  // 根据部署状态调整间隔
  switch (status) {
    case 'building':
    case 'uploading':
    case 'deploying':
      // 活跃阶段：2秒
      currentPollingInterval = 2000
      break
    case 'cloning':
    case 'pending':
      // 等待阶段：3秒
      currentPollingInterval = 3000
      break
    case 'queued':
      // 排队中：5秒
      currentPollingInterval = 5000
      break
    default:
      // 默认：2秒
      currentPollingInterval = 2000
  }
}

function stopStatusPolling() {
  if (pollingTimer) {
    clearTimeout(pollingTimer)
    pollingTimer = null
  }
  // 重置轮询间隔
  currentPollingInterval = 2000
}

// 日志轮询（当 SSE 不可用时）
async function startPolling(deploymentId: number) {
  ElMessage.warning('SSE连接不可用，已切换到轮询模式')

  if (pollingTimer) {
    clearInterval(pollingTimer)
  }

  let lastLogCount = logs.value.length

  pollingTimer = setInterval(async () => {
    try {
      const deployment = await deploymentsApi.get(deploymentId)

      // 更新部署状态
      if (currentDeployment.value) {
        currentDeployment.value = deployment
      }

      // 获取新日志
      if (deployment.logs && deployment.logs.length > lastLogCount) {
        const newLogs = deployment.logs.slice(lastLogCount)
        newLogs.forEach((log: DeploymentLog) => {
          logs.value.push({
            level: log.level,
            timestamp: log.timestamp,
            content: log.content,
          })
        })

        lastLogCount = deployment.logs.length

        nextTick(() => {
          if (logsContainer.value) {
            logsContainer.value.scrollTop = logsContainer.value.scrollHeight
          }
        })
      }

      // 如果部署完成，停止轮询
      if (['success', 'failed', 'cancelled'].includes(deployment.status)) {
        stopStatusPolling()
        deploying.value = false
        usePolling = false
      }
    } catch (error) {
      console.error('轮询失败:', error)
    }
  }, 2000) // 每2秒轮询一次
}

function getStepLabel(step: string): string {
  const stepLabels: Record<string, string> = {
    pending: '等待中',
    cloning: '克隆代码',
    building: '构建项目',
    uploading: '上传文件',
    deploying: '部署中',
    health_checking: '健康检查',
  }
  return stepLabels[step] || step
}

function getStepColor(step: string): string {
  const stepColors: Record<string, string> = {
    pending: 'info',
    cloning: 'primary',
    building: 'warning',
    uploading: 'primary',
    deploying: 'success',
    health_checking: 'info',
  }
  return stepColors[step] || 'info'
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString()
}

loadData()

onUnmounted(() => {
  eventSource?.close()
  stopStatusPolling()
  usePolling = false
})
</script>

<style scoped>
.deployment-console {
  padding: 20px;
}

.project-option,
.server-group-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.form-tip {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 5px;
  font-size: 12px;
  color: #606266;
}

.radio-option {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.radio-label {
  font-weight: 500;
}

.radio-desc {
  font-size: 12px;
  color: #909399;
}

.logs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.logs-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.deployment-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 12px;
  border-right: 1px solid #dcdfe6;
  margin-right: 12px;
}

.progress-label {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
  white-space: nowrap;
}

.logs-container {
  height: 500px;
  overflow-y: auto;
  background-color: #1e1e1e;
  padding: 15px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.log-entry {
  padding: 4px 0;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.log-icon {
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}

.log-time {
  color: #808080;
  flex-shrink: 0;
  cursor: help;
  transition: color 0.2s;
}

.log-time:hover {
  color: #4ec9b0;
}

.log-content {
  flex: 1;
  min-width: 0;
}

.log-repeat {
  color: #dcdcaa;
  font-size: 11px;
  flex-shrink: 0;
  font-style: italic;
}

.log-info {
  color: #4ec9b0;
}

.log-warning {
  color: #dcdcaa;
}

.log-error {
  color: #f48771;
}

.search-highlight {
  background-color: #634caf;
  color: #ffffff;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: bold;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .deployment-console {
    padding: 10px;
  }

  :deep(.el-row) {
    flex-direction: column;
  }

  :deep(.el-col) {
    width: 100% !important;
    max-width: 100%;
    margin-bottom: 15px;
  }

  .logs-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .logs-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .logs-container {
    height: 300px;
    padding: 10px;
    font-size: 11px;
  }

  .log-entry {
    padding: 2px 0;
    font-size: 11px;
  }

  .log-time {
    font-size: 10px;
  }

  .log-icon {
    width: 16px;
    font-size: 12px;
  }
}

/* 小屏移动端适配 */
@media (max-width: 480px) {
  .deployment-console {
    padding: 5px;
  }

  :deep(.el-form-item__label) {
    width: 80px !important;
    font-size: 13px;
  }

  .logs-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .logs-actions > * {
    width: 100%;
  }

  :deep(.el-radio-group) {
    display: flex;
    justify-content: space-between;
  }

  :deep(.el-radio-button) {
    flex: 1;
  }

  :deep(.el-radio-button__inner) {
    padding: 5px 8px;
    font-size: 12px;
  }

  .logs-container {
    height: 250px;
    padding: 8px;
    font-size: 10px;
  }

  :deep(.el-card__body) {
    padding: 15px;
  }
}

/* 超小屏适配 */
@media (max-width: 360px) {
  :deep(.el-form-item__label) {
    width: 70px !important;
    font-size: 12px;
  }

  .logs-container {
    height: 200px;
    padding: 5px;
  }

  :deep(.el-radio-button__inner) {
    padding: 4px 6px;
    font-size: 11px;
  }
}
</style>
