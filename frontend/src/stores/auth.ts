import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

import authApi from '@/api/auth'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const user = ref<User | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const response = await authApi.login({ username, password })
    token.value = response.access_token
    localStorage.setItem('access_token', response.access_token)
    await fetchUser()
  }

  async function fetchUser() {
    if (!token.value) return
    const userData = await authApi.getMe()
    user.value = userData
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    fetchUser,
    logout,
  }
})
