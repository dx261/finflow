import { defineStore } from 'pinia'
import { api, REFRESH_TOKEN_KEY, TOKEN_KEY } from '@/api/client'
import type { TokenPair, User } from '@/types'
import { authMode } from '@/lib/auth-mode'

interface AuthState {
  user: User | null
  token: string | null
  demoMode: boolean
  initialized: boolean
  startupError: string | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    token: localStorage.getItem(TOKEN_KEY),
    demoMode: false,
    initialized: false,
    startupError: null,
  }),

  getters: {
    isAuthenticated: (state) => (state.demoMode ? Boolean(state.user) : Boolean(state.token)),
    displayName: (state) => (state.demoMode ? '演示用户' : (state.user?.username ?? '未登录')),
  },

  actions: {
    async login(login: string, password: string): Promise<void> {
      const { data } = await api.post<TokenPair>('/auth/login', { login, password })
      this.token = data.access_token
      localStorage.setItem(TOKEN_KEY, data.access_token)
      localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token)
      await this.fetchMe()
    },

    async register(
      username: string,
      email: string,
      password: string,
      registrationToken?: string,
    ): Promise<void> {
      await api.post('/auth/register', {
        username,
        email,
        password,
        registration_token: registrationToken || null,
      })
    },

    async fetchMe(): Promise<void> {
      const { data } = await api.get<User>('/auth/me')
      this.user = data
    },

    async restore(): Promise<void> {
      if (!this.initialized) {
        const { data } = await api.get<{ demo_mode: boolean }>('/auth/config')
        this.demoMode = data.demo_mode
        authMode.demoMode = data.demo_mode
        this.initialized = true
      }
      if (this.demoMode) {
        if (!this.user) await this.fetchMe()
        return
      }
      if (this.token && !this.user) {
        try {
          await this.fetchMe()
        } catch {
          this.logout()
        }
      }
    },

    logout(): void {
      this.user = null
      this.token = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
    },
  },
})
