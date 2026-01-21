<template>
  <div class="server-group-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>Server Groups</span>
          <el-button type="primary" @click="handleCreate" :icon="Plus">
            New Server Group
          </el-button>
        </div>
      </template>

      <el-table :data="serverGroups" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="Name" />
        <el-table-column prop="description" label="Description" show-overflow-tooltip />
        <el-table-column label="Servers" width="200">
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
              No servers
            </span>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="150" fixed="right">
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
      :title="isEdit ? 'Edit Server Group' : 'New Server Group'"
      width="600px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="Group Name" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>

        <el-form-item label="Description">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>

        <el-form-item label="Servers" prop="server_ids">
          <el-select
            v-model="form.server_ids"
            multiple
            style="width: 100%"
            placeholder="Select servers"
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
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import api from '@/api'
import type { ServerGroup, Server } from '@/types'

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
  server_ids: [] as number[],
})

const rules = {
  name: [{ required: true, message: 'Required', trigger: 'blur' }],
}

async function loadData() {
  loading.value = true
  try {
    serverGroups.value = await api.servers.listGroups()
    allServers.value = await api.servers.listServers()
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  isEdit.value = false
  Object.assign(form, {
    name: '',
    description: '',
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
    server_ids: group.servers?.map(s => s.id) || [],
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  try {
    await formRef.value.validate()
    submitting.value = true

    if (isEdit.value && currentGroup.value) {
      await api.servers.updateGroup(currentGroup.value.id, form)
      ElMessage.success('Server group updated')
    } else {
      await api.servers.createGroup(form)
      ElMessage.success('Server group created')
    }

    dialogVisible.value = false
    loadData()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(group: ServerGroup) {
  try {
    await ElMessageBox.confirm(`Delete server group "${group.name}"?`, 'Confirm', {
      type: 'warning',
    })

    await api.servers.deleteGroup(group.id)
    ElMessage.success('Server group deleted')
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
</style>
