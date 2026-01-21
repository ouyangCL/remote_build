<template>
  <div class="server-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>Servers</span>
          <el-button type="primary" @click="handleCreate" :icon="Plus">
            New Server
          </el-button>
        </div>
      </template>

      <el-table :data="servers" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="Name" />
        <el-table-column prop="host" label="Host" />
        <el-table-column prop="port" label="Port" width="80" />
        <el-table-column prop="auth_type" label="Auth Type" width="100" />
        <el-table-column label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? 'Active' : 'Inactive' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleTest(row)" :icon="Connection">
              Test
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
      :title="isEdit ? 'Edit Server' : 'New Server'"
      width="600px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="Server Name" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>

        <el-form-item label="Host" prop="host">
          <el-input v-model="form.host" placeholder="192.168.1.100" />
        </el-form-item>

        <el-form-item label="Port" prop="port">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>

        <el-form-item label="Username" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>

        <el-form-item label="Auth Type" prop="auth_type">
          <el-select v-model="form.auth_type" style="width: 100%">
            <el-option label="Password" value="password" />
            <el-option label="SSH Key" value="ssh_key" />
          </el-select>
        </el-form-item>

        <el-form-item label="Password / Key" prop="auth_value">
          <el-input
            v-model="form.auth_value"
            :type="showPassword ? 'text' : 'password'"
            placeholder="Password or SSH private key content"
          >
            <template #append>
              <el-button @click="showPassword = !showPassword" :icon="showPassword ? View : Hide" />
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="Deploy Path" prop="deploy_path">
          <el-input v-model="form.deploy_path" placeholder="/opt/app" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          {{ isEdit ? 'Update' : 'Create' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Connection, View, Hide } from '@element-plus/icons-vue'
import api from '@/api'
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
  name: [{ required: true, message: 'Required', trigger: 'blur' }],
  host: [{ required: true, message: 'Required', trigger: 'blur' }],
  username: [{ required: true, message: 'Required', trigger: 'blur' }],
  auth_type: [{ required: true, message: 'Required', trigger: 'change' }],
  auth_value: [{ required: true, message: 'Required', trigger: 'blur' }],
}

async function loadData() {
  loading.value = true
  try {
    servers.value = await api.servers.listServers()
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
      await api.servers.updateServer(currentServer.value.id, form)
      ElMessage.success('Server updated')
    } else {
      await api.servers.createServer(form)
      ElMessage.success('Server created')
    }

    dialogVisible.value = false
    loadData()
  } finally {
    submitting.value = false
  }
}

async function handleTest(server: Server) {
  const loading = ElMessage({
    message: 'Testing connection...',
    type: 'info',
    duration: 0,
  })

  try {
    const result = await api.servers.testConnection(server.id)
    loading.close()

    if (result.success) {
      ElMessage.success(result.message || 'Connection successful')
    } else {
      ElMessage.error(result.message || 'Connection failed')
    }
  } catch {
    loading.close()
    ElMessage.error('Connection test failed')
  }
}

async function handleDelete(server: Server) {
  try {
    await ElMessageBox.confirm(`Delete server "${server.name}"?`, 'Confirm', {
      type: 'warning',
    })

    await api.servers.deleteServer(server.id)
    ElMessage.success('Server deleted')
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
</style>
