import axios, { type AxiosError } from 'axios'
import type { ErrorBody } from '@/types'
import { authMode } from '@/lib/auth-mode'

export const TOKEN_KEY = 'finflow_access_token'
export const REFRESH_TOKEN_KEY = 'finflow_refresh_token'

interface TokenResponse {
  access_token: string
  refresh_token: string
}

let refreshRequest: Promise<TokenResponse> | null = null

function refreshTokens(refreshToken: string): Promise<TokenResponse> {
  if (!refreshRequest) {
    refreshRequest = axios
      .post<TokenResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken })
      .then((response) => response.data)
      .finally(() => {
        refreshRequest = null
      })
  }
  return refreshRequest
}

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token && !authMode.demoMode) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ErrorBody>) => {
    const url = error.config?.url ?? ''
    if (!authMode.demoMode && error.response?.status === 401 && !url.includes('/auth/')) {
      const config = error.config as (typeof error.config & { _retry?: boolean }) | undefined
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
      if (config && !config._retry && refreshToken) {
        config._retry = true
        try {
          // Concurrent 401 responses share one refresh request, avoiding a
          // burst of token rotations and retries.
          const tokens = await refreshTokens(refreshToken)
          localStorage.setItem(TOKEN_KEY, tokens.access_token)
          localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
          config.headers.Authorization = `Bearer ${tokens.access_token}`
          return api.request(config)
        } catch {
          // Fall through to a clean logout when refresh is invalid/expired.
        }
      }
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      if (window.location.pathname !== '/login') window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

/** Extract the unified error message from an Axios error. */
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as ErrorBody | undefined
    if (body?.message) return `${body.code}: ${body.message}`
    return error.message
  }
  return String(error)
}
