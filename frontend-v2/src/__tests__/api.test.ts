import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { apiFetch, apiFetchNoAuth, ApiError } from '../lib/api'

describe('apiFetch', () => {
  const originalFetch = globalThis.fetch
  const originalLocation = window.location

  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true })
  })

  it('devuelve JSON en 200', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )
    const data = await apiFetch<{ ok: boolean }>('/api/health')
    expect(data).toEqual({ ok: true })
  })

  it('lanza ApiError con detail en errores', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: 'algo falló' }), { status: 400 }),
    )
    await expect(apiFetch('/api/x')).rejects.toMatchObject({
      status: 400,
      detail: 'algo falló',
    })
  })

  it('en 401 redirige a /login y lanza Session expired', async () => {
    const assign = vi.fn()
    Object.defineProperty(window, 'location', { value: { href: '' }, writable: true })
    window.location.href = ''
    Object.defineProperty(window, 'location', { value: { ...window.location, assign }, writable: true })
    vi.mocked(fetch).mockResolvedValue(new Response('{}', { status: 401 }))
    await expect(apiFetch('/api/auth/status')).rejects.toMatchObject({ status: 401 })
    expect(window.location.href).toBe('/login')
  })

  it('apiFetchNoAuth no fuerza credenciales ni redirige en 401', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('{}', { status: 401 }))
    await expect(apiFetchNoAuth('/public')).rejects.toMatchObject({ status: 401 })
    expect(window.location.href).not.toBe('/login')
  })

  it('lanza timeout si excede el limite', async () => {
    vi.mocked(fetch).mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          )
        }),
    )
    await expect(apiFetch('/slow', { timeoutMs: 5 })).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
    })
  })
})
