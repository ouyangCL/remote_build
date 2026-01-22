<template>
  <div class="deployment-history">
    <el-card>
      <template #header>
        <div class="header">
          <span>部署历史</span>
          <el-button @click="loadData" :icon="Refresh">刷新</el-button>
        </div>
      </template>

      <el-table :data="deployments" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="project.name" label="项目" />
        <el-table-column prop="branch" label="分支" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              @click="handleView(row)"
              :icon="View"
            >
              查看
            </el-button>
            <el-button
              size="small"
              type="warning"
              @click="handleRollback(row)"
              :icon="RefreshLeft"
              :disabled="row.status !== 'success'"
            >
              回滚
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog
      v-model="detailVisible"
      title="部署详情"
      width="800px"
    >
      <div v-if="currentDeployment">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">
            {{ currentDeployment.id }}
          </el-descriptions-item>
          <el-descriptions-item label="项目">
            {{ currentDeployment.project?.name }}
          </el-descriptions-item>
          <el-descriptions-item label="分支">
            {{ currentDeployment.branch }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentDeployment.status)">
              {{ getStatusLabel(currentDeployment.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="提交" :span="2">
            {{ currentDeployment.commit_hash?.substring(0, 8) }} - {{ currentDeployment.commit_message }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider>日志</el-divider>

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
import { deployments as deploymentsApi } from '@/api'
import type { Deployment } from '@/types'

const deployments = ref<Deployment[]>([])
const loading = ref(false)
const detailVisible = ref(false)
const currentDeployment = ref<Deployment | null>(null)

async function loadData() {
  loading.value = true
  try {
    deployments.value = await deploymentsApi.list()
  } finally {
    loading.value = false
  }
}

async function handleView(deployment: Deployment) {
  currentDeployment.value = await deploymentsApi.get(deployment.id)
  detailVisible.value = true
}

async function handleRollback(deployment: Deployment) {
  try {
    await ElMessageBox.confirm(
      `确定回滚到部署 ${deployment.id}?`,
      '确认回滚',
      {
        type: 'warning',
      }
    )

    const groupIds = deployment.server_groups?.map(g => g.id) || []
    await deploymentsApi.rollback(deployment.id, groupIds)

    ElMessage.success('回滚已启动')
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

function getStatusLabel(status: string) {
  const labels: Record<string, string> = {
    success: '成功',
    failed: '失败',
    cancelled: '已取消',
    pending: '等待中',
    building: '构建中',
    deploying: '部署中',
  }
  return labels[status] || status
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

/* 移动端适配 */
@media (max-width: 768px) {
  .deployment-history {
    padding: 10px;
  }

  .header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .header span {
    font-size: 16px;
  }

  /* 表格移动端适配 */
  .el-table :deep(.el-table__cell) {
    padding: 8px 5px;
  }

  /* 隐藏ID列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(1)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(1)) {
    display: none;
  }

  .log-viewer {
    max-height: 300px;
    padding: 10px;
    font-size: 11px;
  }
}

/* 小屏移动端适配 */
@media (max-width: 480px) {
  .deployment-history {
    padding: 5px;
  }

  .header {
    gap: 8px;
  }

  .header span {
    font-size: 14px;
  }

  .el-table :deep(.el-table__cell) {
    font-size: 12px;
  }

  /* 隐藏时间列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(5)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(5)) {
    display: none;
  }

  /* 对话框适配 */
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 0 auto;
  }

  :deep(.el-dialog__body) {
    padding: 15px;
  }

  .log-viewer {
    max-height: 250px;
    padding: 8px;
    font-size: 10px;
  }
}

/* 超小屏适配 */
@media (max-width: 360px) {
  /* 隐藏分支列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(3)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(3)) {
    display: none;
  }

  .log-viewer {
    max-height: 200px;
    padding: 5px;
  }
}
</style>
