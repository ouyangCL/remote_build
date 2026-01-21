<template>
  <el-container class="dashboard-container">
    <el-aside width="200px">
      <div class="logo">
        <h3>运维平台</h3>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/deploy">
          <el-icon><Upload /></el-icon>
          <span>部署</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>
          <span>历史</span>
        </el-menu-item>
        <el-menu-item index="/projects" v-if="isAdmin">
          <el-icon><Folder /></el-icon>
          <span>项目</span>
        </el-menu-item>
        <el-menu-item index="/servers" v-if="isAdmin">
          <el-icon><Monitor /></el-icon>
          <span>服务器</span>
        </el-menu-item>
        <el-menu-item index="/server-groups" v-if="isAdmin">
          <el-icon><Files /></el-icon>
          <span>服务器组</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header>
        <div class="header-content">
          <span>{{ authStore.user?.username }}</span>
          <el-tag :type="roleType">{{ authStore.user?.role }}</el-tag>
          <el-button @click="handleLogout" text>退出登录</el-button>
        </div>
      </el-header>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)
const isAdmin = computed(() => authStore.user?.role === 'admin')
const roleType = computed(() => {
  const role = authStore.user?.role
  if (role === 'admin') return 'danger'
  if (role === 'operator') return 'warning'
  return 'info'
})

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.dashboard-container {
  height: 100vh;
}

.logo {
  padding: 20px;
  text-align: center;
  background-color: #263445;
}

.logo h3 {
  margin: 0;
  color: #fff;
}

.el-aside {
  background-color: #304156;
}

.el-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 15px;
  width: 100%;
}

.el-main {
  background-color: #f0f2f5;
}
</style>
