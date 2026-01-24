<template>
  <div class="project-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>项目管理</span>
          <el-button type="primary" @click="handleCreate" :icon="Plus">
            新建项目
          </el-button>
        </div>
      </template>

      <el-table :data="projects" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="项目名称" />
        <el-table-column prop="git_url" label="Git地址" show-overflow-tooltip />
        <el-table-column prop="project_type" label="类型" width="100" />
        <el-table-column label="环境" width="120">
          <template #default="{ row }">
            <el-tag :type="getEnvironmentColor(row.environment)" :icon="getEnvironmentIcon(row.environment)">
              {{ getEnvironmentLabel(row.environment) }}
            </el-tag>
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
      :title="isEdit ? '编辑项目' : '新建项目'"
      width="600px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>

        <el-form-item label="Git地址" prop="git_url">
          <el-input v-model="form.git_url" placeholder="https://github.com/user/repo.git" />
        </el-form-item>

        <el-form-item label="认证方式">
          <el-radio-group v-model="authMethod" @change="handleAuthMethodChange">
            <el-radio value="token">Git Token</el-radio>
            <el-radio value="ssh">SSH Key</el-radio>
            <el-radio value="none">无需认证</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="Git Token" v-if="authMethod === 'token'">
          <el-input
            v-model="form.git_token"
            type="password"
            placeholder="输入 Git Token"
            show-password
          />
          <div class="form-tip">
            <el-icon color="#909399"><InfoFilled /></el-icon>
            <span>用于访问 HTTP(S) 私有仓库</span>
          </div>
        </el-form-item>

        <el-form-item label="SSH Key" v-if="authMethod === 'ssh'">
          <el-input
            v-model="form.git_ssh_key"
            type="textarea"
            :rows="6"
            placeholder="-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----"
          />
          <div class="form-tip">
            <el-icon color="#909399"><InfoFilled /></el-icon>
            <span>用于访问 SSH 仓库（git@xxx.git）</span>
          </div>
        </el-form-item>

        <el-form-item v-if="authMethod === 'none'">
          <div class="form-tip">
            <el-icon color="#E6A23C"><Warning /></el-icon>
            <span class="warning-text">公开仓库无需认证，私有仓库请选择认证方式</span>
          </div>
        </el-form-item>

        <el-form-item label="项目类型" prop="project_type">
          <el-select v-model="form.project_type" style="width: 100%" @change="handleProjectTypeChange">
            <el-option label="前端 (Vue3/Vite)" value="frontend" />
            <el-option label="后端 (Node/Python)" value="backend" />
            <el-option label="Java (Maven)" value="java" />
          </el-select>
        </el-form-item>

        <el-form-item label="环境" prop="environment">
          <el-select v-model="form.environment" style="width: 100%">
            <el-option label="开发/测试" value="development" />
            <el-option label="生产" value="production" />
          </el-select>
          <div class="form-tip">
            <el-icon v-if="form.environment === 'production'" color="#f56c6c"><Warning /></el-icon>
            <span v-if="form.environment === 'production'" class="warning-text">
              生产环境项目将只能部署到生产环境服务器组
            </span>
          </div>
        </el-form-item>

        <el-form-item label="构建脚本" prop="build_script">
          <el-input
            v-model="form.build_script"
            type="textarea"
            placeholder="npm run build"
          />
        </el-form-item>

        <el-form-item label="输出目录" prop="output_dir">
          <el-input v-model="form.output_dir" placeholder="dist" />
        </el-form-item>

        <el-form-item label="重启脚本" prop="deploy_script_path">
          <el-input v-model="form.deploy_script_path" placeholder="/opt/restart.sh" />
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
import { Plus, Edit, Delete, Warning, InfoFilled } from '@element-plus/icons-vue'
import { projects as projectsApi } from '@/api'
import { ENVIRONMENT_DISPLAY } from '@/types'
import type { Project, Environment } from '@/types'

const projects = ref<Project[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref()
const currentProject = ref<Project | null>(null)

const authMethod = ref<'token' | 'ssh' | 'none'>('none')

const form = reactive({
  name: '',
  description: '',
  git_url: '',
  git_token: '',
  git_ssh_key: '',
  project_type: 'frontend',
  environment: 'development' as Environment,
  build_script: '',
  output_dir: 'dist',
  deploy_script_path: '/opt/restart.sh',
})

const rules = {
  name: [{ required: true, message: '必填', trigger: 'blur' }],
  git_url: [{ required: true, message: '必填', trigger: 'blur' }],
  project_type: [{ required: true, message: '必填', trigger: 'change' }],
  environment: [{ required: true, message: '必填', trigger: 'change' }],
  build_script: [{ required: true, message: '必填', trigger: 'blur' }],
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

// 项目类型预设模板
const PROJECT_TEMPLATES: Record<string, { build_script: string; output_dir: string; deploy_script_path: string }> = {
  frontend: {
    build_script: 'npm run build',
    output_dir: 'dist',
    deploy_script_path: '/opt/restart.sh',
  },
  backend: {
    build_script: 'npm run build',
    output_dir: 'dist',
    deploy_script_path: '/opt/restart.sh',
  },
  java: {
    build_script: 'mvn clean package',
    output_dir: 'target',
    deploy_script_path: '/opt/restart-java.sh',
  },
}

// 认证方式切换处理
function handleAuthMethodChange(method: 'token' | 'ssh' | 'none') {
  // 清空其他认证方式的字段
  if (method === 'token') {
    form.git_ssh_key = ''
  } else if (method === 'ssh') {
    form.git_token = ''
  } else {
    form.git_token = ''
    form.git_ssh_key = ''
  }
}

// 项目类型切换处理
function handleProjectTypeChange(projectType: string) {
  const template = PROJECT_TEMPLATES[projectType]
  if (template) {
    // 只有在新建且字段为空时才自动填充
    if (!isEdit.value) {
      if (!form.build_script) {
        form.build_script = template.build_script
      }
      if (form.output_dir === 'dist') {  // 只有默认值时才替换
        form.output_dir = template.output_dir
      }
      if (form.deploy_script_path === '/opt/restart.sh') {
        form.deploy_script_path = template.deploy_script_path
      }
    }
  }
}

async function loadData() {
  loading.value = true
  try {
    projects.value = await projectsApi.list()
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  isEdit.value = false
  authMethod.value = 'none'
  Object.assign(form, {
    name: '',
    description: '',
    git_url: '',
    git_token: '',
    git_ssh_key: '',
    project_type: 'frontend',
    environment: 'development' as Environment,
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

  // 自动检测认证方式
  if (form.git_ssh_key) {
    authMethod.value = 'ssh'
  } else if (form.git_token) {
    authMethod.value = 'token'
  } else {
    authMethod.value = 'none'
  }

  dialogVisible.value = true
}

async function handleSubmit() {
  try {
    await formRef.value.validate()
    submitting.value = true

    if (isEdit.value && currentProject.value) {
      await projectsApi.update(currentProject.value.id, form)
      ElMessage.success('项目已更新')
    } else {
      await projectsApi.create(form)
      ElMessage.success('项目已创建')
    }

    dialogVisible.value = false
    loadData()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(project: Project) {
  try {
    await ElMessageBox.confirm(`确定删除项目 "${project.name}"?`, '确认', {
      type: 'warning',
    })

    await projectsApi.delete(project.id)
    ElMessage.success('项目已删除')
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

/* 移动端适配 */
@media (max-width: 768px) {
  .project-list {
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

  /* 表格移动端适配 - 在小屏幕上隐藏部分列 */
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
  .project-list {
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
  /* 隐藏Git地址列 */
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
