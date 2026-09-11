import { defineStore } from 'pinia'
import { api, TOKEN_KEY } from '@/api/client'
import type { TokenPair, User } from '@/types'

interface AuthState {
  user: User | null
  token: string | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    token: localStorage.getItem(TOKEN_KEY),
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    displayName: (state) => state.user?.username ?? '未登录',
  },

  actions: {
    async login(login: string, password: string): Promise<void> {
      const { data } = await api.post<TokenPair>('/auth/login', { login, password })
      this.token = data.access_token
      localStorage.setItem(TOKEN_KEY, data.access_token)
      await this.fetchMe()
    },

    async register(username: string, email: string, password: string): Promise<void> {
      await api.post('/auth/register', { username, email, password })
    },

    async fetchMe(): Promise<void> {
      const { data } = await api.get<User>('/auth/me')
      this.user = data
    },

    async restore(): Promise<void> {
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
    },
  },
})
