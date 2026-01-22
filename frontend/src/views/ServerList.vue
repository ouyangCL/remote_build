<template>
  <div class="server-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>服务器列表</span>
          <el-button type="primary" @click="handleCreate" :icon="Plus">
            新建服务器
          </el-button>
        </div>
      </template>

      <el-table :data="servers" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="host" label="主机" />
        <el-table-column prop="port" label="端口" width="80" />
        <el-table-column prop="auth_type" label="认证类型" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '活跃' : '未激活' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleTest(row)" :icon="Connection">
              测试连接
            </el-button>
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
      :title="isEdit ? '编辑服务器' : '新建服务器'"
      width="600px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="服务器名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>

        <el-form-item label="主机地址" prop="host">
          <el-input v-model="form.host" placeholder="192.168.1.100" />
        </el-form-item>

        <el-form-item label="端口" prop="port">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>

        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>

        <el-form-item label="认证类型" prop="auth_type">
          <el-select v-model="form.auth_type" style="width: 100%">
            <el-option label="密码" value="password" />
            <el-option label="SSH密钥" value="ssh_key" />
          </el-select>
        </el-form-item>

        <el-form-item label="密码/密钥" prop="auth_value">
          <el-input
            v-model="form.auth_value"
            :type="showPassword ? 'text' : 'password'"
            placeholder="密码或SSH私钥内容"
          >
            <template #append>
              <el-button @click="showPassword = !showPassword" :icon="showPassword ? View : Hide" />
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="部署路径" prop="deploy_path">
          <el-input v-model="form.deploy_path" placeholder="/opt/app" />
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
import { Plus, Edit, Delete, Connection, View, Hide } from '@element-plus/icons-vue'
import { servers as serversApi } from '@/api'
import type { Server } from '@/types'

const servers = ref<Server[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const showPassword = ref(false)
const formRef = ref()
const currentServer = ref<Server | null>(null)

const form = reactive({
  name: '',
  host: '',
  port: 22,
  username: '',
  auth_type: 'password',
  auth_value: '',
  deploy_path: '/opt/app',
})

const rules = {
  name: [{ required: true, message: '必填', trigger: 'blur' }],
  host: [{ required: true, message: '必填', trigger: 'blur' }],
  username: [{ required: true, message: '必填', trigger: 'blur' }],
  auth_type: [{ required: true, message: '必填', trigger: 'change' }],
  auth_value: [{ required: true, message: '必填', trigger: 'blur' }],
}

async function loadData() {
  loading.value = true
  try {
    servers.value = await serversApi.listServers()
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  isEdit.value = false
  showPassword.value = false
  Object.assign(form, {
    name: '',
    host: '',
    port: 22,
    username: '',
    auth_type: 'password',
    auth_value: '',
    deploy_path: '/opt/app',
  })
  dialogVisible.value = true
}

function handleEdit(server: Server) {
  isEdit.value = true
  currentServer.value = server
  Object.assign(form, server)
  dialogVisible.value = true
}

async function handleSubmit() {
  try {
    await formRef.value.validate()
    submitting.value = true

    if (isEdit.value && currentServer.value) {
      await serversApi.updateServer(currentServer.value.id, form)
      ElMessage.success('服务器已更新')
    } else {
      await serversApi.createServer(form)
      ElMessage.success('服务器已创建')
    }

    dialogVisible.value = false
    loadData()
  } finally {
    submitting.value = false
  }
}

async function handleTest(server: Server) {
  const loading = ElMessage({
    message: '正在测试连接...',
    type: 'info',
    duration: 0,
  })

  try {
    const result = await serversApi.testConnection(server.id)
    loading.close()

    if (result.success) {
      ElMessage.success(result.message || '连接成功')
    } else {
      ElMessage.error(result.message || '连接失败')
    }
  } catch {
    loading.close()
    ElMessage.error('连接测试失败')
  }
}

async function handleDelete(server: Server) {
  try {
    await ElMessageBox.confirm(`确定删除服务器 "${server.name}"?`, '确认', {
      type: 'warning',
    })

    await serversApi.deleteServer(server.id)
    ElMessage.success('服务器已删除')
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
.server-list {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .server-list {
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
}

/* 小屏移动端适配 */
@media (max-width: 480px) {
  .server-list {
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

  /* 隐藏端口列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(4)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(4)) {
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

  :deep(.el-form-item__label) {
    width: 100px !important;
    font-size: 13px;
  }
}

/* 超小屏适配 */
@media (max-width: 360px) {
  /* 隐藏主机列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(3)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(3)) {
    display: none;
  }

  :deep(.el-form-item__label) {
    width: 80px !important;
    font-size: 12px;
  }
}
</style>
