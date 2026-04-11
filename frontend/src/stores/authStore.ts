import { create } from 'zustand'
import type { User } from '@/types'
import apiClient from '@/api/client'

interface AuthState {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  initialize: () => Promise<void>
  login: (user: User, accessToken: string, refreshToken: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,

  initialize: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ user: null, isLoading: false, isAuthenticated: false })
      return
    }
    try {
      const { data } = await apiClient.get('/auth/me')
      set({ user: data, isLoading: false, isAuthenticated: true })
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      set({ user: null, isLoading: false, isAuthenticated: false })
    }
  },

  login: (user, accessToken, refreshToken) => {
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshToken)
    set({ user, isLoading: false, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ user: null, isLoading: false, isAuthenticated: false })
    window.location.href = '/login'
  },
}))
