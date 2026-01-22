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
              <el-select
                v-model="form.branch"
                placeholder="请选择分支"
                :loading="loadingBranches"
                style="width: 100%"
              >
                <el-option
                  v-for="branch in branches"
                  :key="branch"
                  :label="branch"
                  :value="branch"
                />
              </el-select>
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
            <span>部署日志</span>
          </template>

          <div class="logs-container" ref="logsContainer">
            <div
              v-for="(log, index) in logs"
              :key="index"
              :class="['log-entry', `log-${log.level.toLowerCase()}`]"
            >
              <span class="log-time">{{ formatTime(log.timestamp) }}</span>
              <span class="log-content">{{ log.content }}</span>
            </div>

            <el-empty v-if="logs.length === 0 && !deploying" description="暂无日志" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { projects as projectsApi, servers as serversApi, deployments as deploymentsApi } from '@/api'
import { ENVIRONMENT_DISPLAY } from '@/types'
import type { Project, ServerGroup, DeploymentLog, Environment } from '@/types'

const projects = ref<Project[]>([])
const serverGroups = ref<ServerGroup[]>([])
const branches = ref<string[]>([])
const loadingBranches = ref(false)
const deploying = ref(false)
const logs = ref<string[]>([])
const logsContainer = ref<HTMLElement>()

const form = reactive({
  project_id: null as number | null,
  branch: '',
  server_group_ids: [] as number[],
})

const canDeploy = computed(
  () => form.project_id && form.branch && form.server_group_ids.length > 0
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

async function loadData() {
  projects.value = await projectsApi.list()
  serverGroups.value = await serversApi.listGroups()
}

async function handleProjectChange() {
  if (!form.project_id) return

  // 清空服务器组选择，因为环境可能不匹配
  form.server_group_ids = []

  loadingBranches.value = true
  try {
    const result = await projectsApi.getBranches(form.project_id)
    branches.value = result.branches
  } catch (err) {
    ElMessage.error('加载分支失败')
  } finally {
    loadingBranches.value = false
  }
}

async function handleDeploy() {
  deploying.value = true
  logs.value = []

  try {
    const deployment = await deploymentsApi.create({
      project_id: form.project_id!,
      branch: form.branch,
      server_group_ids: form.server_group_ids,
    })

    ElMessage.success('部署已启动')

    // Connect to SSE for real-time logs
    eventSource = deploymentsApi.streamLogs(deployment.id)

    eventSource.onmessage = (e) => {
      if (e.data === ': keepalive') return

      const [level, timestamp, ...contentParts] = e.data.split(' ')
      const content = contentParts.join(' ')

      logs.value.push({ level, timestamp, content })

      nextTick(() => {
        if (logsContainer.value) {
          logsContainer.value.scrollTop = logsContainer.value.scrollHeight
        }
      })
    }

    eventSource.onerror = () => {
      eventSource?.close()
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '启动部署失败')
    deploying.value = false
  }
}

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString()
}

loadData()

onUnmounted(() => {
  eventSource?.close()
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

.log-time {
  color: #808080;
  margin-right: 10px;
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

  .logs-container {
    height: 300px;
    padding: 10px;
    font-size: 11px;
  }

  .log-entry {
    padding: 2px 0;
  }

  .log-time {
    font-size: 10px;
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
}
</style>
