import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'
import { AuthProvider, useAuth } from '../context/AuthContext'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

const Dashboard = () => <div>Dashboard Content</div>
const LoginPage = () => <div>Login Page</div>

const ProtectedRouteAlt = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) return <div>Loading...</div>
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

const LocationDisplay = () => {
  const location = useLocation()
  return <span data-testid="location">{location.pathname}</span>
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('no server'))
  })

  it('redirects to login when not authenticated', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <AuthProvider>
          <LocationDisplay />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRouteAlt>
                  <Dashboard />
                </ProtectedRouteAlt>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('location').textContent).toBe('/login')
    })
  })
})
