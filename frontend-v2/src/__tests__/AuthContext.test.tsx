import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import React from 'react'
import { AuthProvider, useAuth } from '../context/AuthContext'

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
)

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('no server'))
  })

  it('is not authenticated initially', () => {
    const { result } = renderHook(() => useAuth(), { wrapper: TestWrapper })
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.isLoading).toBe(true)
  })

  it('login sets authenticated', () => {
    const { result } = renderHook(() => useAuth(), { wrapper: TestWrapper })
    act(() => {
      result.current.login()
    })
    expect(result.current.isAuthenticated).toBe(true)
  })

  it('logout clears authenticated', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: TestWrapper })
    act(() => {
      result.current.login()
    })
    await act(async () => {
      await result.current.logout()
    })
    expect(result.current.isAuthenticated).toBe(false)
  })
})
