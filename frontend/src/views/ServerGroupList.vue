<template>
  <div class="server-group-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>服务器组</span>
          <el-button type="primary" @click="handleCreate" :icon="Plus">
            新建服务器组
          </el-button>
        </div>
      </template>

      <el-table :data="serverGroups" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column label="环境" width="120">
          <template #default="{ row }">
            <el-tag :type="getEnvironmentColor(row.environment)" :icon="getEnvironmentIcon(row.environment)">
              {{ getEnvironmentLabel(row.environment) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="服务器" width="200">
          <template #default="{ row }">
            <el-tag
              v-for="server in row.servers"
              :key="server.id"
              size="small"
              style="margin-right: 5px"
            >
              {{ server.name }}
            </el-tag>
            <span v-if="!row.servers || row.servers.length === 0" class="text-gray">
              暂无服务器
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)" :icon="Edit" />
            <el-button
              size="small"
              type="danger"
              @click="handleDelete(row)"
              :icon="Delete"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Form Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑服务器组' : '新建服务器组'"
      width="600px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="组名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>

        <el-form-item label="环境" prop="environment">
          <el-select v-model="form.environment" style="width: 100%">
            <el-option label="开发/测试" value="development" />
            <el-option label="生产" value="production" />
          </el-select>
          <div class="form-tip">
            <el-icon v-if="form.environment === 'production'" color="#f56c6c"><Warning /></el-icon>
            <span v-if="form.environment === 'production'" class="warning-text">
              生产环境服务器组只能部署生产环境项目
            </span>
          </div>
        </el-form-item>

        <el-form-item label="服务器" prop="server_ids">
          <el-select
            v-model="form.server_ids"
            multiple
            style="width: 100%"
            placeholder="请选择服务器"
          >
            <el-option
              v-for="server in allServers"
              :key="server.id"
              :label="server.name"
              :value="server.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          {{ isEdit ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Warning } from '@element-plus/icons-vue'
import { servers as serversApi } from '@/api'
import { ENVIRONMENT_DISPLAY } from '@/types'
import type { ServerGroup, Server, Environment } from '@/types'

const serverGroups = ref<ServerGroup[]>([])
const allServers = ref<Server[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref()
const currentGroup = ref<ServerGroup | null>(null)

const form = reactive({
  name: '',
  description: '',
  environment: 'development' as Environment,
  server_ids: [] as number[],
})

const rules = {
  name: [{ required: true, message: '必填', trigger: 'blur' }],
  environment: [{ required: true, message: '必填', trigger: 'change' }],
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

async function loadData() {
  loading.value = true
  try {
    serverGroups.value = await serversApi.listGroups()
    allServers.value = await serversApi.listServers()
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  isEdit.value = false
  Object.assign(form, {
    name: '',
    description: '',
    environment: 'development' as Environment,
    server_ids: [],
  })
  dialogVisible.value = true
}

function handleEdit(group: ServerGroup) {
  isEdit.value = true
  currentGroup.value = group
  Object.assign(form, {
    name: group.name,
    description: group.description || '',
    environment: group.environment,
    server_ids: group.servers?.map(s => s.id) || [],
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  try {
    await formRef.value.validate()
    submitting.value = true

    if (isEdit.value && currentGroup.value) {
      await serversApi.updateGroup(currentGroup.value.id, form)
      ElMessage.success('服务器组已更新')
    } else {
      await serversApi.createGroup(form)
      ElMessage.success('服务器组已创建')
    }

    dialogVisible.value = false
    loadData()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(group: ServerGroup) {
  try {
    await ElMessageBox.confirm(`确定删除服务器组 "${group.name}"?`, '确认', {
      type: 'warning',
    })

    await serversApi.deleteGroup(group.id)
    ElMessage.success('服务器组已删除')
    loadData()
  } catch {
    // User cancelled
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.server-group-list {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.text-gray {
  color: #909399;
  font-size: 12px;
}

.form-tip {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 5px;
  font-size: 12px;
}

.warning-text {
  color: #f56c6c;
}
</style>
