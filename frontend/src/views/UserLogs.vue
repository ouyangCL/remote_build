<template>
  <div class="audit-logs">
    <div class="header">
      <h2>操作记录</h2>
    </div>

    <!-- Filters -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filters">
        <el-form-item label="用户">
          <el-select
            v-model="filters.user_id"
            placeholder="全部用户"
            clearable
            style="width: 150px"
          >
            <el-option
              v-for="user in userList"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="操作类型">
          <el-select
            v-model="filters.action"
            placeholder="全部操作"
            clearable
            style="width: 150px"
          >
            <el-option
              v-for="action in actionOptions"
              :key="action.value"
              :label="action.label"
              :value="action.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="资源类型">
          <el-select
            v-model="filters.resource_type"
            placeholder="全部资源"
            clearable
            style="width: 150px"
          >
            <el-option label="用户" value="user" />
            <el-option label="项目" value="project" />
            <el-option label="服务器" value="server" />
            <el-option label="服务器组" value="server_group" />
            <el-option label="部署" value="deployment" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            @change="handleDateChange"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadLogs">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Logs Table -->
    <el-table :data="logs" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column label="用户" width="120">
        <template #default="{ row }">
          {{ row.user?.username || `用户${row.user_id}` }}
        </template>
      </el-table-column>
      <el-table-column prop="action" label="操作" width="150">
        <template #default="{ row }">
          <el-tag :type="getActionType(row.action)" size="small">
            {{ getActionLabel(row.action) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="resource_type" label="资源类型" width="100">
        <template #default="{ row }">
          {{ row.resource_type ? getResourceTypeLabel(row.resource_type) : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="details" label="详情" min-width="200">
        <template #default="{ row }">
          <span v-if="row.details">
            {{ formatDetails(row.details) }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="ip_address" label="IP地址" width="140" />
      <el-table-column prop="created_at" label="时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at, 'datetime') }}
        </template>
      </el-table-column>
    </el-table>

    <!-- Pagination -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="filters.page"
        v-model:page-size="filters.page_size"
        :page-sizes="[20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadLogs"
        @current-change="loadLogs"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { users } from '@/api'
import { formatDate } from '@/utils/date'
import type { AuditLog, AuditLogFilters, User } from '@/types'

const loading = ref(false)
const logs = ref<AuditLog[]>([])
const userList = ref<User[]>([])
const dateRange = ref<[string, string] | null>(null)
const total = ref(0)

const filters = ref<AuditLogFilters>({
  page: 1,
  page_size: 20,
})

const actionOptions = [
  { label: '登录', value: 'login' },
  { label: '登出', value: 'logout' },
  { label: '创建用户', value: 'user_create' },
  { label: '更新用户', value: 'user_update' },
  { label: '删除用户', value: 'user_delete' },
  { label: '切换用户状态', value: 'user_toggle' },
  { label: '创建项目', value: 'project_create' },
  { label: '更新项目', value: 'project_update' },
  { label: '删除项目', value: 'project_delete' },
  { label: '创建服务器', value: 'server_create' },
  { label: '更新服务器', value: 'server_update' },
  { label: '删除服务器', value: 'server_delete' },
  { label: '创建部署', value: 'deployment_create' },
  { label: '取消部署', value: 'deployment_cancel' },
  { label: '回滚部署', value: 'deployment_rollback' },
]

function getActionType(action: string) {
  if (action.includes('delete') || action.includes('cancel')) return 'danger'
  if (action.includes('create')) return 'success'
  if (action.includes('update') || action.includes('toggle')) return 'warning'
  return ''
}

function getActionLabel(action: string) {
  const option = actionOptions.find((opt) => opt.value === action)
  return option?.label || action
}

function getResourceTypeLabel(type: string) {
  const map: Record<string, string> = {
    user: '用户',
    project: '项目',
    server: '服务器',
    server_group: '服务器组',
    deployment: '部署',
  }
  return map[type] || type
}

function formatDetails(details: Record<string, unknown>): string {
  if (typeof details === 'string') {
    try {
      details = JSON.parse(details)
    } catch {
      return details
    }
  }

  const parts: string[] = []
  if (details.project_name) parts.push(`项目: ${details.project_name}`)
  if (details.server_name) parts.push(`服务器: ${details.server_name}`)
  if (details.group_name) parts.push(`组: ${details.group_name}`)
  if (details.target_username) parts.push(`目标: ${details.target_username}`)
  if (details.branch) parts.push(`分支: ${details.branch}`)
  if (details.new_status !== undefined) parts.push(`状态: ${details.new_status ? '启用' : '禁用'}`)
  if (details.role) parts.push(`角色: ${details.role}`)

  return parts.length > 0 ? parts.join(' | ') : JSON.stringify(details)
}

function handleDateChange(value: [string, string] | null) {
  if (value) {
    filters.value.start_date = value[0]
    filters.value.end_date = value[1]
  } else {
    delete filters.value.start_date
    delete filters.value.end_date
  }
}

function resetFilters() {
  filters.value = {
    page: 1,
    page_size: filters.value.page_size,
  }
  dateRange.value = null
  loadLogs()
}

async function loadLogs() {
  loading.value = true
  try {
    const result = await users.getAuditLogs(filters.value)
    logs.value = result.items
    total.value = result.total
  } catch (error) {
    console.error('Load audit logs failed:', error)
  } finally {
    loading.value = false
  }
}

async function loadUserList() {
  try {
    userList.value = await users.listUsers()
  } catch (error) {
    console.error('Load users failed:', error)
  }
}

onMounted(() => {
  loadLogs()
  loadUserList()
})
</script>

<style scoped>
.audit-logs {
  padding: 20px;
}

.header {
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

.filter-card {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .audit-logs {
    padding: 10px;
  }

  .header h2 {
    font-size: 18px;
  }

  /* 筛选表单适配 */
  .filter-card :deep(.el-form) {
    flex-direction: column;
  }

  .filter-card :deep(.el-form-item) {
    width: 100%;
    margin-right: 0;
  }

  .filter-card :deep(.el-select),
  .filter-card :deep(.el-date-picker) {
    width: 100% !important;
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

  /* 分页适配 */
  .pagination {
    justify-content: center;
  }

  .pagination :deep(.el-pagination) {
    flex-wrap: wrap;
    justify-content: center;
  }
}

/* 小屏移动端适配 */
@media (max-width: 480px) {
  .audit-logs {
    padding: 5px;
  }

  .header h2 {
    font-size: 16px;
  }

  .el-table :deep(.el-table__cell) {
    font-size: 12px;
  }

  /* 隐藏IP地址列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(6)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(6)) {
    display: none;
  }

  /* 隐藏资源类型列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(4)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(4)) {
    display: none;
  }

  /* 分页适配 */
  .pagination :deep(.el-pagination__sizes),
  .pagination :deep(.el-pagination__jump) {
    display: none;
  }
}

/* 超小屏适配 */
@media (max-width: 360px) {
  /* 隐藏时间列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(6)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(6)) {
    display: none;
  }

  /* 进一步简化分页 */
  .pagination :deep(.el-pagination) {
    font-size: 12px;
  }

  .pagination :deep(.el-pager li) {
    min-width: 28px;
    height: 28px;
    line-height: 28px;
  }
}
</style>
