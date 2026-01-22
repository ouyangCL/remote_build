<template>
  <el-container class="dashboard-container">
    <!-- 移动端侧边栏抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :with-header="false"
      direction="ltr"
      size="200px"
      class="sidebar-drawer"
    >
      <div class="logo">
        <h3>运维平台</h3>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        @select="handleMenuSelect"
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
        <el-menu-item index="/users" v-if="isAdmin">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/audit-logs" v-if="isAdmin">
          <el-icon><Document /></el-icon>
          <span>操作记录</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <!-- 桌面端侧边栏 -->
    <el-aside width="200px" class="desktop-sidebar">
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
        <el-menu-item index="/users" v-if="isAdmin">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/audit-logs" v-if="isAdmin">
          <el-icon><Document /></el-icon>
          <span>操作记录</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header>
        <div class="header-content">
          <el-button
            class="menu-toggle"
            :icon="Menu"
            @click="drawerVisible = true"
            circle
          />
          <div class="header-right">
            <span class="username">{{ authStore.user?.username }}</span>
            <el-tag :type="roleType" size="small">{{ authStore.user?.role }}</el-tag>
            <el-button @click="handleLogout" text size="small">退出登录</el-button>
          </div>
        </div>
      </el-header>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Upload,
  Clock,
  Folder,
  Monitor,
  Files,
  User,
  Document,
  Menu,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const drawerVisible = ref(false)
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

function handleMenuSelect() {
  drawerVisible.value = false
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

/* 移动端侧边栏抽屉样式 */
.sidebar-drawer {
  background-color: #304156;
}

.sidebar-drawer :deep(.el-drawer__body) {
  padding: 0;
  background-color: #304156;
}

.el-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 20px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 15px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.username {
  font-size: 14px;
  color: #333;
}

/* 汉堡菜单按钮 - 默认隐藏 */
.menu-toggle {
  display: none;
}

.el-main {
  background-color: #f0f2f5;
  padding: 20px;
}

/* 桌面端侧边栏 - 默认显示 */
.desktop-sidebar {
  display: block;
}

/* 平板和移动端适配 */
@media (max-width: 768px) {
  .el-header {
    padding: 0 15px;
    height: 50px !important;
  }

  /* 显示汉堡菜单按钮 */
  .menu-toggle {
    display: flex;
  }

  /* 隐藏桌面端侧边栏 */
  .desktop-sidebar {
    display: none;
  }

  .header-right {
    gap: 8px;
  }

  .username {
    display: none;
  }

  .el-main {
    padding: 15px;
  }
}

/* 小屏移动端适配 */
@media (max-width: 480px) {
  .el-header {
    padding: 0 10px;
  }

  .header-right {
    gap: 5px;
  }

  .el-tag {
    font-size: 11px;
    padding: 0 5px;
    height: 20px;
    line-height: 20px;
  }

  .el-main {
    padding: 10px;
  }
}
</style>
