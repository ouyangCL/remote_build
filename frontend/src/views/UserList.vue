<template>
  <div class="user-list">
    <div class="header">
      <h2>用户管理</h2>
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        新建用户
      </el-button>
    </div>

    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" width="150" />
      <el-table-column prop="email" label="邮箱" width="200" />
      <el-table-column prop="role" label="角色" width="120">
        <template #default="{ row }">
          <el-tag :type="getRoleType(row.role)">{{ getRoleLabel(row.role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="editUser(row)">
            编辑
          </el-button>
          <el-button
            link
            :type="row.is_active ? 'warning' : 'success'"
            size="small"
            @click="toggleUser(row)"
            :disabled="row.id === currentUserId"
          >
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
          <el-button
            link
            type="danger"
            size="small"
            @click="confirmDelete(row)"
            :disabled="row.id === currentUserId"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑用户' : '新建用户'"
      width="500px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱（可选）" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" placeholder="请选择角色">
            <el-option label="管理员" value="admin" />
            <el-option label="操作员" value="operator" />
            <el-option label="查看者" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item label="密码" :prop="isEdit ? 'password' : ''">
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="isEdit ? '留空则不修改密码' : '请输入密码'"
            show-password
          />
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { users as usersApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { formatDate } from '@/utils/date'
import type { User, UserCreate, UserUpdate } from '@/types'

const authStore = useAuthStore()
const currentUserId = computed(() => authStore.user?.id)

const loading = ref(false)
const users = ref<User[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = ref<UserCreate & { id?: number }>({
  username: '',
  password: '',
  email: '',
  role: 'viewer',
  is_active: true,
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 1, max: 50, message: '用户名长度在 1 到 50 个字符', trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  password: [
    { required: !isEdit.value, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少 6 个字符', trigger: 'blur' },
  ],
}

function getRoleType(role: string) {
  const map: Record<string, 'danger' | 'warning' | 'info'> = {
    admin: 'danger',
    operator: 'warning',
    viewer: 'info',
  }
  return map[role] || 'info'
}

function getRoleLabel(role: string) {
  const map: Record<string, string> = {
    admin: '管理员',
    operator: '操作员',
    viewer: '查看者',
  }
  return map[role] || role
}

function showCreateDialog() {
  isEdit.value = false
  form.value = {
    username: '',
    password: '',
    email: '',
    role: 'viewer',
    is_active: true,
  }
  dialogVisible.value = true
}

function editUser(user: User) {
  isEdit.value = true
  form.value = {
    id: user.id,
    username: user.username,
    email: user.email || '',
    role: user.role,
    is_active: user.is_active,
    password: '',
  }
  dialogVisible.value = true
}

async function toggleUser(user: User) {
  if (user.id === currentUserId.value) {
    ElMessage.warning('不能禁用自己')
    return
  }
  try {
    await usersApi.toggleUser(user.id)
    ElMessage.success('用户状态已更新')
    await loadUsers()
  } catch (error) {
    console.error('Toggle user failed:', error)
  }
}

function confirmDelete(user: User) {
  if (user.id === currentUserId.value) {
    ElMessage.warning('不能删除自己')
    return
  }
  ElMessageBox.confirm(
    `确定要删除用户 "${user.username}" 吗？此操作不可恢复。`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
    .then(async () => {
      try {
        await usersApi.deleteUser(user.id)
        ElMessage.success('用户已删除')
        await loadUsers()
      } catch (error) {
        console.error('Delete user failed:', error)
      }
    })
    .catch(() => {})
}

async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      const data: UserCreate | UserUpdate = {
        username: form.value.username,
        email: form.value.email || undefined,
        role: form.value.role,
        is_active: form.value.is_active,
      }

      if (isEdit.value) {
        // Edit mode - password is optional
        if (form.value.password) {
          (data as UserUpdate).password = form.value.password
        }
        await usersApi.updateUser(form.value.id!, data as UserUpdate)
        ElMessage.success('用户已更新')
      } else {
        // Create mode - password is required
        (data as UserCreate).password = form.value.password
        await usersApi.createUser(data as UserCreate)
        ElMessage.success('用户已创建')
      }

      dialogVisible.value = false
      await loadUsers()
    } catch (error) {
      console.error('Submit form failed:', error)
    } finally {
      submitting.value = false
    }
  })
}

async function loadUsers() {
  loading.value = true
  try {
    users.value = await usersApi.listUsers()
  } catch (error) {
    console.error('Load users failed:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.user-list {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h2 {
  margin: 0;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .user-list {
    padding: 10px;
  }

  .header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .header h2 {
    font-size: 18px;
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
  .user-list {
    padding: 5px;
  }

  .header {
    gap: 8px;
  }

  .header h2 {
    font-size: 16px;
  }

  .el-table :deep(.el-table__cell) {
    font-size: 12px;
  }

  /* 隐藏邮箱列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(3)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(3)) {
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
    width: 80px !important;
    font-size: 13px;
  }
}

/* 超小屏适配 */
@media (max-width: 360px) {
  /* 隐藏创建时间列 */
  .el-table :deep(.el-table__body-wrapper td:nth-child(6)) {
    display: none;
  }
  .el-table :deep(.el-table__header-wrapper th:nth-child(6)) {
    display: none;
  }

  :deep(.el-form-item__label) {
    width: 70px !important;
    font-size: 12px;
  }
}
</style>
