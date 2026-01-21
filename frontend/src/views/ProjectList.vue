<template>
  <div class="project-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>Projects</span>
          <el-button type="primary" @click="handleCreate" :icon="Plus">
            New Project
          </el-button>
        </div>
      </template>

      <el-table :data="projects" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="Name" />
        <el-table-column prop="git_url" label="Git URL" show-overflow-tooltip />
        <el-table-column prop="project_type" label="Type" width="100" />
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
      :title="isEdit ? 'Edit Project' : 'New Project'"
      width="600px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="Project Name" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>

        <el-form-item label="Description">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>

        <el-form-item label="Git URL" prop="git_url">
          <el-input v-model="form.git_url" placeholder="https://github.com/user/repo.git" />
        </el-form-item>

        <el-form-item label="Project Type" prop="project_type">
          <el-select v-model="form.project_type" style="width: 100%">
            <el-option label="Frontend" value="frontend" />
            <el-option label="Backend" value="backend" />
          </el-select>
        </el-form-item>

        <el-form-item label="Build Script" prop="build_script">
          <el-input
            v-model="form.build_script"
            type="textarea"
            placeholder="npm run build"
          />
        </el-form-item>

        <el-form-item label="Output Directory" prop="output_dir">
          <el-input v-model="form.output_dir" placeholder="dist" />
        </el-form-item>

        <el-form-item label="Restart Script" prop="deploy_script_path">
          <el-input v-model="form.deploy_script_path" placeholder="/opt/restart.sh" />
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
import type { Project } from '@/types'

const projects = ref<Project[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref()
const currentProject = ref<Project | null>(null)

const form = reactive({
  name: '',
  description: '',
  git_url: '',
  project_type: 'frontend',
  build_script: '',
  output_dir: 'dist',
  deploy_script_path: '/opt/restart.sh',
})

const rules = {
  name: [{ required: true, message: 'Required', trigger: 'blur' }],
  git_url: [{ required: true, message: 'Required', trigger: 'blur' }],
  project_type: [{ required: true, message: 'Required', trigger: 'change' }],
  build_script: [{ required: true, message: 'Required', trigger: 'blur' }],
}

async function loadData() {
  loading.value = true
  try {
    projects.value = await api.projects.list()
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  isEdit.value = false
  Object.assign(form, {
    name: '',
    description: '',
    git_url: '',
    project_type: 'frontend',
    build_script: '',
    output_dir: 'dist',
    deploy_script_path: '/opt/restart.sh',
  })
  dialogVisible.value = true
}

function handleEdit(project: Project) {
  isEdit.value = true
  currentProject.value = project
  Object.assign(form, project)
  dialogVisible.value = true
}

async function handleSubmit() {
  try {
    await formRef.value.validate()
    submitting.value = true

    if (isEdit.value && currentProject.value) {
      await api.projects.update(currentProject.value.id, form)
      ElMessage.success('Project updated')
    } else {
      await api.projects.create(form)
      ElMessage.success('Project created')
    }

    dialogVisible.value = false
    loadData()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(project: Project) {
  try {
    await ElMessageBox.confirm(`Delete project "${project.name}"?`, 'Confirm', {
      type: 'warning',
    })

    await api.projects.delete(project.id)
    ElMessage.success('Project deleted')
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
.project-list {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
