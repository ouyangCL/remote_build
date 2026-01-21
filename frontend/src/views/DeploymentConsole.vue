<template>
  <div class="deployment-console">
    <el-row :gutter="20">
      <el-col :span="10">
        <el-card>
          <template #header>
            <span>New Deployment</span>
          </template>

          <el-form :model="form" label-width="100px">
            <el-form-item label="Project">
              <el-select
                v-model="form.project_id"
                placeholder="Select project"
                @change="handleProjectChange"
                style="width: 100%"
              >
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="Branch">
              <el-select
                v-model="form.branch"
                placeholder="Select branch"
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

            <el-form-item label="Server Groups">
              <el-select
                v-model="form.server_group_ids"
                placeholder="Select server groups"
                multiple
                style="width: 100%"
              >
                <el-option
                  v-for="group in serverGroups"
                  :key="group.id"
                  :label="group.name"
                  :value="group.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                @click="handleDeploy"
                :loading="deploying"
                :disabled="!canDeploy"
              >
                Start Deployment
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card>
          <template #header>
            <span>Deployment Logs</span>
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

            <el-empty v-if="logs.length === 0 && !deploying" description="No logs yet" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { Project, ServerGroup, DeploymentLog } from '@/types'

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

let eventSource: EventSource | null = null

async function loadData() {
  projects.value = await api.projects.list()
  serverGroups.value = await api.servers.listGroups()
}

async function handleProjectChange() {
  if (!form.project_id) return

  loadingBranches.value = true
  try {
    const result = await api.projects.getBranches(form.project_id)
    branches.value = result.branches
  } catch (err) {
    ElMessage.error('Failed to load branches')
  } finally {
    loadingBranches.value = false
  }
}

async function handleDeploy() {
  deploying.value = true
  logs.value = []

  try {
    const deployment = await api.deployments.create({
      project_id: form.project_id!,
      branch: form.branch,
      server_group_ids: form.server_group_ids,
    })

    ElMessage.success('Deployment started')

    // Connect to SSE for real-time logs
    eventSource = api.deployments.streamLogs(deployment.id)

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
  } catch (err) {
    ElMessage.error('Failed to start deployment')
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
</style>
