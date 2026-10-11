import { beforeEach, describe, expect, it } from 'vitest'
import { api, TOKEN_KEY } from '@/api/client'
import { authMode } from '@/lib/auth-mode'

describe('demo HTTP requests', () => {
  beforeEach(() => {
    localStorage.clear()
    authMode.demoMode = false
  })

  async function requestHeaders() {
    const response = await api.get('/accounts', {
      adapter: async (config) => ({
        config,
        data: config.headers,
        headers: {},
        status: 200,
        statusText: 'OK',
      }),
    })
    return response.data
  }

  it('does not send stored real credentials in demo mode', async () => {
    localStorage.setItem(TOKEN_KEY, 'real-token')
    authMode.demoMode = true
    expect((await requestHeaders()).Authorization).toBeUndefined()
    expect(localStorage.getItem(TOKEN_KEY)).toBe('real-token')
  })

  it('keeps bearer authentication in normal mode', async () => {
    localStorage.setItem(TOKEN_KEY, 'real-token')
    expect((await requestHeaders()).Authorization).toBe('Bearer real-token')
  })
})
