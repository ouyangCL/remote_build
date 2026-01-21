<template>
  <div class="deployment-history">
    <el-card>
      <template #header>
        <div class="header">
          <span>Deployment History</span>
          <el-button @click="loadData" :icon="Refresh">Refresh</el-button>
        </div>
      </template>

      <el-table :data="deployments" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="project.name" label="Project" />
        <el-table-column prop="branch" label="Branch" />
        <el-table-column label="Status" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="Time" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              @click="handleView(row)"
              :icon="View"
            >
              View
            </el-button>
            <el-button
              size="small"
              type="warning"
              @click="handleRollback(row)"
              :icon="RefreshLeft"
              :disabled="row.status !== 'success'"
            >
              Rollback
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog
      v-model="detailVisible"
      title="Deployment Details"
      width="800px"
    >
      <div v-if="currentDeployment">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">
            {{ currentDeployment.id }}
          </el-descriptions-item>
          <el-descriptions-item label="Project">
            {{ currentDeployment.project?.name }}
          </el-descriptions-item>
          <el-descriptions-item label="Branch">
            {{ currentDeployment.branch }}
          </el-descriptions-item>
          <el-descriptions-item label="Status">
            <el-tag :type="getStatusType(currentDeployment.status)">
              {{ currentDeployment.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Commit" :span="2">
            {{ currentDeployment.commit_hash?.substring(0, 8) }} - {{ currentDeployment.commit_message }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider>Logs</el-divider>

        <div class="log-viewer">
          <div
            v-for="(log, index) in currentDeployment.logs"
            :key="index"
            class="log-entry"
          >
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span :class="['log-level', `log-${log.level.toLowerCase()}`]">
              [{{ log.level }}]
            </span>
            <span class="log-content">{{ log.content }}</span>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, View, RefreshLeft } from '@element-plus/icons-vue'
import api from '@/api'
import type { Deployment } from '@/types'

const deployments = ref<Deployment[]>([])
const loading = ref(false)
const detailVisible = ref(false)
const currentDeployment = ref<Deployment | null>(null)

async function loadData() {
  loading.value = true
  try {
    deployments.value = await api.deployments.list()
  } finally {
    loading.value = false
  }
}

async function handleView(deployment: Deployment) {
  currentDeployment.value = await api.deployments.get(deployment.id)
  detailVisible.value = true
}

async function handleRollback(deployment: Deployment) {
  try {
    await ElMessageBox.confirm(
      `Rollback to deployment ${deployment.id}?`,
      'Confirm Rollback',
      {
        type: 'warning',
      }
    )

    const groupIds = deployment.server_groups?.map(g => g.id) || []
    await api.deployments.rollback(deployment.id, groupIds)

    ElMessage.success('Rollback started')
    loadData()
  } catch (err) {
    // User cancelled
  }
}

function getStatusType(status: string) {
  const types: Record<string, any> = {
    success: 'success',
    failed: 'danger',
    cancelled: 'info',
    pending: 'warning',
    building: 'primary',
    deploying: 'primary',
  }
  return types[status] || ''
}

function formatTime(time: string) {
  return new Date(time).toLocaleString()
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.deployment-history {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-viewer {
  max-height: 400px;
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
}

.log-time {
  color: #808080;
  margin-right: 10px;
}

.log-level {
  margin-right: 10px;
}

.log-info {
  color: #4ec9b0;
}

.log-error {
  color: #f48771;
}
</style>
