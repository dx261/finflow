import axios, { type AxiosError } from 'axios'
import type { ErrorBody } from '@/types'

export const TOKEN_KEY = 'finflow_access_token'

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ErrorBody>) => {
    // On 401 outside the auth endpoints, drop the session and go to login.
    const url = error.config?.url ?? ''
    if (error.response?.status === 401 && !url.includes('/auth/')) {
      localStorage.removeItem(TOKEN_KEY)
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
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
