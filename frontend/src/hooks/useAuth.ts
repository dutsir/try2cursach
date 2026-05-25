import { useEffect, useState, useCallback } from 'react'
import { api } from '@/api/client'
import type { User } from '@/types'

interface AuthContextType {
  user: User | null
  loading: boolean
  isAuth: boolean
  logout: () => Promise<void>
}

const initialState: AuthContextType = {
  user: null,
  loading: true,
  isAuth: false,
  logout: async () => {},
}

let authState = initialState

export function useAuth(): AuthContextType {
  const [state, setState] = useState(initialState)

  useEffect(() => {
    setState(authState)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/api/auth/logout/', {})
      authState = initialState
      setState(initialState)
    } catch (e) {
      console.error('Logout error:', e)
    }
  }, [])

  return { ...state, logout }
}

export async function initAuth(): Promise<User | null> {
  try {
    const user = await api.get<User>('/api/auth/me/')
    authState = { user, loading: false, isAuth: true, logout: async () => {} }
    return user
  } catch (e) {
    console.error('Auth check failed:', e)
  }
  authState = { ...initialState, loading: false }
  return null
}
