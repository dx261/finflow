import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { api, REFRESH_TOKEN_KEY, TOKEN_KEY } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { authMode } from '@/lib/auth-mode'

const user = {
  id: '00000000-0000-0000-0000-000000000001',
  username: 'owner',
  email: 'owner@example.com',
  role: 'OWNER',
  status: 'ACTIVE',
}

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    authMode.demoMode = false
    vi.restoreAllMocks()
  })

  it('persists both tokens and loads the current user after login', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({
      data: { access_token: 'access', refresh_token: 'refresh', token_type: 'bearer' },
    })
    vi.spyOn(api, 'get').mockResolvedValue({ data: user })

    const auth = useAuthStore()
    await auth.login('owner', 'password')

    expect(auth.user).toEqual(user)
    expect(localStorage.getItem(TOKEN_KEY)).toBe('access')
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('refresh')
  })

  it('removes access and refresh credentials on logout', () => {
    localStorage.setItem(TOKEN_KEY, 'access')
    localStorage.setItem(REFRESH_TOKEN_KEY, 'refresh')
    const auth = useAuthStore()

    auth.logout()

    expect(auth.token).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
  })

  it('enters demo mode without logging in or replacing stored real credentials', async () => {
    localStorage.setItem(TOKEN_KEY, 'real-access')
    const get = vi
      .spyOn(api, 'get')
      .mockResolvedValueOnce({ data: { demo_mode: true } })
      .mockResolvedValueOnce({ data: user })
    const post = vi.spyOn(api, 'post')
    const auth = useAuthStore()

    await auth.restore()
    await auth.restore()

    expect(auth.demoMode).toBe(true)
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.displayName).toBe('演示用户')
    expect(authMode.demoMode).toBe(true)
    expect(get.mock.calls.map(([url]) => url)).toEqual(['/auth/config', '/auth/me'])
    expect(post).not.toHaveBeenCalled()
    expect(localStorage.getItem(TOKEN_KEY)).toBe('real-access')
  })

  it('keeps normal anonymous access unauthenticated when demo is off', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: { demo_mode: false } })
    const auth = useAuthStore()
    await auth.restore()
    expect(auth.demoMode).toBe(false)
    expect(auth.isAuthenticated).toBe(false)
  })
})
