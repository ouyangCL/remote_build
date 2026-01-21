import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/Dashboard.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/deploy',
      },
      {
        path: 'deploy',
        name: 'Deploy',
        component: () => import('@/views/DeploymentConsole.vue'),
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/DeploymentHistory.vue'),
      },
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/ProjectList.vue'),
      },
      {
        path: 'servers',
        name: 'Servers',
        component: () => import('@/views/ServerList.vue'),
      },
      {
        path: 'server-groups',
        name: 'ServerGroups',
        component: () => import('@/views/ServerGroupList.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth !== false && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    next('/')
  } else {
    // 如果有token但没有用户信息，需要获取用户信息
    if (authStore.isAuthenticated && !authStore.user) {
      await authStore.fetchUser()
    }
    next()
  }
})

export default router
