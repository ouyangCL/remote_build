<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <h2>运维部署平台</h2>
      </template>

      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleLogin" :loading="loading" style="width: 100%">
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="error"
        :title="error"
        type="error"
        :closable="false"
        style="margin-top: 20px"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref()
const loading = ref(false)
const error = ref('')

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  try {
    await formRef.value.validate()
    loading.value = true
    error.value = ''

    await authStore.login(form.username, form.password)

    ElMessage.success('登录成功')
    router.push('/')
  } catch (err: any) {
    // 从 API 响应中提取错误信息
    const errorMessage = err?.response?.data?.detail || err?.message || '登录失败，请稍后重试'
    error.value = errorMessage
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f5f7fa;
  padding: 20px;
}

.login-card {
  width: 400px;
  max-width: 100%;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-radius: 8px;
}

.login-card :deep(.el-card__header) {
  border-bottom: 1px solid #ebeef5;
  padding: 24px 20px;
}

.login-card h2 {
  margin: 0;
  text-align: center;
  color: #303133;
  font-weight: 600;
}

/* 移动端适配 */
@media (max-width: 480px) {
  .login-container {
    padding: 15px;
  }

  .login-card {
    width: 100%;
  }

  .login-card :deep(.el-card__header) {
    padding: 20px 15px;
  }

  .login-card h2 {
    font-size: 18px;
  }

  .login-card :deep(.el-card__body) {
    padding: 20px 15px;
  }
}

/* 小屏移动端适配 */
@media (max-width: 360px) {
  .login-container {
    padding: 10px;
  }

  .login-card :deep(.el-card__header) {
    padding: 16px 12px;
  }

  .login-card h2 {
    font-size: 16px;
  }

  .login-card :deep(.el-card__body) {
    padding: 16px 12px;
  }
}
</style>
